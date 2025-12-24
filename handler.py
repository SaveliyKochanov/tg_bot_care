# Стандартные библиотеки Python
import re
import sqlite3

# Сторонние библиотеки
import requests
from aiogram import Bot, Router, F, types
from aiogram.types import (
    Message, 
    FSInputFile, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy import select, delete
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

# Локальные модули
from config_file import config
import keyb as keyboard
import texts as txt
import data_base.req as rq
from data_base.struct_1 import async_session, User
from middlewares import AccessMiddleware, BanUserMiddleware
from filters import checkAdminFilter, adm

# Дополнительные импорты aiogram для полноты
from aiogram.types import ReplyKeyboardRemove

import asyncio
from datetime import datetime
import os

admin = [int(x.strip()) for x in config.admins.strip().split(',')]
request_chat_id = config.request_chat_id
question_chat_id = config.question_chat_id
password_chat_id = config.password_chat_id

wait_users = []
questions_in_group = []
answer_btn = []

rt = Router() # Отделяем файл с хендлерами от остальных модулей
#rt.message.middleware(AccessMiddleware()) # Подключение пропускного миддлвэйра к роутеру
rt.message.middleware(BanUserMiddleware()) # Подключение бан-миддлвэйра к роутеру

# Класс состояния регистрации пользователя по параметрам: Имя, Номер телефона
class Register(StatesGroup):
    name = State()
    number = State()

# состояние для вопроса пользователя и ответа HR-а
class Ask(StatesGroup):
    user_id = State()
    question = State()
    answer = State()

# Состояние для блокировки/разблокировки пользователя
class dialog(StatesGroup):
    ban = State()
    unban = State()

# Состояние типа документа
class documents(StatesGroup):
    number = State()
    employees = State()
    companies = State()

class SendCreds(StatesGroup):
    waiting_for_credentials = State()

Base = declarative_base()

class AllowUser(Base):
    __tablename__ = 'allow_users'
    id = Column(Integer, primary_key=True, index=True)
    allow_tg_id = Column(String, unique=True)

class BlockedUser(Base):
    __tablename__ = 'blocked'
    id = Column(Integer, primary_key=True, index=True)
    block_tg_id = Column(String, unique=True)

# Обработчик для команды /start
@rt.message(CommandStart())
async def cmd_start(message: types.Message, bot: Bot):
    con = sqlite3.connect('db.sqlite3')
    cursor = con.cursor()
    cursor.execute(f"SELECT tg_id FROM users WHERE tg_id = {message.from_user.id}")
    user_id_massive = cursor.fetchall()
    txt_3 = txt.text_3
    if user_id_massive:
        await message.reply('Вы в главном меню!') 
        await message.answer(txt_3, reply_markup=keyboard.kb)
        await keyboard.set_main_menu(bot)
    else:
        await keyboard.hide_main_menu(bot)
        await message.reply("Приветствую! Добро пожаловать в чат-бота от Красинтегра!", reply_markup=ReplyKeyboardRemove())
        await message.answer('Пройдите регистрацию в боте, чтобы пользоваться функционалом.',reply_markup=keyboard.btn_reg)
    if message.from_user.id in admin and user_id_massive:
        await message.answer('👮‍♂️ Вы авторизованы как Администратор!',reply_markup=keyboard.kb_admin)
        

# Обработчик для кнопки "Админ Панель" + проверка на админа
@rt.message(checkAdminFilter(adm), F.text == '💼Админ Панель')
async def admin_commands(message: types.Message):
    await message.answer('Меню Администратора',reply_markup=keyboard.btn_admin)

# Обработчик для команды /help и кнопки F.A.Q.
@rt.message(Command(commands='help'))
async def handle_help(message: types.Message):
    await message.answer(txt.text_1)

@rt.message(F.text.contains('❓F.A.Q'))
async def admin_commands(message: types.Message):
    await message.answer(txt.text_1)


@rt.message(F.text == '📄Обратиться к hr-у')
async def handle_support(message: types.Message, state: FSMContext):
    data = await state.get_data()
    for question in questions_in_group:
        if data['user_id'] in question:
            await message.answer('❌ Дождитесь ответа от HR!')
            return
    # Состояние ввода вопроса
    await state.set_state(Ask.question)
    await message.answer('''Задайте вопрос HR-специалисту.
Если не хотите, введите "<b>стоп</b>"''', parse_mode='HTML')
    
@rt.message(Ask.question, F.text)
async def post_question(message: types.Message, state: FSMContext, bot: Bot):
    if message.text.lower() == 'стоп':
        await message.answer('Вопрос отклонен.')
        await state.set_state("cancel_question")
        return
    # Получение ФИО и tg_id пользователя
    con = sqlite3.connect('db.sqlite3') # Подключаемся к бд
    cursor = con.cursor() # Создаем курсор
    tg_id = message.from_user.id
    name = cursor.execute(f'SELECT name FROM users WHERE tg_id = {tg_id}').fetchall()[0][0]
    # Отправка вопроса в чат с вопросами
    await state.update_data(user_id=tg_id)
    text = f'''Вопрос от пользователя "{name}"
(ID: {tg_id}):
{message.text}'''
    answer_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Ответить', callback_data=f'answer_{message.from_user.id}')]
    ])
    question_message = await bot.send_message(chat_id=question_chat_id, text=text, reply_markup=answer_kb)
    questions_in_group.append([tg_id, question_message.message_id])
    # Запуск таймера
    task = asyncio.create_task(delete_button_after_time(chat_id=question_chat_id, 
                                                 message_id=question_message.message_id, 
                                                 time=43200, 
                                                 bot=bot))
    answer_btn.append([task, tg_id])
    await state.clear()
    await message.answer('✅ Вопрос отправлен! Ожидайте ответа в течение 12 часов.')

