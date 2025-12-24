### Файл с реализцией клавиатурных и инлайн кнопок ###

from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import BotCommand

# Основная клавиатура с кнопками исполнения команд 
kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text = '👤Профиль')],
                                   [KeyboardButton(text = '📑Сотрудники')],
                                   [KeyboardButton(text = '🏛️Компания')],
                                   #[KeyboardButton(text = '📞Номера')],
                                   [KeyboardButton(text = '📄Обратиться к hr-у')]],
                        resize_keyboard=True)

# Экземпляр основной клавиатуры для авторизованного админа
kb_admin = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text = '👤Профиль')],
                                   [KeyboardButton(text = '📑Сотрудники')],
                                   [KeyboardButton(text = '🏛️Компания')],
                                   #[KeyboardButton(text = '📞Номера')],
                                   [KeyboardButton(text = '📄Обратиться к hr-у')],
                                   [KeyboardButton(text = '💼Админ Панель')]], 
                        resize_keyboard=True)

# Кнопка с функцией "Поделиться контактом" на этапе регистрации
btn_number = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Отправить номер',
                                                           request_contact=True, one_time_keyboard=True)]],
                                 resize_keyboard=True)

# Инлайн кнопка регистрация 
btn_reg = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text = 'Регистрация', callback_data = 'regist')]])

# Инлайн кнопка с ссылкой в главном меню после исполнения /start
btn_menu_start = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text = 'Подписаться на группу!', callback_data='menu_start', url='https://vk.com/krasintegra_it')]])

# Инлайн кнопка для команды /my_vac
btn_my_vac = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text = 'Узнать остаток', callback_data='find_rest')],
    [InlineKeyboardButton(text = 'Написать заявление на отпуск', callback_data='write_vac')],
    [InlineKeyboardButton(text = 'Перенести',callback_data='ret_m')],
    [InlineKeyboardButton(text = 'Табель отпусков на текущий год',callback_data='time_sheet')]])

# Инлайн кнопка для команды /my_term
btn_my_term = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text = 'Чек-лист', callback_data='check_list')],
    [InlineKeyboardButton(text = 'Штатное расписание',callback_data='staff')]])

# Инлайн кнопка для админ панели
btn_admin = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text = 'Заблокировать пользователя',callback_data='ban_user')],
    [InlineKeyboardButton(text = 'Разблокировать пользователя',callback_data = 'unban_user')],
    [InlineKeyboardButton(text = 'Статистика',callback_data='statistic_users')],
    [InlineKeyboardButton(text = 'Номера',callback_data='numbers_doc')],
    [InlineKeyboardButton(text = 'Компании',callback_data='companies_doc')],
    [InlineKeyboardButton(text = 'Сотрудники',callback_data='employees_doc')]
])

main_menu_btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data='get_help')],
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data='get_support')],
        [InlineKeyboardButton(text="📄 Справка", callback_data='order_cert')],
        [InlineKeyboardButton(text="📝 Заявление", callback_data='write_note')],
        [InlineKeyboardButton(text="🤒 Больничный", callback_data='my_hospital')],
        [InlineKeyboardButton(text="🏠 Обстоятельства", callback_data='life_circum')],
        [InlineKeyboardButton(text="🏖 Отпуск", callback_data='my_vac')],
        [InlineKeyboardButton(text="⏳ Испыт. срок", callback_data='my_term')],
])

# Фунция создания быстрого меню команд(Бургер-меню)
async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command="/start", description="Перезапуск бота"),
        #BotCommand(command="/help", description="Основная Информация"),
        # BotCommand(command="/order_cert",description="Заказать справку"),
        # BotCommand(command="/write_note",description="Написать заявление"),
        # BotCommand(command="/hospital",description="Мой больничный"),
        # BotCommand(command="/life_circum",description="Жизненные обстоятельства"),
        # BotCommand(command="/my_vac", description = "Мой отпуск"),
        # BotCommand(command="/my_term",description = "Мой испытательный срок")
        ]     
    await bot.set_my_commands(main_menu_commands)

async def hide_main_menu(bot: Bot):
    await bot.set_my_commands([])

# кливиатура для подтверждения или отклонения заявки пользователя на регистрацию
approve_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data="approve_{}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data="reject_{}")
        ]
    ]
)

# Кнопка для ответа на сообщение пользователя
answer_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='Ответить', callback_data='answer_{}') 
        ]
    ]
)