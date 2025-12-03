### ФАЙЛ С MIDDLEWARE ###

import sqlite3

from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import Message, TelegramObject

# Middleware для исполнение блокировки пользоватея
class BanUserMiddleware(BaseMiddleware):
    def __init__(self):
        self.con2 = sqlite3.connect('db.sqlite3')
        self.cursor2 = self.con2.cursor()

    async def __call__(self,
                       handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject,
                       data: Dict[str, Any]) -> Any:
        ban_id = data["event_from_user"].id
        banned = self.cursor2.execute(f"SELECT block_tg_id FROM blocked WHERE block_tg_id = {data['event_from_user'].id}").fetchall()
        if ban_id in banned:
            return await event.bot.send_message('Вы были заблокированы!')
        else:
            return await handler(event,data)

# Основной Middleware для проверки по вайт-листу
class AccessMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.con1 = sqlite3.connect('db.sqlite3')
        self.cursor1 = self.con1.cursor()

    async def __call__(self,
                       handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
                       event: Message,
                       data: Dict[str, Any]) -> Any:
        allowed = self.cursor1.execute(f"SELECT allow_tg_id FROM allow_users WHERE allow_tg_id = {data["event_from_user"].id}").fetchone()
        user_id = data["event_from_user"].id
        if user_id not in allowed:
             return await event.bot.send_message('Нет доступа к данному ресурсу')
        else:
             return await handler(event, data) 
        

