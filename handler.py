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

admin = [int(x.strip()) for x in config.admins.strip().split(',')]
request_chat_id = config.request_chat_id
password_chat_id = config.password_chat_id

wait_users = []

rt = Router() # Отделяем файл с хендлерами от остальных модулей
#rt.message.middleware(AccessMiddleware()) # Подключение пропускного миддлвэйра к роутеру
rt.message.middleware(BanUserMiddleware()) # Подключение бан-миддлвэйра к роутеру

# Класс состояния регистрации пользователя по параметрам: Имя, Номер телефона
class Register(StatesGroup):
    name = State()
    number = State()

# Состояние для блокировки/разблокировки пользователя
class dialog(StatesGroup):
    ban = State()
    unban = State()

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
async def cmd_start(message: types.Message):
    con = sqlite3.connect('db.sqlite3')
    cursor = con.cursor()
    cursor.execute(f"SELECT tg_id FROM users WHERE tg_id = {message.from_user.id}")
    user_id_massive = cursor.fetchall()
    txt_3 = txt.text_3
    if user_id_massive:
        welcome_file = FSInputFile('Добро пожаловать в компанию.pdf')
        about_file = FSInputFile('О компании.pdf')
        await message.reply('Вы в главном меню!') 
        await message.answer(txt_3, reply_markup=keyboard.kb)
        await message.answer('Скачайте файлы, чтобы узнать больше о нашей компании!')
        await message.answer_document(welcome_file)
        await message.answer_document(about_file)
    else:
        await message.reply("Приветствую! Добро пожаловать в чат-бота от Красинтегра!")
        await message.answer('Пройдите регистрацию в боте, чтобы пользоваться функционалом.',reply_markup=keyboard.btn_reg)
    if message.from_user.id in admin and user_id_massive:
        await message.answer('👮‍♂️ Вы авторизованы как Администратор!',reply_markup=keyboard.kb_admin)
        

# Обработчик для кнопки "Меню"
@rt.message(F.text == 'Меню')
async def main_menu(message: types.Message):
    await message.answer('Меню', reply_markup=keyboard.main_menu_btns)

# Обработчик для кнопки "Админ Панель" + проверка на админа
@rt.message(checkAdminFilter(adm), F.text == '💼Админ Панель')
async def admin_commands(message: types.Message):
    await message.answer('Меню Администратора',reply_markup=keyboard.btn_admin)

# Обработчик для команды /help и кнопки F.A.Q.
@rt.callback_query(F.data == 'get_help')
async def handle_help(callback: CallbackQuery):
    await callback.message.answer(txt.text_1)

@rt.message(F.text.contains('❓F.A.Q'))
async def admin_commands(message: types.Message):
    await message.answer(txt.text_1)


