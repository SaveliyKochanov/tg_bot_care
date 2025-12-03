### ФАЙЛ ФИЛЬТРА ДЛЯ ПРОВЕРКИ ПОЛЬЗОВАТЕЛЯ НА АДМИНА ###

from aiogram.types import Message
from aiogram.filters import BaseFilter

from config_file import config

adm = [int(x.strip()) for x in config.admins.strip().split(',')]
#[int(x) for x in config.admins.split(',')]

class checkAdminFilter(BaseFilter):
    def __init__(self, adm) -> None:
        super().__init__()
        self.admin_ids = adm

    async def __call__(self, message: Message) -> None:
       return message.from_user.id in self.admin_ids

# Отладочный вывод 
print("Admins from .env:", config.admins) 
print("Parsed admins list:", adm) 
print(config.model_dump())