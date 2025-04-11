import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import sqlite3

from system import setup_handlers as system_handlers, setup_database
from user import setup_handlers as user_handlers
from feed import setup_handlers as feed_handlers
from admin import setup_handlers as admin_handlers
from random_post import setup_handlers as random_handlers

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота с вашим токеном
TOKEN = 'TOKEN'
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def main():
    # Инициализация базы данных
    conn = sqlite3.connect('database.db')
    setup_database(conn)

    # Подключение обработчиков из модулей
    system_handlers(dp, conn, bot)
    user_handlers(dp, conn, bot)
    feed_handlers(dp, conn, bot)
    admin_handlers(dp, conn, bot)
    random_handlers(dp, conn, bot)

    try:
        logger.info("Бот StoryGram запущен!")
        await dp.start_polling(bot)
    finally:
        await dp.storage.close()
        await bot.session.close()
        conn.close()

if __name__ == "__main__":
    asyncio.run(main())