# Обработчик для команды /ask 
@rt.callback_query(F.data == 'get_support')
async def handle_support(callback: CallbackQuery):
    await callback.message.answer("Обратитесь в техподдержку: <a href='https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')


# Обработчик для команды /profile и кнопки Профиль
@rt.callback_query(F.data == 'get_profile')
async def handle_profile(callback: CallbackQuery):
    con5 = sqlite3.connect('db.sqlite3') # Подключаемся к бд
    cursor5 = con5.cursor() # Создаем курсор 
    user_id = callback.from_user.id # Получаем ID пользователя
    user_name = callback.from_user.full_name # Получаем Имя пользователя
    cursor5.execute('''SELECT name, number FROM users WHERE tg_id = ?''', (user_id,))
    len_tg = cursor5.fetchone()
    #for name, number in len_tg:
    if len_tg:
      name, number = len_tg
      response = f"👤 Имя пользователя: {user_name}\n\n🔖 ID пользователя: {user_id}\n\n📃 ФИО Пользователя: {name}\n\n☎️ Номер Пользователя: {number}" # Готовим ответ
    await callback.message.reply(response)

# Обработчик для команды /order_cert из Быстрого меню
@rt.callback_query(F.data == 'order_cert')
async def handle_cert(callback: CallbackQuery ):
    await callback.message.answer("Заказать справку можно в личных сообщениях у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')


# Обработчик для команды /write_note из Быстрого меню
@rt.callback_query(F.data == 'write_note')
async def link_docs(callback: CallbackQuery):
    await callback.message.answer('Ссылки на образцы документов: https://drive.google.com/drive/folders/1QRCZIoHT_Ctd-e3XQgH1FKe6mHZh8-Dh?usp=sharing')

# Обработчик для команды /hospital из Быстрого меню
@rt.callback_query(F.data == 'my_hospital')
async def handle_hospital(callback: CallbackQuery):
    await callback.message.answer("Узнать информацию по больничному можно у <a href = 'https://t.me/hr_krasintegra'>HR Krasintegra</a>", parse_mode='HTML')

@rt.callback_query(F.data == 'life_circum')
async def handle_circ(callback: CallbackQuery):
    await callback.message.answer("Перейдите по этой <a href ='https://sfr.gov.ru/grazhdanam/families_with_children'>ссылке</a>, чтобы узнать подробности", parse_mode='HTML')


# Обработчик для команды /my_vac из Быстрого меню
@rt.callback_query(F.data == 'my_vac')
async def info_vac(message: types.Message):
    await message.answer('Выбери одну из опций:',reply_markup=keyboard.btn_my_vac)

# Обработчик для команды /my_term из Быстрого меню
@rt.callback_query(F.data == 'my_term')
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
        await callback.message.answer("Предже, чем регистрироваться, подождите ответ от модератора!")
        return
    await state.set_state(Register.name) # Устанавливаем состояние для ввода имени
    await callback.message.answer('Введите ваше имя') # Делаем запрос имени

# Обработчик для инлайн кнопки "Заблокировать пользователя"
@rt.callback_query(checkAdminFilter(adm),F.data == 'ban_user')
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
    async with async_session() as session:
        result = await session.execute(select(User.tg_id))
        user_ids = [row[0] for row in result.fetchall()]
        sum_users = len(set(user_ids))
        return user_ids, sum_users
    if users_tg: # Вывод данных из колонок
        message = '👥Информация о базе данных пользователей\n\n'
        for tg_id, name, number, reg_date in users_tg:
            message += (f"👤ID Пользователя: {tg_id}\n"
                        f"📝ФИО Пользователя: {name}\n"
                        f"☎️Номер Пользователя: {number}\n"
                        f"📅Дата регистрации: {reg_date}"
                        f"\n〰️〰️〰️〰️〰️〰️〰️〰️〰️\n\n")
        message += f"Всего пользователей в боте: {sum_users}"
    else:
        message = 'Нет данных о людях'
    await callback.message.answer(message) 

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
    con2 = sqlite3.connect('db.sqlite3')
    cur3 = con2.cursor()
    cur3.execute(f"SELECT block_tg_id FROM blocked where block_tg_id = {data_ban['ban']}")
    select_ban = cur3.fetchall()
    if select_ban:
        await message.answer('❌ Пользователь уже заблокирован!')
    else:
      await message.answer('✅ Пользователь успешно заблокирован!')
      await rq.set_ban(data_ban['ban']) # Заносим ID в БД
      cursor2 = con2.cursor() # Создаем курсор для запросов
      cursor2.execute(f'DELETE FROM allow_users WHERE allow_tg_id = ?', (data_ban['ban'],)) # Удаляем запись из вайтлиста
    con2.commit() # Сохраняем
    await state.clear() # Чистим состояние

# Обработчик для состояния разбана юзера
@rt.message(dialog.unban) 
async def unbanan(message: types.Message, state: FSMContext):
    await state.update_data(unban=message.text) # Сохраняем ID в состоянии 
    data_unban = await state.get_data()  # Получаем сохраненные данные

    await message.answer('✅ Пользователь успешно разблокирован!')
    async with async_session() as session:
        allow_user = AllowUser(allow_tg_id=data_unban['unban'])
        session.add(allow_user)

        stmt = delete(BlockedUser).where(BlockedUser.block_tg_id == data_unban['unban'])
        await session.execute(stmt)
 
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
    await message.answer("⏳ Ваша заявка на регистрацию отправлена. Ожидайте подтверждения модератора.")


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
    del wait_users[user_id]
    await callback.bot.send_message(
        chat_id=user_id,
        text=f"""✨ <b>Регистрация подтверждена!</b>

Рады приветствовать вас, <b>{data['name']}</b>! 🎊

Теперь у вас есть доступ к боту бесплатной доставки еды для сотрудников:

🍽️ <b>ЕДА | обеды</b>
🤖 @kras_eda_delivery_bot

📢 <b>Общая группа:</b> <a href="https://t.me/your_company_group">Красинтегра. Общая информация</a>

<i>Для начала работы воспользуйтесь меню ниже 👇</i>""",
        reply_markup=keyboard.kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Отправить логин и пароль", callback_data=f"send_creds_{user_id}")]
        ]
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
async def reject_registration(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])

    fsm_context = FSMContext(
        storage=state.storage,
        key=StorageKey(bot_id=callback.bot.id, chat_id=user_id, user_id=user_id)
    )

    await fsm_context.clear()
    await callback.bot.send_message(chat_id=user_id, reply_markup=ReplyKeyboardRemove(), text="❌ Ваша регистрация была отклонена модератором.")
    await callback.answer("Регистрация отклонена.")



    

