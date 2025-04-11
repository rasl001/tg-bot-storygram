from aiogram import Dispatcher, types, Bot
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    edit_welcome = State()
    edit_info = State()
    edit_rules = State()
    block_user = State()
    set_delay = State()

def get_admin_menu():
    buttons = [
        [KeyboardButton(text="Редактировать приветствие"), KeyboardButton(text="Редактировать информацию")],
        [KeyboardButton(text="Редактировать правила"), KeyboardButton(text="Блокировать пользователя")],
        [KeyboardButton(text="Список заблокированных"), KeyboardButton(text="Модерация постов")],
        [KeyboardButton(text="Настройки модерации"), KeyboardButton(text="Задержка постов")],
        [KeyboardButton(text="Удалить пост"), KeyboardButton(text="Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def setup_handlers(dp: Dispatcher, conn: sqlite3.Connection, bot: Bot):
    @dp.message(lambda message: message.text == "Админка")
    async def admin_menu(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if not result or not result[0]:
            await message.answer("У вас нет доступа к админке!")
            return
        await message.answer("Панель администратора", reply_markup=get_admin_menu())

    @dp.message(lambda message: message.text == "Редактировать приветствие")
    async def edit_welcome(message: types.Message, state: FSMContext):
        await message.answer("Введите новое приветственное сообщение:")
        await state.set_state(AdminStates.edit_welcome)

    @dp.message(AdminStates.edit_welcome)
    async def process_welcome(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'welcome_message'", (message.text,))
        conn.commit()
        await message.answer("Приветствие обновлено!", reply_markup=get_admin_menu())
        await state.clear()

    @dp.message(lambda message: message.text == "Редактировать информацию")
    async def edit_info(message: types.Message, state: FSMContext):
        await message.answer("Введите новый текст информации:")
        await state.set_state(AdminStates.edit_info)

    @dp.message(AdminStates.edit_info)
    async def process_info(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'info'", (message.text,))
        conn.commit()
        await message.answer("Информация обновлена!", reply_markup=get_admin_menu())
        await state.clear()

    @dp.message(lambda message: message.text == "Редактировать правила")
    async def edit_rules(message: types.Message, state: FSMContext):
        await message.answer("Введите новый текст правил:")
        await state.set_state(AdminStates.edit_rules)

    @dp.message(AdminStates.edit_rules)
    async def process_rules(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = 'rules'", (message.text,))
        conn.commit()
        await message.answer("Правила обновлены!", reply_markup=get_admin_menu())
        await state.clear()

    @dp.message(lambda message: message.text == "Блокировать пользователя")
    async def block_user(message: types.Message, state: FSMContext):
        await message.answer("Введите ник пользователя (с @):")
        await state.set_state(AdminStates.block_user)

    @dp.message(AdminStates.block_user)
    async def process_block(message: types.Message, state: FSMContext):
        username = message.text.lstrip("@")
        c = conn.cursor()
        c.execute("UPDATE users SET is_blocked = 1 WHERE username = ?", (username,))
        if c.rowcount == 0:
            await message.answer("Пользователь не найден!")
        else:
            c.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            user_id = c.fetchone()[0]
            await bot.send_message(user_id, "Администрация StoryGram заблокировала вас.")
            await message.answer("Пользователь заблокирован!", reply_markup=get_admin_menu())
        conn.commit()
        await state.clear()

    @dp.message(lambda message: message.text == "Список заблокированных")
    async def blocked_list(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE is_blocked = 1")
        blocked = c.fetchall()

        if not blocked:
            await message.answer("Нет заблокированных пользователей", reply_markup=get_admin_menu())
            return

        text = "Заблокированные пользователи:\n" + "\n".join([f"@{u[0]}" for u in blocked])
        buttons = [[KeyboardButton(text=f"Разблокировать @{u[0]}") for u in blocked[:2]],
                   [KeyboardButton(text="Назад")]]
        keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
        await message.answer(text, reply_markup=keyboard)

    @dp.message(lambda message: message.text and message.text.startswith("Разблокировать @"))
    async def unblock_user(message: types.Message):
        username = message.text.split("@")[1]
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        if user:
            user_id = user[0]
            c.execute("UPDATE users SET is_blocked = 0 WHERE username = ?", (username,))
            conn.commit()
            await bot.send_message(user_id, "Вы были разблокированы администрацией StoryGram!")
            await message.answer(f"@{username} разблокирован!", reply_markup=get_admin_menu())
        else:
            await message.answer(f"Пользователь @{username} не найден.", reply_markup=get_admin_menu())

    @dp.message(lambda message: message.text == "Модерация постов")
    async def moderate_posts(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT post_id, title, content, image_id, username FROM posts p "
                  "JOIN users u ON p.user_id = u.user_id WHERE status = 'pending' ORDER BY created_at ASC LIMIT 5")
        posts = c.fetchall()

        if not posts:
            await message.answer("Нет постов на модерации", reply_markup=get_admin_menu())
            return

        for post_id, title, content, image_id, username in posts:
            short_content = content[:100] + "..." if len(content) > 100 else content
            text = f"📝 {title}\n{short_content}\nАвтор: @{username}"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"Одобрить: {title[:15]}..." if len(title) > 15 else f"Одобрить: {title}",
                                      callback_data=f"approve_{post_id}"),
                 InlineKeyboardButton(text=f"Вернуть: {title[:15]}..." if len(title) > 15 else f"Вернуть: {title}",
                                      callback_data=f"return_{post_id}")]
            ])

            if image_id:
                await bot.send_photo(message.chat.id, photo=image_id, caption=text, reply_markup=keyboard)
            else:
                await message.answer(text, reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith("approve_"))
    async def approve_post(callback: types.CallbackQuery):
        post_id = int(callback.data.split("_")[1])
        c = conn.cursor()
        c.execute("SELECT user_id, title FROM posts WHERE post_id = ?", (post_id,))
        user_id, title = c.fetchone()
        c.execute("UPDATE posts SET status = 'approved' WHERE post_id = ?", (post_id,))
        c.execute("UPDATE users SET posts_count = posts_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()

        await bot.send_message(user_id, f"История '{title}' прошла модерацию и опубликована ✅")
        if callback.message.photo:
            await callback.message.edit_caption(caption=callback.message.caption + "\n✅ Пост одобрен!",
                                                reply_markup=None)
        else:
            await callback.message.edit_text(callback.message.text + "\n✅ Пост одобрен!", reply_markup=None)
        await callback.answer("Пост одобрен!")

    @dp.callback_query(lambda c: c.data.startswith("return_"))
    async def return_post(callback: types.CallbackQuery):
        post_id = int(callback.data.split("_")[1])
        c = conn.cursor()
        c.execute("SELECT user_id, title FROM posts WHERE post_id = ?", (post_id,))
        user_id, title = c.fetchone()
        c.execute("UPDATE posts SET status = 'returned' WHERE post_id = ?", (post_id,))
        conn.commit()

        await bot.send_message(user_id, f"История '{title}' не прошла модерацию и возвращена на доработку ❌")
        if callback.message.photo:
            await callback.message.edit_caption(caption=callback.message.caption + "\n↩️ Пост возвращён на доработку!",
                                                reply_markup=None)
        else:
            await callback.message.edit_text(callback.message.text + "\n↩️ Пост возвращён на доработку!",
                                             reply_markup=None)
        await callback.answer("Пост возвращён на доработку!")

    @dp.message(lambda message: message.text == "Настройки модерации")
    async def moderation_settings(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'moderation_enabled'")
        current = c.fetchone()[0]
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Включить модерацию"), KeyboardButton(text="Выключить модерацию")],
                [KeyboardButton(text="Назад")]
            ],
            resize_keyboard=True
        )
        await message.answer(f"Модерация сейчас: {'включена' if current == '1' else 'выключена'}",
                             reply_markup=keyboard)

    @dp.message(lambda message: message.text in ["Включить модерацию", "Выключить модерацию"])
    async def toggle_moderation(message: types.Message):
        c = conn.cursor()
        value = '1' if message.text == "Включить модерацию" else '0'
        c.execute("UPDATE settings SET value = ? WHERE key = 'moderation_enabled'", (value,))
        conn.commit()
        await message.answer(f"Модерация {'включена' if value == '1' else 'выключена'}!",
                             reply_markup=get_admin_menu())

    @dp.message(lambda message: message.text == "Задержка постов")
    async def set_delay(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'post_delay'")
        current = c.fetchone()[0]
        await message.answer(f"Текущая задержка: {current} минут\nВведите новое значение (в минутах):")
        await state.set_state(AdminStates.set_delay)

    @dp.message(AdminStates.set_delay)
    async def process_delay(message: types.Message, state: FSMContext):
        try:
            delay = int(message.text)
            if delay < 1:
                raise ValueError
            c = conn.cursor()
            c.execute("UPDATE settings SET value = ? WHERE key = 'post_delay'", (delay,))
            conn.commit()
            await message.answer(f"Задержка установлена: {delay} минут", reply_markup=get_admin_menu())
            await state.clear()
        except ValueError:
            await message.answer("Введите корректное число!")

    @dp.message(lambda message: message.text == "Удалить пост")
    async def delete_post_menu(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT post_id, title, username FROM posts p JOIN users u ON p.user_id = u.user_id "
                  "WHERE status = 'approved' ORDER BY created_at DESC LIMIT 5")
        posts = c.fetchall()
        if not posts:
            await message.answer("Нет опубликованных постов для удаления.", reply_markup=get_admin_menu())
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{title} (@{username})", callback_data=f"admin_delete_{post_id}")]
            for post_id, title, username in posts
        ])
        await message.answer("Выберите пост для удаления:", reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith("admin_delete_"))
    async def delete_post(callback: types.CallbackQuery):
        try:
            post_id = int(callback.data.split("_")[2])
            c = conn.cursor()
            c.execute("SELECT title, user_id FROM posts WHERE post_id = ?", (post_id,))
            post = c.fetchone()
            if post:
                title, user_id = post
                c.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
                conn.commit()
                await bot.send_message(user_id, f"История '{title}' удалена администрацией.")
                await callback.message.edit_text(f"Пост '{title}' удалён.", reply_markup=None)
                await callback.answer("Удаление завершено!")
            else:
                await callback.answer("Пост не найден!")
        except (IndexError, ValueError) as e:
            logger.error(f"Ошибка в delete_post: {e}")
            await callback.answer("Ошибка при удалении поста.")