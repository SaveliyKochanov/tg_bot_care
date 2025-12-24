import re
import sqlite3

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

# ========== СОЗДАЕМ РАЗНЫЕ РОУТЕРЫ ==========
callback_rt = Router()  # Для callback-кнопок (работает везде)
private_rt = Router()   # Для личных сообщений пользователей
groups_rt = Router()    # Для групповых чатов (вопросы, админ-чаты)
admin_rt = Router()     # Для админских команд в личных сообщениях

# Подключаем миддлвары только к нужным роутерам
private_rt.message.middleware(BanUserMiddleware())
admin_rt.message.middleware(BanUserMiddleware())

# ========== ФИЛЬТРЫ ДЛЯ РАЗНЫХ ТИПОВ ЧАТОВ ==========
def private_chat_only():
    """Только личные сообщения"""
    return F.chat.type == "private"

def question_chat_only():
    """Только чат вопросов"""
    return F.chat.id == question_chat_id

def request_chat_only():
    """Только чат заявок на регистрацию"""
    return F.chat.id == request_chat_id

def password_chat_only():
    """Только чат для паролей"""
    return F.chat.id == password_chat_id

# ========== КЛАССЫ СОСТОЯНИЙ ==========
class Register(StatesGroup):
    name = State()
    number = State()

class Ask(StatesGroup):
    user_id = State()
    question = State()
    answer = State()

class dialog(StatesGroup):
    ban = State()
    unban = State()

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

# ========== ФУНКЦИИ-УТИЛИТЫ ==========
async def delete_button_after_time(chat_id, message_id, time, bot: Bot):
    """Удаление кнопки под вопросом через 12 часов"""
    await asyncio.sleep(time)
    await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)

# ========== CALLBACK ОБРАБОТЧИКИ (callback_rt) ==========
# Эти обработчики работают ВЕЗДЕ, независимо от чата

