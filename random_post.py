from aiogram import Dispatcher, types, Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import sqlite3
import random
import html
from datetime import datetime
from system import get_main_menu
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RandomPostStates(StatesGroup):
    add_comment = State()

def get_random_post_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Назад")]],
        resize_keyboard=True
    )

def setup_handlers(dp: Dispatcher, conn: sqlite3.Connection, bot: Bot):
    @dp.message(lambda message: message.text == "Случайная история")
    async def random_post(message: types.Message):
        logger.info(f"random_post called for user {message.from_user.id}")
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        c.execute("SELECT post_id, title, content, username, image_id FROM posts p "
                  "JOIN users u ON p.user_id = u.user_id WHERE status = 'approved' "
                  "ORDER BY RANDOM() LIMIT 1")
        post = c.fetchone()

        if not post:
            await message.answer("Пока нет историй!", reply_markup=get_random_post_menu())
            return

        post_id, title, content, username, image_id = post
        short_content = content[:100] + "..." if len(content) > 100 else content
        c.execute("SELECT username, content FROM comments WHERE post_id = ? ORDER BY created_at DESC LIMIT 3",
                  (post_id,))
        comments = c.fetchall()
        comments_text = "\n".join([f"@{c[0]}: {c[1]}" for c in comments]) if comments else "Нет комментариев"
        text = (f"📝 {html.escape(title)}\n{html.escape(short_content)}\n"
                f"Автор: <a href='tg://user?id={post_id}'>@{html.escape(username)}</a>\n"
                f"Комментарии:\n{comments_text}")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Читать дальше", callback_data=f"read_{post_id}")]
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        await message.answer("Вы в случайной истории", reply_markup=get_random_post_menu())

    @dp.callback_query(lambda c: c.data.startswith("read_"))
    async def read_post(callback: types.CallbackQuery):
        logger.info(f"read_post called with callback.data: {callback.data}")
        post_id = int(callback.data.split("_")[1])
        c = conn.cursor()
        c.execute("SELECT title, content, username, image_id FROM posts p "
                  "JOIN users u ON p.user_id = u.user_id WHERE post_id = ?",
                  (post_id,))
        post = c.fetchone()

        if not post:
            await callback.message.edit_text("Пост не найден!")
            await callback.answer()
            return

        title, content, username, image_id = post
        c.execute("SELECT username, content FROM comments WHERE post_id = ? ORDER BY created_at DESC LIMIT 5",
                  (post_id,))
        comments = c.fetchall()
        comments_text = "\n".join([f"@{c[0]}: {c[1]}" for c in comments]) if comments else "Нет комментариев"
        text = (f"📝 {html.escape(title)}\n{html.escape(content)}\n"
                f"Автор: <a href='tg://user?id={post_id}'>@{html.escape(username)}</a>\n"
                f"Комментарии:\n{comments_text}")
        c.execute("SELECT reaction FROM reactions WHERE user_id = ? AND post_id = ?",
                  (callback.from_user.id, post_id))
        existing_reaction = c.fetchone()
        if existing_reaction:
            text += "\n❤️ Лайк учтён"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Комментировать", callback_data=f"comment_{post_id}")]
            ])
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❤️", callback_data=f"like_{post_id}"),
                 InlineKeyboardButton(text="Комментировать", callback_data=f"comment_{post_id}")]
            ])
        if image_id:
            await bot.send_photo(callback.message.chat.id, image_id, caption=text,
                                 parse_mode="HTML", reply_markup=keyboard)
            await callback.message.delete()
        else:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("comment_"))
    async def comment_post(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"comment_post called with callback.data: {callback.data}")
        post_id = int(callback.data.split("_")[1])
        await state.update_data(post_id=post_id)
        await callback.message.reply("Введите ваш комментарий:", reply_markup=get_random_post_menu())
        await state.set_state(RandomPostStates.add_comment)
        await callback.answer()

    @dp.message(RandomPostStates.add_comment)
    async def process_comment(message: types.Message, state: FSMContext):
        logger.info(f"process_comment called for user {message.from_user.id}")
        data = await state.get_data()
        post_id = data["post_id"]
        comment = message.text
        c = conn.cursor()
        c.execute("INSERT INTO comments (post_id, user_id, username, content, created_at) VALUES (?, ?, ?, ?, ?)",
                  (post_id, message.from_user.id, message.from_user.username, comment, datetime.now().isoformat()))
        conn.commit()
        await message.answer("Комментарий добавлен!", reply_markup=get_random_post_menu())
        await state.clear()

    @dp.message(lambda message: message.text == "Назад")
    async def go_back(message: types.Message):
        logger.info(f"go_back called for user {message.from_user.id}")
        c = conn.cursor()
        c.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        is_admin = result[0] if result else False
        await message.answer("Вы вернулись в главное меню", reply_markup=get_main_menu(is_admin))

    @dp.callback_query(lambda c: c.data.startswith("like_"))
    async def process_reaction(callback: types.CallbackQuery):
        logger.info(f"process_reaction called with callback.data: {callback.data}")
        post_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id

        c = conn.cursor()
        c.execute("SELECT reaction FROM reactions WHERE user_id = ? AND post_id = ?", (user_id, post_id))
        if c.fetchone():
            await callback.answer("Вы уже поставили лайк!")
            return

        c.execute("INSERT INTO reactions (user_id, post_id, reaction) VALUES (?, ?, ?)",
                  (user_id, post_id, "like"))
        c.execute("UPDATE posts SET likes = likes + 1 WHERE post_id = ?", (post_id,))
        c.execute("UPDATE users SET likes = likes + 1 WHERE user_id = "
                  "(SELECT user_id FROM posts WHERE post_id = ?)", (post_id,))
        conn.commit()

        # Обновляем текст сообщения, добавляя индикацию лайка
        current_text = callback.message.text or callback.message.caption
        updated_text = f"{current_text}\n❤️ Лайк учтён"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Комментировать", callback_data=f"comment_{post_id}")]
        ])
        if callback.message.photo:
            await bot.edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=updated_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(updated_text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer("Ваш лайк учтён!")