# Удаление кнопки под вопросом через 12 часов
async def delete_button_after_time(chat_id, message_id, time, bot: Bot):
    await asyncio.sleep(time)
    await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)

@rt.callback_query(F.data.startswith("answer_"))
async def answer_question(callback: types.CallbackQuery, state: FSMContext, bot):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(user_id=user_id)
    con = sqlite3.connect('db.sqlite3')
    cursor = con.cursor()
    name = cursor.execute(f'SELECT name FROM users WHERE tg_id = {user_id}').fetchall()[0][0]
    text=f'Введите ответ для пользователя <b>{name}</b>'
    await state.set_state(Ask.answer)
    await bot.send_message(chat_id=question_chat_id, text=text, parse_mode='HTML')

@rt.message(Ask.answer, F.chat.type.in_({"group", "supergroup"}))
async def send_answer(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    # Удаление кнопки "Ответить" с вопроса
    for i in range(len(questions_in_group)):
        if data['user_id'] in questions_in_group[i]:
            await bot.edit_message_reply_markup(chat_id=question_chat_id, message_id=questions_in_group[i][1], reply_markup=None)
            del questions_in_group[i]
            break
    # Удаление счетчика для исчезновения кнопки через 12 часов
    for i in range(len(answer_btn)):
        if data['user_id'] in answer_btn[i]:
            answer_btn[i][0].cancel()
            del answer_btn[i]
            break
    await bot.send_message(chat_id=question_chat_id, text='✅ Ответ отправлен!')
    text = f'''Получен ответ от HR:
{message.text}'''
    await bot.send_message(chat_id=data['user_id'], text=text)


# Обработчик для команды /profile и кнопки Профиль
@rt.message(F.text == '👤Профиль')
async def handle_profile(message: types.Message):
    con5 = sqlite3.connect('db.sqlite3') # Подключаемся к бд
    cursor5 = con5.cursor() # Создаем курсор 
    user_id = message.from_user.id # Получаем ID пользователя
    user_name = message.from_user.full_name # Получаем Имя пользователя
    cursor5.execute('''SELECT name, number FROM users WHERE tg_id = ?''', (user_id,))
    len_tg = cursor5.fetchone()
    #for name, number in len_tg:
    if len_tg:
        name, number = len_tg
        response = f"👤 Имя пользователя: {user_name}\n\n🔖 ID пользователя: {user_id}\n\n📃 ФИО Пользователя: {name}\n\n☎️ Номер Пользователя: {number}" # Готовим ответ
        await message.reply(response)

@rt.message(F.text == '📑Сотрудники')
async def handle_employees(message: types.Message):
    file_name = os.listdir("documents\\employees")[0]
    employees_file = FSInputFile(f'documents\\employees\\{file_name}')
    await message.answer_document(document=employees_file)

@rt.message(F.text == '🏛️Компания')
async def handle_companies(message: types.Message):
    file_name = os.listdir("documents\\companies")[0]
    companies_file = FSInputFile(f'documents\\companies\\{file_name}')
    await message.answer_document(document=companies_file)

# Обработчик для команды /order_cert из Быстрого меню
@rt.message(Command(commands='order_cert'))
async def handle_cert(message: types.Message):
    await message.answer("Заказать справку можно в личных сообщениях у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')


# Обработчик для команды /write_note из Быстрого меню
@rt.message(Command(commands='write_note'))
async def link_docs(message: types.Message):
    await message.answer('Ссылки на образцы документов: https://drive.google.com/drive/folders/1QRCZIoHT_Ctd-e3XQgH1FKe6mHZh8-Dh?usp=sharing')

# Обработчик для команды /hospital из Быстрого меню
@rt.message(Command(commands='hospital'))
async def handle_hospital(message: types.Message):
    await message.answer("Узнать информацию по больничному можно у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')

@rt.message(Command(commands='life_circum'))
async def handle_circ(message: types.Message):
    await message.answer("Перейдите по этой <a href ='https://sfr.gov.ru/grazhdanam/families_with_children'>ссылке</a>, чтобы узнать подробности", parse_mode='HTML')

# Обработчик для команды /my_vac из Быстрого меню
@rt.message(Command(commands='my_vac'))
async def info_vac(message: types.Message):
    await message.answer('Выбери одну из опций:',reply_markup=keyboard.btn_my_vac)

# Обработчик для команды /my_term из Быстрого меню
@rt.message(Command(commands='my_term'))
async def info_term(message: types.Message):
    await message.answer('Выбери одну из опций:',reply_markup=keyboard.btn_my_term)

# Обработчик для регистрации
@rt.callback_query(F.data == 'regist')
async def send_reg(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
    
    if user:
        await callback.message.answer("Вы уже зарегистрированы!")
        return
    if user_id in wait_users:
        await callback.message.answer("Нельзя регистрироваться во время ожидания!")
        return
    await state.set_state(Register.name) # Устанавливаем состояние для ввода имени
    await callback.message.answer('Введите ваше ФИО полностью') # Делаем запрос имени

# Обработчик для инлайн кнопки "Номера"
@rt.callback_query(checkAdminFilter(adm), F.data == 'numbers_doc')
async def send_doc(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(documents.number)
    await callback.message.answer(f'Загрузите excel-файл (.xlsx или .xls) с номерами.')

# Обработчик для инлайн кнопки "Сотрудники"
@rt.callback_query(checkAdminFilter(adm), F.data == 'employees_doc')
async def send_doc(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(documents.employees)
    await callback.message.answer(f'Загрузите excel-файл (.xlsx или .xls) с данными сотрудников.')

# Обработчик для инлайн кнопки "Компании"
@rt.callback_query(checkAdminFilter(adm), F.data == 'companies_doc')
async def send_doc(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(documents.companies)
    await callback.message.answer(f'Загрузите excel-файл (.xlsx или .xls) с компаниями.')

@rt.message(checkAdminFilter(adm), documents.number, F.document)
async def send_numbers(message: types.Message, bot: Bot):
    file_name = message.document.file_name
    if not (file_name.endswith('.xlsx') or file_name.endswith('.xls')):
        await message.answer('❌ Неверный формат файла!')
        return
    file_id = message.document.file_id
    file_path = (await bot.get_file(file_id)).file_path
    download_path = f"documents\\numbers\\{message.document.file_name}"
    for file in os.listdir(path='documents\\numbers'):
        os.remove(f'documents\\numbers\\{file}')
    await bot.download_file(file_path, download_path)
    await message.answer(f'✅ Excel-файл {file_name} успешно заменен!')

@rt.message(checkAdminFilter(adm), documents.companies, F.document)
async def send_numbers(message: types.Message, bot: Bot):
    file_name = message.document.file_name
    if not (file_name.endswith('.xlsx') or file_name.endswith('.xls')):
        await message.answer('❌ Неверный формат файла!')
        return
    file_id = message.document.file_id
    file_path = (await bot.get_file(file_id)).file_path
    download_path = f"documents\\companies\\{message.document.file_name}"
    for file in os.listdir(path='documents\\companies'):
        os.remove(f'documents\\companies\\{file}')
    await bot.download_file(file_path, download_path)
    await message.answer(f'✅ Excel-файл {file_name} успешно заменен!')

@rt.message(checkAdminFilter(adm), documents.employees, F.document)
async def send_numbers(message: types.Message, bot: Bot):
    file_name = message.document.file_name
    if not (file_name.endswith('.xlsx') or file_name.endswith('.xls')):
        await message.answer('❌ Неверный формат файла!')
        return
    file_id = message.document.file_id
    file_path = (await bot.get_file(file_id)).file_path
    download_path = f"documents\\employees\\{message.document.file_name}"
    for file in os.listdir(path='documents\\employees'):
        os.remove(f'documents\\employees\\{file}')
    await bot.download_file(file_path, download_path)
    await message.answer(f'✅ Excel-файл {file_name} успешно заменен!')


# Обработчик для инлайн кнопки "Заблокировать пользователя"
@rt.callback_query(checkAdminFilter(adm), F.data == 'ban_user')
async def black_list(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(dialog.ban) # Устанавливаем состояние для ввода ID
    await callback.message.answer('Введите ID пользователя')

# Обработчик для инлайн кнопки "Разблокировать пользователя"
@rt.callback_query(checkAdminFilter(adm), F.data == 'unban_user')
async def unban(callback: types. CallbackQuery, state: FSMContext):
    await state.set_state(dialog.unban) # Устанавливаем состояние для ввода ID
    await callback.message.answer('Введите ID Пользователя')

# Обработчик для инлайн кнопки "Статистика"
@rt.callback_query(checkAdminFilter(adm), F.data == 'statistic_users')
async def statistic(callback: types. CallbackQuery):
    #async with async_session() as session:
    #    result = await session.execute(select(User.tg_id))
    #    user_ids = [row[0] for row in result.fetchall()]
    #    sum_users = len(set(user_ids))
        #return user_ids, sum_users
    con2 = sqlite3.connect('db.sqlite3')
    cur3 = con2.cursor()
    users_tg = cur3.execute('SELECT * FROM users').fetchall()
    if len(users_tg) > 0: # Вывод данных из колонок
        new_message = '👥Информация о базе данных пользователей\n\n'
        old_message = new_message
        for id, tg_id, name, number, reg_date in users_tg:
            new_message += (f"👤ID Пользователя: {tg_id}\n"
                        f"📝ФИО Пользователя: {name}\n"
                        f"☎️Номер Пользователя: {number}\n"
                        f"📅Дата регистрации: {reg_date}"
                        f"\n〰️〰️〰️〰️〰️〰️〰️〰️〰️\n\n")
            if len(new_message) > 4000: 
                await callback.message.answer(old_message)
                new_message = (f"👤ID Пользователя: {tg_id}\n"
                        f"📝ФИО Пользователя: {name}\n"
                        f"☎️Номер Пользователя: {number}\n"
                        f"📅Дата регистрации: {reg_date}"
                        f"\n〰️〰️〰️〰️〰️〰️〰️〰️〰️\n\n")
                old_message = new_message
                continue
            old_message = new_message
        new_message += f"Всего пользователей в боте: {len(users_tg)}"
    else:
        new_message = 'Нет данных о людях'
    await callback.message.answer(new_message) 

@rt.callback_query(F.data == 'find_rest')
async def send_ost(callback: types.CallbackQuery):
    await callback.message.answer("Узнать остаток можно в личных сообщениях у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>",parse_mode='HTML')

# Обработчик для инлайн-кнопки 'Написать заявление'
@rt.callback_query(F.data == 'write_vac')
async def send_pdf(callback: types.CallbackQuery):
    pdf_path = FSInputFile("vacation.dotx")
    await callback.message.answer_document(pdf_path, caption='Шаблон заявления на отпуск')

# Обработчик для инлайн-кнопки 'Перенести заявление'
@rt.callback_query(F.data == 'ret_m')
async def send_pdf(callback: types.CallbackQuery):
    pdf_path_2 = FSInputFile("vac_transfer.dotx")
    await callback.message.answer_document(pdf_path_2, caption='Шаблон заявления о переносе отпуска')

# Обработчик для инлайн-кнопки 'Табель отпусков'
@rt.callback_query(F.data == 'time_sheet')
async def send_pdf(callback: types.CallbackQuery):
    pdf_path_3 = FSInputFile("vac_timesheet.pdf")
    await callback.message.answer_document(pdf_path_3, caption='Табель отпусков на текущий год')

# Обработчик для инлайн-кнопки 'Чек-лист'
@rt.callback_query(F.data == 'check_list')
async def send_xslx(callback: types.CallbackQuery):
    xslx_path = FSInputFile("check_list.xlsx")
    await callback.message.answer_document(xslx_path, caption='Чек-лист')

# Обработчик для инлайн-кнопки ''Штатное расписание
@rt.callback_query(F.data == 'staff')
async def send_xls(callback: types.CallbackQuery):
    xls_path = FSInputFile("stuff_schedule.xls")
    await callback.message.answer_document(xls_path, caption='Штатное расписание')

# Обработчик для состояния блокировки юзера
@rt.message(dialog.ban) 
async def banan(message: types.Message, state: FSMContext):
    await state.update_data(ban=message.text) # Сохраняем ID в состоянии 
    data_ban = await state.get_data() # Получаем сохраненные данные
    #id_pattern = re.compile(r'^[0-9]{10}$')
    #if not id_pattern.match(message.text):
    #    await message.answer('❌ Неверный id пользователя!')
    #    return
    con2 = sqlite3.connect('db.sqlite3')
    cur3 = con2.cursor()
    cur3.execute(f"SELECT tg_id FROM users where tg_id = {int(message.text)}")
    select_user = cur3.fetchall()
    cur3.execute(f"SELECT block_tg_id FROM blocked where block_tg_id = {int(message.text)}")
    select_block = cur3.fetchall()
    if select_user == []:
        await message.answer('❌ Такого пользователя не существует!')
        return
    if len(select_block) > 0:
        await message.answer('✅ Пользователь уже заблокирован!')
        return
    
    #await rq.set_ban(data_ban['ban']) # Заносим ID в БД
    cur2 = con2.cursor() # Создаем курсор для запросов
    cur2.execute(f'DELETE FROM allow_users WHERE allow_tg_id = {int(message.text)}') # Удаляем запись из вайтлиста
    cur2.execute(f'INSERT INTO blocked (block_tg_id) VALUES ({int(message.text)})')
    con2.commit() # Сохраняем
    await message.answer('✅ Пользователь успешно заблокирован!')
    await state.clear() # Чистим состояние

# Обработчик для состояния разбана юзера
@rt.message(dialog.unban) 
async def unbanan(message: types.Message, state: FSMContext):
    await state.update_data(unban=message.text) # Сохраняем ID в состоянии 
    data_unban = await state.get_data()  # Получаем сохраненные данные
    #id_pattern = re.compile(r'^[0-9]{10}$')
    #if not id_pattern.match(message.text):
    #    await message.answer('❌ Неверный id пользователя!')
    #    return
    con2 = sqlite3.connect('db.sqlite3')
    cur3 = con2.cursor()
    cur3.execute(f"SELECT tg_id FROM users where tg_id = {int(message.text)}")
    select_user = cur3.fetchall()
    cur3.execute(f"SELECT allow_tg_id FROM allow_users where allow_tg_id = {int(message.text)}")
    select_allow = cur3.fetchall()
    if select_user == []:
        await message.answer('❌ Такого пользователя не существует!')
        return
    if len(select_allow) > 0:
        await message.answer('✅ Пользователь уже разблокирован!')
        return
    #async with async_session() as session:
    #    allow_user = AllowUser(allow_tg_id=data_unban['unban'])
    #    session.add(allow_user)
#
    #    stmt = delete(BlockedUser).where(BlockedUser.block_tg_id == data_unban['unban'])
    #    await session.execute(stmt)
    cur3.execute(f'DELETE FROM blocked WHERE block_tg_id = {int(message.text)}')
    cur3.execute(f'INSERT INTO allow_users (allow_tg_id) VALUES ({int(message.text)})')
    con2.commit()

    await message.answer('✅ Пользователь успешно разблокирован!')
    await state.clear() # Чистим состояние

# Обработчик получения имени юзера
@rt.message(Register.name, F.text)
async def reg_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'): # Условие проверки валидности данных
        await message.answer('❌ Нельзя использовать команды во время регистрации!')
        return
    name_pattern = re.compile(r'^[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+$') # Проверяем формат введеных данных на соответсвие 'ФИО'
    if not name_pattern.match(message.text):
        await message.answer('❌ Пожалуйста, введите имя в формате "Фамилия Имя Отчество" (например, Иванов Иван Иванович)')
        return
    await state.update_data(name=message.text) # Сохраняем имя в состоянии
    await state.set_state(Register.number) # Переход к состоянию ввода номера 
    await message.answer('Отправьте ваш номер телефона нажав на кнопку "Отправить номер"', reply_markup=keyboard.btn_number)

# Обработчик для получения данных от юзера и завершение состояния
@rt.message(Register.number, F.contact)
async def reg_num(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(number=message.contact.phone_number) # Сохраняем номер в состоянии
    data = await state.get_data() # Получаем сохраненные данные

    await state.set_state("waiting_for_approval")
    text = f"📥 Новая заявка на регистрацию:\n👤 Имя: {data['name']}\n📱 Номер: {data['number']}\n🆔 TG ID: {message.from_user.id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{message.from_user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{message.from_user.id}")
        ]
    ])
    await bot.send_message(chat_id=request_chat_id, text=text, reply_markup=kb)
    wait_users.append(message.from_user.id)
    await message.answer("⏳ Ваша заявка на регистрацию отправлена. Ожидайте подтверждения модератора.", reply_markup=ReplyKeyboardRemove())


# Обработчик подтверждения заявки администратором
@rt.callback_query(F.data.startswith("approve_"))
async def approve_registration(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split("_")[1])

    async with async_session() as session:
        # Проверяем, нет ли уже пользователя в БД
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if user:
            await callback.answer("Уже зарегистрирован.")
            return

    # ❗ Получаем контекст состояния пользователя через существующее состояние FSM
    fsm_context = FSMContext(
        storage=state.storage,
        key=StorageKey(bot_id=callback.bot.id, chat_id=user_id, user_id=user_id)
    )

    data = await fsm_context.get_data()

    # Сохраняем пользователя
    await rq.set_user(user_id, data['name'], data['number'])
    del wait_users[wait_users.index(user_id)]
    await keyboard.set_main_menu(bot)

    await callback.bot.send_message(chat_id=user_id, text='✨ <b>Регистрация подтверждена!</b>', parse_mode="HTML")
    photo_file = FSInputFile('logo.png', filename='logo.png')
    await bot.send_photo(chat_id=user_id, photo=photo_file, caption=f'''Рады приветствовать вас, <b>{data['name']}</b>!
Теперь у вас есть доступ к информационному боту поддержки сотрудников компании КрасИнтегра.''', parse_mode="HTML")
    await callback.bot.send_message(chat_id=user_id, text='Презентации для новичков.')
    welcome_file = FSInputFile('Добро пожаловать в компанию.pdf')
    about_file = FSInputFile('О компании.pdf')
    await callback.bot.send_document(chat_id=user_id, document=welcome_file)
    await callback.bot.send_document(chat_id=user_id, document=about_file)
    await callback.bot.send_message(
        chat_id=user_id,
        text=f"""
📢 Просим зарегистрироваться в общем чате Красинтегры:
<a href="https://t.me/your_company_group">Красинтегра. Общая информация</a>

📢 Просим зарегистрироваться в официальной группе ВК:
<a href="https://vk.com/krasintegra_it">Красинтегра. Группа ВК</a>

📢 Просим зарегистрироваться в боте заказа обедов:
<a href="https://web.telegram.org/a/#7595569646">@kras_eda_delivery_bot</a>

<i>По кадровым вопросам воспользуйтесь меню ниже: 👇</i>""",
        reply_markup=keyboard.kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Отправить логин и пароль", callback_data=f"send_creds_{user_id}")]
        ]
    )
    await bot.edit_message_reply_markup(
       chat_id=callback.message.chat.id,
       message_id=callback.message.message_id,
       reply_markup=None
    )
    
    text_for_admin = f"""🆕 Новый пользователь прошёл регистрацию:

    👤 <b>{data['name']}</b>
    📞 <code>{data['number']}</code>
    🆔 <code>{user_id}</code>

    Вы можете отправить ему логин и пароль."""
    # Отправляем красивое сообщение пользователю
    await bot.send_message(chat_id=password_chat_id, text=text_for_admin, reply_markup=kb, parse_mode="HTML")
    # Завершаем состояние
    await fsm_context.clear()

@rt.callback_query(F.data.startswith("send_creds_"))
async def ask_for_creds(callback: types.CallbackQuery, state: FSMContext):
    print(f"SEND_CREDS: callback.data = {callback.data}")
    user_id = int(callback.data.split("_")[2])
    print(f"SEND_CREDS: user_id = {user_id}")
    
    # Сохраняем ID, кому отправлять логин/пароль
    await state.set_state(SendCreds.waiting_for_credentials)
    await state.update_data(target_user_id=user_id)
    
    # Отвечаем на callback, чтобы убрать "часики" на кнопке
    await callback.answer()
    
    await callback.message.answer(
        "✏️ Введите логин и пароль, которые нужно отправить пользователю. Формат:\n\n<code>Логин: example\nПароль: 123456</code>",
        parse_mode="HTML"
    )

@rt.message(SendCreds.waiting_for_credentials)
async def handle_creds_input(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    
    if not target_user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя.")
        await state.clear()
        return
    
    # Отправка пользователю
    try:
        await bot.send_message(
            chat_id=target_user_id,
            text=f"""🔐 <b>Ваши данные для входа:</b>

{message.text}

Если возникнут вопросы, обращайтесь к технической поддержке.
""",
            parse_mode="HTML"
        )
        await message.answer("✅ Логин и пароль успешно отправлены пользователю.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")
    
    await state.clear()


@rt.callback_query(F.data.startswith("reject_"))
async def reject_registration(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split("_")[1])

    fsm_context = FSMContext(
        storage=state.storage,
        key=StorageKey(bot_id=callback.bot.id, chat_id=user_id, user_id=user_id)
    )
    del wait_users[wait_users.index(user_id)]
    await fsm_context.clear()
    await callback.bot.send_message(chat_id=user_id, reply_markup=ReplyKeyboardRemove(), text="❌ Ваша регистрация была отклонена модератором.")
    await callback.answer("Регистрация отклонена.")
    
    await bot.edit_message_reply_markup(
       chat_id=callback.message.chat.id,
       message_id=callback.message.message_id,
       reply_markup=None
    )



    