@callback_rt.callback_query(F.data.startswith("answer_"))
async def answer_question(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    
    print(f"=== КНОПКА 'ОТВЕТИТЬ' НАЖАТА ===")
    print(f"Отвечаем пользователю: {user_id}")
    print(f"Кнопку нажал: {callback.from_user.id} (админ: {callback.from_user.id in admin})")
    print(f"В чате: {callback.message.chat.id}")
    
    con = sqlite3.connect('db.sqlite3')
    cursor = con.cursor()
    name = cursor.execute(f'SELECT name FROM users WHERE tg_id = {user_id}').fetchall()[0][0]
    
    await state.update_data(
        user_id=user_id,
        user_name=name,
        question_chat_id=callback.message.chat.id,
        question_message_id=callback.message.message_id
    )
    
    await state.set_state(Ask.answer)
    
    text = f'✏️ Введите ответ для пользователя <b>{name}</b> (ID: {user_id}):'
    await callback.message.answer(text, parse_mode='HTML')
    await callback.answer("Готово к вводу ответа")

@callback_rt.callback_query(F.data.startswith("approve_"))
async def approve_registration(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split("_")[1])

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if user:
            await callback.answer("Уже зарегистрирован.")
            return

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
    
    await bot.send_message(chat_id=password_chat_id, text=text_for_admin, reply_markup=kb, parse_mode="HTML")
    await fsm_context.clear()

@callback_rt.callback_query(F.data.startswith("reject_"))
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

@callback_rt.callback_query(F.data.startswith("send_creds_"))
async def ask_for_creds(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    
    await state.set_state(SendCreds.waiting_for_credentials)
    await state.update_data(target_user_id=user_id)
    
    await callback.answer()
    
    await callback.message.answer(
        "✏️ Введите логин и пароль, которые нужно отправить пользователю. Формат:\n\n<code>Логин: example\nПароль: 123456</code>",
        parse_mode="HTML"
    )

# Общие callback-кнопки
@callback_rt.callback_query(F.data == 'regist')
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
    
    await state.set_state(Register.name)
    await callback.message.answer('Введите ваше ФИО полностью')

@callback_rt.callback_query(F.data == 'find_rest')
async def send_ost(callback: types.CallbackQuery):
    await callback.message.answer("Узнать остаток можно в личных сообщениях у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')

@callback_rt.callback_query(F.data == 'write_vac')
async def send_pdf(callback: types.CallbackQuery):
    pdf_path = FSInputFile("vacation.dotx")
    await callback.message.answer_document(pdf_path, caption='Шаблон заявления на отпуск')

@callback_rt.callback_query(F.data == 'ret_m')
async def send_pdf(callback: types.CallbackQuery):
    pdf_path_2 = FSInputFile("vac_transfer.dotx")
    await callback.message.answer_document(pdf_path_2, caption='Шаблон заявления о переносе отпуска')

@callback_rt.callback_query(F.data == 'time_sheet')
async def send_pdf(callback: types.CallbackQuery):
    pdf_path_3 = FSInputFile("vac_timesheet.pdf")
    await callback.message.answer_document(pdf_path_3, caption='Табель отпусков на текущий год')

@callback_rt.callback_query(F.data == 'check_list')
async def send_xslx(callback: types.CallbackQuery):
    xslx_path = FSInputFile("check_list.xlsx")
    await callback.message.answer_document(xslx_path, caption='Чек-лист')

@callback_rt.callback_query(F.data == 'staff')
async def send_xls(callback: types.CallbackQuery):
    xls_path = FSInputFile("stuff_schedule.xls")
    await callback.message.answer_document(xls_path, caption='Штатное расписание')

@callback_rt.callback_query(checkAdminFilter(adm), F.data == 'numbers_doc')
async def send_doc(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(documents.number)
    await callback.message.answer(f'Загрузите excel-файл (.xlsx или .xls) с номерами.')

@callback_rt.callback_query(checkAdminFilter(adm), F.data == 'employees_doc')
async def send_doc(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(documents.employees)
    await callback.message.answer(f'Загрузите excel-файл (.xlsx или .xls) с данными сотрудников.')

@callback_rt.callback_query(checkAdminFilter(adm), F.data == 'companies_doc')
async def send_doc(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(documents.companies)
    await callback.message.answer(f'Загрузите excel-файл (.xlsx или .xls) с компаниями.')

@callback_rt.callback_query(checkAdminFilter(adm), F.data == 'ban_user')
async def black_list(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(dialog.ban)
    await callback.message.answer('Введите ID пользователя')

@callback_rt.callback_query(checkAdminFilter(adm), F.data == 'unban_user')
async def unban(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(dialog.unban)
    await callback.message.answer('Введите ID Пользователя')

@callback_rt.callback_query(checkAdminFilter(adm), F.data == 'statistic_users')
async def statistic(callback: types.CallbackQuery):
    con2 = sqlite3.connect('db.sqlite3')
    cur3 = con2.cursor()
    users_tg = cur3.execute('SELECT * FROM users').fetchall()
    
    if len(users_tg) > 0:
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

# ========== ОБРАБОТЧИКИ ДЛЯ ЛИЧНЫХ СООБЩЕНИЙ (private_rt) ==========

@private_rt.message(CommandStart(), private_chat_only())
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
        await message.answer('Пройдите регистрацию в боте, чтобы пользоваться функционалом.', reply_markup=keyboard.btn_reg)
    
    if message.from_user.id in admin and user_id_massive:
        await message.answer('👮‍♂️ Вы авторизованы как Администратор!', reply_markup=keyboard.kb_admin)

@private_rt.message(checkAdminFilter(adm), private_chat_only(), F.text == '💼Админ Панель')
async def admin_commands(message: types.Message):
    await message.answer('Меню Администратора', reply_markup=keyboard.btn_admin)

@private_rt.message(Command(commands='help'), private_chat_only())
async def handle_help(message: types.Message):
    await message.answer(txt.text_1)

@private_rt.message(private_chat_only(), F.text.contains('❓F.A.Q'))
async def handle_faq(message: types.Message):
    await message.answer(txt.text_1)

@private_rt.message(private_chat_only(), F.text == '📄Обратиться к hr-у')
async def handle_support(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    for question in questions_in_group:
        if user_id in question:
            await message.answer('❌ Дождитесь ответа от HR!')
            return
    
    await state.set_state(Ask.question)
    await message.answer('''Задайте вопрос HR-специалисту.
Если не хотите, введите "<b>стоп</b>"''', parse_mode='HTML')

@private_rt.message(private_chat_only(), Ask.question, F.text)
async def post_question(message: types.Message, state: FSMContext, bot: Bot):
    if message.text.lower() == 'стоп':
        await message.answer('Вопрос отклонен.')
        await state.clear()
        return
    
    con = sqlite3.connect('db.sqlite3')
    cursor = con.cursor()
    tg_id = message.from_user.id
    name = cursor.execute(f'SELECT name FROM users WHERE tg_id = {tg_id}').fetchall()[0][0]
    
    await state.update_data(user_id=tg_id)
    text = f'''Вопрос от пользователя "{name}"
(ID: {tg_id}):
{message.text}'''
    
    answer_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Ответить', callback_data=f'answer_{message.from_user.id}')]
    ])
    
    question_message = await bot.send_message(chat_id=question_chat_id, text=text, reply_markup=answer_kb)
    questions_in_group.append([tg_id, question_message.message_id])
    
    task = asyncio.create_task(delete_button_after_time(
        chat_id=question_chat_id, 
        message_id=question_message.message_id, 
        time=43200, 
        bot=bot
    ))
    
    answer_btn.append([task, tg_id])
    await state.clear()
    await message.answer('✅ Вопрос отправлен! Ожидайте ответа в течение 12 часов.')

@private_rt.message(private_chat_only(), F.text == '👤Профиль')
async def handle_profile(message: types.Message):
    con5 = sqlite3.connect('db.sqlite3')
    cursor5 = con5.cursor()
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    cursor5.execute('''SELECT name, number FROM users WHERE tg_id = ?''', (user_id,))
    len_tg = cursor5.fetchone()
    
    if len_tg:
        name, number = len_tg
        response = f"👤 Имя пользователя: {user_name}\n\n🔖 ID пользователя: {user_id}\n\n📃 ФИО Пользователя: {name}\n\n☎️ Номер Пользователя: {number}"
        await message.reply(response)

@private_rt.message(private_chat_only(), F.text == '📑Сотрудники')
async def handle_employees(message: types.Message):
    file_name = os.listdir("documents\\employees")[0]
    employees_file = FSInputFile(f'documents\\employees\\{file_name}')
    await message.answer_document(document=employees_file)

@private_rt.message(private_chat_only(), F.text == '🏛️Компания')
async def handle_companies(message: types.Message):
    file_name = os.listdir("documents\\companies")[0]
    companies_file = FSInputFile(f'documents\\companies\\{file_name}')
    await message.answer_document(document=companies_file)

@private_rt.message(private_chat_only(), Command(commands='order_cert'))
async def handle_cert(message: types.Message):
    await message.answer("Заказать справку можно в личных сообщениях у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')

@private_rt.message(private_chat_only(), Command(commands='write_note'))
async def link_docs(message: types.Message):
    await message.answer('Ссылки на образцы документов: https://drive.google.com/drive/folders/1QRCZIoHT_Ctd-e3XQgH1FKe6mHZh8-Dh?usp=sharing')

@private_rt.message(private_chat_only(), Command(commands='hospital'))
async def handle_hospital(message: types.Message):
    await message.answer("Узнать информацию по больничному можно у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')

@private_rt.message(private_chat_only(), Command(commands='life_circum'))
async def handle_circ(message: types.Message):
    await message.answer("Перейдите по этой <a href ='https://sfr.gov.ru/grazhdanam/families_with_children'>ссылке</a>, чтобы узнать подробности", parse_mode='HTML')

@private_rt.message(private_chat_only(), Command(commands='my_vac'))
async def info_vac(message: types.Message):
    await message.answer('Выбери одну из опций:', reply_markup=keyboard.btn_my_vac)

@private_rt.message(private_chat_only(), Command(commands='my_term'))
async def info_term(message: types.Message):
    await message.answer('Выбери одну из опций:', reply_markup=keyboard.btn_my_term)

@private_rt.message(private_chat_only(), Register.name, F.text)
async def reg_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await message.answer('❌ Нельзя использовать команды во время регистрации!')
        return
    
    name_pattern = re.compile(r'^[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+\s[А-ЯЁ][а-яё]+$')
    if not name_pattern.match(message.text):
        await message.answer('❌ Пожалуйста, введите имя в формате "Фамилия Имя Отчество" (например, Иванов Иван Иванович)')
        return
    
    await state.update_data(name=message.text)
    await state.set_state(Register.number)
    await message.answer('Отправьте ваш номер телефона нажав на кнопку "Отправить номер"', reply_markup=keyboard.btn_number)

@private_rt.message(private_chat_only(), Register.number, F.contact)
async def reg_num(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(number=message.contact.phone_number)
    data = await state.get_data()

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

@groups_rt.message(StateFilter(Ask.answer), F.text)
async def send_answer(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    
    if not user_id:
        await message.reply('❌ Ошибка: данные устарели.')
        await state.clear()
        return
    
    print(f"=== ОБРАБОТКА ОТВЕТА ===")
    print(f"Для пользователя: {user_id} ({user_name})")
    print(f"Ответ от: {message.from_user.id}")
    print(f"Текст ответа: {message.text[:50]}...")
    
    # Удаление кнопки "Ответить" с вопроса
    for i in range(len(questions_in_group)):
        if user_id in questions_in_group[i]:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=question_chat_id, 
                    message_id=questions_in_group[i][1], 
                    reply_markup=None
                )
                print(f"✅ Кнопка удалена с сообщения {questions_in_group[i][1]}")
                del questions_in_group[i]
                break
            except Exception as e:
                print(f"❌ Ошибка удаления кнопки: {e}")
    
    for i in range(len(answer_btn)):
        if user_id in answer_btn[i]:
            try:
                answer_btn[i][0].cancel()
                print(f"✅ Таймер отменен для пользователя {user_id}")
                del answer_btn[i]
                break
            except Exception as e:
                print(f"❌ Ошибка отмены таймера: {e}")
    
    await message.reply('✅ Ответ отправлен!')
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f'''📨 Получен ответ от HR:

{message.text}

Если у вас остались вопросы, обратитесь к HR повторно.'''
        )
        print(f"✅ Ответ отправлен пользователю {user_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки пользователю: {e}")
        await message.reply('❌ Не удалось отправить ответ пользователю.')
    
    await state.clear()

@groups_rt.message(password_chat_only(), SendCreds.waiting_for_credentials, F.text)
async def handle_creds_input(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    
    if not target_user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя.")
        await state.clear()
        return
    
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


@admin_rt.message(private_chat_only(), checkAdminFilter(adm), dialog.ban, F.text)
async def banan(message: types.Message, state: FSMContext):
    await state.update_data(ban=message.text)
    data_ban = await state.get_data()
    
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
    
    cur2 = con2.cursor()
    cur2.execute(f'DELETE FROM allow_users WHERE allow_tg_id = {int(message.text)}')
    cur2.execute(f'INSERT INTO blocked (block_tg_id) VALUES ({int(message.text)})')
    con2.commit()
    
    await message.answer('✅ Пользователь успешно заблокирован!')
    await state.clear()

@admin_rt.message(private_chat_only(), checkAdminFilter(adm), dialog.unban, F.text)
async def unbanan(message: types.Message, state: FSMContext):
    await state.update_data(unban=message.text)
    data_unban = await state.get_data()
    
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
    
    cur3.execute(f'DELETE FROM blocked WHERE block_tg_id = {int(message.text)}')
    cur3.execute(f'INSERT INTO allow_users (allow_tg_id) VALUES ({int(message.text)})')
    con2.commit()

    await message.answer('✅ Пользователь успешно разблокирован!')
    await state.clear()

@admin_rt.message(private_chat_only(), checkAdminFilter(adm), documents.number, F.document)
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

@admin_rt.message(private_chat_only(), checkAdminFilter(adm), documents.companies, F.document)
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

@admin_rt.message(private_chat_only(), checkAdminFilter(adm), documents.employees, F.document)
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

__all__ = ['callback_rt', 'private_rt', 'groups_rt', 'admin_rt']