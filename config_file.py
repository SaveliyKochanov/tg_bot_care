### Конфиг файл для работы с .env

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

# Класс определения переменных в .env файле
class Tg_Config(BaseSettings):
    bot_token: SecretStr # Определяем переменную bot_token как SecretStr для хранения конф.данных
    admins: str # Определяем переменную admins как string
    llm_url: str # Определяем переменную llm_url как String
    sql_url: str # Да тут тоже самое
    request_chat_id: str
    password_chat_id: str

    #  Конфигурируем загрузку переменных окружения из файла .env с кодировкой utf-8
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8',extra='allow')

config = Tg_Config() # Создаем экземпляр класса