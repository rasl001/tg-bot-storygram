from aiogram import Dispatcher, types, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ContentType
from aiogram import F
import sqlite3
import logging
from datetime import datetime, timedelta
from system import get_main_menu

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProfileStates(StatesGroup):
    edit_name = State()
    edit_about = State()
    add_post_title = State()
    add_post_content = State()
    add_post_image = State()
    add_post_compression = State()
    awaiting_photo = State()
    add_comment = State()

def get_profile_menu(has_pending_posts=False):
    buttons = [
        [KeyboardButton(text="Обо мне"), KeyboardButton(text="Мой рейтинг")],
        [KeyboardButton(text="Мои истории"), KeyboardButton(text="Добавить историю")]
    ]
    if has_pending_posts:
        buttons.append([KeyboardButton(text="Модерация")])
    buttons.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def calculate_rating(posts_count):
    if posts_count >= 200:
        return "★★★★★"
    elif posts_count >= 100:
        return "★★★★☆"
    elif posts_count >= 50:
        return "★★★☆☆"
    elif posts_count >= 10:
        return "★★☆☆☆"
    return "★☆☆☆☆"

def setup_handlers(dp: Dispatcher, conn: sqlite3.Connection, bot: Bot):
    @dp.message(lambda message: message.text == "Профиль")
    async def profile_menu(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        c.execute("SELECT COUNT(*) FROM posts WHERE user_id = ? AND status IN ('pending', 'returned')",
                  (message.from_user.id,))
        has_pending = c.fetchone()[0] > 0
        await message.answer("Ваш профиль", reply_markup=get_profile_menu(has_pending))

    @dp.message(lambda message: message.text == "Обо мне")
    async def about_me(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        c.execute("SELECT name, about, last_profile_edit, username FROM users WHERE user_id = ?",
                  (message.from_user.id,))
        user = c.fetchone()

        if not user[0]:
            await message.answer("Введите ваше имя:")
            await state.set_state(ProfileStates.edit_name)
            return

        text = f"Ник: @{user[3]}\nИмя: {user[0]}\nОбо мне: {user[1] or 'Не указано'}"
        can_edit = not user[2] or (datetime.now() - datetime.fromisoformat(user[2])).days > 30
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Изменить")] if can_edit else [], [KeyboardButton(text="Назад")]],
            resize_keyboard=True
        )
        if can_edit:
            await message.answer(text, reply_markup=keyboard)
        else:
            last_edit = datetime.fromisoformat(user[2])
            next_edit_date = last_edit + timedelta(days=30)
            days_left = (next_edit_date - datetime.now()).days
            await message.answer(
                f"{text}\n\nРедактирование профиля доступно раз в месяц. "
                f"Следующее редактирование возможно {next_edit_date.strftime('%d.%m.%Y')} "
                f"(через {days_left} дн.)",
                reply_markup=keyboard
            )

    @dp.message(lambda message: message.text == "Изменить")
    async def edit_profile(message: types.Message, state: FSMContext):
        await message.answer("Введите новое имя:")
        await state.set_state(ProfileStates.edit_name)

    @dp.message(StateFilter(ProfileStates.edit_name))
    async def process_name(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)
        await message.answer("Введите информацию о себе:")
        await state.set_state(ProfileStates.edit_about)

    @dp.message(StateFilter(ProfileStates.edit_about))
    async def process_about(message: types.Message, state: FSMContext):
        data = await state.get_data()
        c = conn.cursor()
        c.execute("UPDATE users SET name = ?, about = ?, last_profile_edit = ? WHERE user_id = ?",
                  (data['name'], message.text, datetime.now().isoformat(), message.from_user.id))
        conn.commit()
        await message.answer("Профиль обновлен!", reply_markup=get_profile_menu())
        await state.clear()

    @dp.message(lambda message: message.text == "Мой рейтинг")
    async def my_rating(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        c.execute("SELECT posts_count, likes FROM users WHERE user_id = ?",
                  (message.from_user.id,))
        stats = c.fetchone()

        rating = calculate_rating(stats[0])
        text = (f"Ваш рейтинг: {rating}\n"
                f"📝 Постов: {stats[0]}\n"
                f"❤️ Лайков: {stats[1]}")
        await message.answer(text, reply_markup=get_profile_menu())

    @dp.message(lambda message: message.text == "Мои истории")
    async def my_posts(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        c.execute("SELECT post_id, title, content, status FROM posts WHERE user_id = ? "
                  "AND status = 'approved' ORDER BY created_at ASC LIMIT 10", (message.from_user.id,))
        posts = c.fetchall()

        if not posts:
            await message.answer("У вас пока нет опубликованных историй", reply_markup=get_profile_menu())
            return

        await state.update_data(last_post_id=posts[-1][0])
        for post in posts:
            post_id, title, content, status = post
            short_content = content[:100] + "..." if len(content) > 100 else content
            c.execute("SELECT username, content FROM comments WHERE post_id = ? ORDER BY created_at DESC LIMIT 3",
                      (post_id,))
            comments = c.fetchall()
            comments_text = "\n".join([f"@{c[0]}: {c[1]}" for c in comments]) if comments else "Нет комментариев"
            text = f"📝 {title}\n{short_content}\nКомментарии:\n{comments_text}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Читать дальше", callback_data=f"read_{post_id}"),
                 InlineKeyboardButton(text="Удалить", callback_data=f"delete_{post_id}")]
            ])
            await message.answer(text, reply_markup=keyboard)

        c.execute("SELECT COUNT(*) FROM posts WHERE user_id = ? AND status = 'approved' AND post_id > ?",
                  (message.from_user.id, posts[-1][0]))
        more_posts = c.fetchone()[0] > 0
        if more_posts:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Загрузить ещё", callback_data="load_more_my_posts")]
            ])
            await message.answer("Ваши истории", reply_markup=keyboard)
        else:
            await message.answer("Ваши истории", reply_markup=get_profile_menu())

    @dp.callback_query(lambda c: c.data == "load_more_my_posts")
    async def load_more_my_posts(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"load_more_my_posts called for user {callback.from_user.id}")
        data = await state.get_data()
        last_post_id = data.get("last_post_id", 0)
        c = conn.cursor()
        c.execute("SELECT post_id, title, content, status FROM posts WHERE user_id = ? "
                  "AND status = 'approved' AND post_id > ? ORDER BY created_at ASC LIMIT 10",
                  (callback.from_user.id, last_post_id))
        posts = c.fetchall()

        if not posts:
            await callback.message.edit_text("Больше историй нет!", reply_markup=get_profile_menu())
            await callback.answer()
            return

        await state.update_data(last_post_id=posts[-1][0])
        for post in posts:
            post_id, title, content, status = post
            short_content = content[:100] + "..." if len(content) > 100 else content
            c.execute("SELECT username, content FROM comments WHERE post_id = ? ORDER BY created_at DESC LIMIT 3",
                      (post_id,))
            comments = c.fetchall()
            comments_text = "\n".join([f"@{c[0]}: {c[1]}" for c in comments]) if comments else "Нет комментариев"
            text = f"📝 {title}\n{short_content}\nКомментарии:\n{comments_text}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Читать дальше", callback_data=f"read_{post_id}"),
                 InlineKeyboardButton(text="Удалить", callback_data=f"delete_{post_id}")]
            ])
            await callback.message.answer(text, reply_markup=keyboard)

        c.execute("SELECT COUNT(*) FROM posts WHERE user_id = ? AND status = 'approved' AND post_id > ?",
                  (callback.from_user.id, posts[-1][0]))
        more_posts = c.fetchone()[0] > 0
        if more_posts:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Загрузить ещё", callback_data="load_more_my_posts")]
            ])
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        else:
            await callback.message.edit_reply_markup(reply_markup=get_profile_menu())
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("read_"))
    async def read_post(callback: types.CallbackQuery):
        try:
            post_id = int(callback.data.split("_")[1])
            c = conn.cursor()
            c.execute("SELECT title, content, image_id, is_compressed FROM posts WHERE post_id = ? AND user_id = ?",
                      (post_id, callback.from_user.id))
            post = c.fetchone()
            if post:
                title, content, image_id, is_compressed = post
                logger.info(f"read_post: post_id={post_id}, image_id={image_id}, is_compressed={is_compressed}")
                c.execute("SELECT username, content FROM comments WHERE post_id = ? ORDER BY created_at DESC LIMIT 5",
                          (post_id,))
                comments = c.fetchall()
                comments_text = "\n".join([f"@{c[0]}: {c[1]}" for c in comments]) if comments else "Нет комментариев"
                text = f"📝 {title}\n{content}\nКомментарии:\n{comments_text}"
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
                    if is_compressed:
                        logger.info(f"Отправка сжатого фото для post_id={post_id}, image_id={image_id}")
                        await bot.send_photo(callback.message.chat.id, image_id, caption=text, reply_markup=keyboard)
                    else:
                        logger.info(f"Отправка несжатого изображения для post_id={post_id}, image_id={image_id}")
                        await bot.send_document(callback.message.chat.id, image_id, caption=text, reply_markup=keyboard)
                    await callback.message.delete()
                else:
                    logger.info(f"Фото отсутствует для post_id={post_id}")
                    await callback.message.edit_text(text, reply_markup=keyboard)
            else:
                await callback.message.edit_text("Пост не найден или вы не являетесь его автором.")
            await callback.answer()
        except Exception as e:
            logger.error(f"Ошибка в read_post: {e}")
            await callback.answer("Ошибка при загрузке поста.")

    @dp.callback_query(lambda c: c.data.startswith("delete_"))
    async def delete_post(callback: types.CallbackQuery):
        try:
            post_id = int(callback.data.split("_")[1])
            c = conn.cursor()
            c.execute("SELECT user_id FROM posts WHERE post_id = ? AND status = 'approved'", (post_id,))
            result = c.fetchone()
            if result and result[0] == callback.from_user.id:
                c.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
                conn.commit()
                await callback.message.edit_text(callback.message.text + "\n🗑️ Пост удалён!")
                await callback.answer("История удалена!")
            else:
                await callback.answer("Вы не можете удалить эту историю!")
        except (IndexError, ValueError) as e:
            logger.error(f"Ошибка в delete_post: {e}")
            await callback.answer("Ошибка при удалении поста.")

    @dp.message(lambda message: message.text == "Назад")
    async def go_back(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        current_state = await state.get_state()
        if current_state is None:
            c.execute("SELECT is_admin FROM users WHERE user_id = ?", (message.from_user.id,))
            result = c.fetchone()
            is_admin = result[0] if result else False
            await message.answer("Вы вернулись в главное меню", reply_markup=get_main_menu(is_admin))
        else:
            c.execute("SELECT COUNT(*) FROM posts WHERE user_id = ? AND status IN ('pending', 'returned')",
                      (message.from_user.id,))
            has_pending = c.fetchone()[0] > 0
            await message.answer("Ваш профиль", reply_markup=get_profile_menu(has_pending))

    @dp.message(lambda message: message.text == "Добавить историю")
    async def add_post(message: types.Message, state: FSMContext):
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        c.execute("SELECT MAX(created_at) FROM posts WHERE user_id = ?", (message.from_user.id,))
        last_post = c.fetchone()[0]
        c.execute("SELECT value FROM settings WHERE key = 'post_delay'")
        delay = int(c.fetchone()[0]) * 60

        if last_post and (datetime.now() - datetime.fromisoformat(last_post)).total_seconds() < delay:
            await message.answer(f"Вы можете публиковать пост раз в {delay // 60} минут!")
            return

        await message.answer("Введите заголовок истории:")
        await state.set_state(ProfileStates.add_post_title)

    @dp.message(StateFilter(ProfileStates.add_post_title))
    async def process_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text)
        await message.answer("Введите текст истории:")
        await state.set_state(ProfileStates.add_post_content)

    @dp.message(StateFilter(ProfileStates.add_post_content))
    async def process_content(message: types.Message, state: FSMContext):
        await state.update_data(content=message.text)
        await message.answer(
            "Хотите прикрепить изображение?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        await state.set_state(ProfileStates.add_post_image)

    @dp.message(StateFilter(ProfileStates.add_post_image))
    async def process_image_choice(message: types.Message, state: FSMContext):
        if message.text and message.text.lower() == "нет":
            await save_post(message, state, None, False)
        elif message.text and message.text.lower() == "да":
            await message.answer(
                "Сжать изображение?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )
            await state.set_state(ProfileStates.add_post_compression)
        else:
            await message.answer(
                "Пожалуйста, выберите 'Да' или 'Нет':",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )

    @dp.message(StateFilter(ProfileStates.add_post_compression))
    async def process_compression(message: types.Message, state: FSMContext):
        if message.text and message.text.lower() in ["да", "нет"]:
            is_compressed = message.text.lower() == "да"
            await state.update_data(is_compressed=is_compressed)
            await message.answer("Отправьте изображение:")
            logger.info(f"Переход в состояние awaiting_photo для user_id={message.from_user.id}, is_compressed={is_compressed}")
            await state.set_state(ProfileStates.awaiting_photo)
        else:
            await message.answer(
                "Пожалуйста, выберите 'Да' или 'Нет':",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
            )

    @dp.message(StateFilter(ProfileStates.awaiting_photo))
    async def process_image(message: types.Message, state: FSMContext):
        logger.info(f"Обработка сообщения в состоянии awaiting_photo для user_id={message.from_user.id}")
        image_id = None
        data = await state.get_data()
        is_compressed = data.get('is_compressed', False)

        if message.photo and is_compressed:
            image_id = message.photo[-1].file_id
            logger.info(f"Получено сжатое фото: image_id={image_id}")
        elif message.document and not is_compressed:
            mime_type = message.document.mime_type
            if mime_type and mime_type.startswith('image/'):
                image_id = message.document.file_id
                logger.info(f"Получен несжатый файл-изображение: image_id={image_id}, mime_type={mime_type}")
            else:
                logger.warning(f"Получен документ, но это не изображение: mime_type={mime_type}")
                await message.answer("Пожалуйста, отправьте изображение (фото или файл с расширением .jpg, .png и т.д.).")
                return
        else:
            logger.warning(f"Несоответствие типа файла и настройки сжатия: content_type={message.content_type}, is_compressed={is_compressed}")
            await message.answer("Пожалуйста, отправьте изображение в соответствии с выбранным режимом сжатия.")
            return

        logger.info(f"Сохранение поста с image_id={image_id}, is_compressed={is_compressed}")
        await save_post(message, state, image_id, is_compressed)

    async def save_post(message: types.Message, state: FSMContext, image_id: str, is_compressed: bool):
        data = await state.get_data()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'moderation_enabled'")
        moderation = c.fetchone()[0] == '1'

        status = 'pending' if moderation else 'approved'
        c.execute("INSERT INTO posts (user_id, title, content, image_id, is_compressed, created_at, status) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (message.from_user.id, data['title'], data['content'], image_id,
                   1 if is_compressed else 0, datetime.now().isoformat(), status))
        conn.commit()
        post_id = c.lastrowid
        logger.info(f"Пост сохранён: post_id={post_id}, image_id={image_id}, is_compressed={is_compressed}")

        if not moderation:
            c.execute("UPDATE users SET posts_count = posts_count + 1 WHERE user_id = ?",
                      (message.from_user.id,))
            conn.commit()
            await message.answer("История успешно опубликована!", reply_markup=get_profile_menu())
        else:
            c.execute("SELECT user_id FROM users WHERE is_admin = 1")
            admins = c.fetchall()
            for admin in admins:
                await bot.send_message(admin[0], f"Новый пост на модерацию: {data['title']}")
            await message.answer("История отправлена на проверку!", reply_markup=get_profile_menu())
        await state.clear()

    @dp.message(lambda message: message.text == "Модерация")
    async def moderation_queue(message: types.Message):
        c = conn.cursor()
        c.execute("SELECT is_blocked FROM users WHERE user_id = ?", (message.from_user.id,))
        result = c.fetchone()
        if result and result[0]:
            await message.answer("Администрация StoryGram заблокировала вас.")
            return
        c.execute("SELECT post_id, title, content, status FROM posts WHERE user_id = ? "
                  "AND status IN ('pending', 'returned') ORDER BY created_at DESC", (message.from_user.id,))
        posts = c.fetchall()

        if not posts:
            await message.answer("Нет постов на модерации", reply_markup=get_profile_menu())
            return

        for post_id, title, content, status in posts:
            short_content = content[:100] + "..." if len(content) > 100 else content
            text = f"📝 {title}\n{short_content}\nСтатус: {'На проверке' if status == 'pending' else 'Возвращён на доработку'}"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Редактировать",
                                      callback_data=f"edit_{post_id}")] if status == 'returned' else []
            ])
            await message.answer(text, reply_markup=keyboard)

    @dp.callback_query(lambda c: c.data.startswith("edit_"))
    async def edit_post(callback: types.CallbackQuery, state: FSMContext):
        post_id = int(callback.data.split("_")[1])
        c = conn.cursor()
        c.execute("SELECT title, content FROM posts WHERE post_id = ? AND user_id = ? AND status = 'returned'",
                  (post_id, callback.from_user.id))
        post = c.fetchone()
        if post:
            await state.update_data(post_id=post_id, title=post[0], content=post[1])
            await callback.message.edit_text(f"Текущий заголовок: {post[0]}\nВведите новый заголовок:")
            await state.set_state(ProfileStates.add_post_title)
        await callback.answer()

    @dp.callback_query(lambda c: c.data.startswith("comment_"))
    async def comment_post(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"comment_post called with callback.data: {callback.data}")
        post_id = int(callback.data.split("_")[1])
        await state.update_data(post_id=post_id)
        await callback.message.reply("Введите ваш комментарий:", reply_markup=get_profile_menu())
        await state.set_state(ProfileStates.add_comment)
        await callback.answer()

    @dp.message(StateFilter(ProfileStates.add_comment))
    async def process_comment(message: types.Message, state: FSMContext):
        logger.info(f"process_comment called for user {message.from_user.id}")
        data = await state.get_data()
        post_id = data["post_id"]
        comment = message.text
        c = conn.cursor()
        c.execute("INSERT INTO comments (post_id, user_id, username, content, created_at) VALUES (?, ?, ?, ?, ?)",
                  (post_id, message.from_user.id, message.from_user.username, comment, datetime.now().isoformat()))
        conn.commit()
        await message.answer("Комментарий добавлен!", reply_markup=get_profile_menu())
        await state.clear()

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