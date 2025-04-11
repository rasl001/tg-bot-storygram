from aiogram import Dispatcher, types, Bot
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import sqlite3
from datetime import datetime

class RegistrationStates(StatesGroup):
    confirm_rules = State()

def setup_database(conn):
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        name TEXT,
        about TEXT,
        rating INTEGER DEFAULT 0,
        posts_count INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        dislikes INTEGER DEFAULT 0,
        last_profile_edit TIMESTAMP,
        is_blocked INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        joined_at TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT,
        content TEXT,
        image_id TEXT,
        is_compressed INTEGER DEFAULT 0,
        created_at TIMESTAMP,
        likes INTEGER DEFAULT 0,
        dislikes INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        user_id INTEGER,
        username TEXT,
        content TEXT,
        created_at TIMESTAMP,
        FOREIGN KEY (post_id) REFERENCES posts(post_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS reactions (
        user_id INTEGER,
        post_id INTEGER,
        reaction TEXT,
        PRIMARY KEY (user_id, post_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        FOREIGN KEY (post_id) REFERENCES posts(post_id)
    )''')

    default_settings = [
        ('welcome_message', 'Добро пожаловать в StoryGram!'),
        ('rules', 'Правила StoryGram:\n1. Только 18+\n2. Без спама\n3. Уважайте других\nStoryGram хранит заполненную вами информацию о себе.'),
        ('info', 'StoryGram - мини-социальная сеть для историй с вашими историями'),
        ('moderation_enabled', '0'),
        ('post_delay', '5')
    ]
    c.executemany('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', default_settings)
    c.execute("INSERT OR IGNORE INTO users (user_id, username, is_admin, joined_at) VALUES (?, ?, ?, ?)",
              (000000000, "admin", 1, datetime.now().isoformat()))
    conn.commit()

def get_main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="Главная")],
        [KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Лента")],
        [KeyboardButton(text="Случайная история")],
        [KeyboardButton(text="Информация")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="Админка")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def setup_handlers(dp: Dispatcher, conn: sqlite3.Connection, bot: Bot):
    @dp.message(Command("start"))
    async def start_command(message: types.Message, state: FSMContext):
        c = conn.cursor()
        user_id = message.from_user.id

        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
        blocked = c.fetchone()
        if blocked and blocked[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return

        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
            is_admin = c.fetchone()[0]
            await message.answer("Место Ваших историй 📄📄📄", reply_markup=get_main_menu(is_admin))
            return

        c.execute("SELECT value FROM settings WHERE key = 'rules'")
        rules = c.fetchone()
        if not rules:
            rules = "Правила отсутствуют. Свяжитесь с администрацией."
        else:
            rules = rules[0]

        await message.answer(
            f"Пожалуйста, согласитесь с условиями использования:\n\n{rules}",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Принять"), KeyboardButton(text="Отклонить")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        await state.set_state(RegistrationStates.confirm_rules)

    @dp.message(RegistrationStates.confirm_rules)
    async def process_rules_confirm(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        c = conn.cursor()

        if message.text.lower() == "принять":
            username = message.from_user.username or f"user_{user_id}"
            is_admin = 1 if user_id == 577690009 else 0
            c.execute("INSERT INTO users (user_id, username, is_admin, joined_at) VALUES (?, ?, ?, ?)",
                      (user_id, username, is_admin, datetime.now().isoformat()))
            conn.commit()

            c.execute("SELECT value FROM settings WHERE key = 'welcome_message'")
            welcome_msg = c.fetchone()[0]

            await message.answer(welcome_msg, reply_markup=get_main_menu(is_admin))
        else:
            await message.answer("Вы не согласились с условиями использования бота.")
        await state.clear()

    @dp.message(lambda message: message.text == "Главная")
    async def main_menu(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        is_admin = result[0] if result else False
        await message.answer("Вы вернулись на главную", reply_markup=get_main_menu(is_admin))

    @dp.message(lambda message: message.text == "Информация")
    async def info(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'info'")
        info_text = c.fetchone()[0]
        await message.answer(info_text, reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Назад")]],
            resize_keyboard=True
        ))

    @dp.message(lambda message: message.text == "Назад")
    async def go_back(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        is_admin = result[0] if result else False
        await message.answer("Вы вернулись в главное меню", reply_markup=get_main_menu(is_admin))