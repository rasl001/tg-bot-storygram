# Telegram StoryGram Bot

---

## 🌟 English

Mini social network with user stories.
A Python-based Telegram bot for creating, sharing, and managing stories, built with **aiogram 3.x** and **SQLite**. 
This bot allows users to post stories with text and images, browse a paginated feed, manage their profile, and interact with content through likes and comments. 
It includes an admin panel for moderating posts and user management.

### 🚀 Features
- **Story Creation**: Post stories with text and optional images (compressed or uncompressed), with a configurable posting delay.
- **Paginated Feed**: Browse a feed of approved stories, loading 10 at a time with a "Load More" button.
- **Profile Management**: Edit your name and bio (once every 30 days), view your stories (also paginated), and see your rating based on posts and likes.
- **Interactions**: Like and comment on stories, with comments displayed in the feed and full post view.
- **Moderation**: Admin panel for approving or rejecting stories, plus user blocking functionality.
- **Database**: Uses SQLite to store users, posts, comments, reactions, and settings.

### 🛠️ Installation
1. Install the required package: `pip install aiogram`
2. Update `BOT_TOKEN` in `main.py` with your Telegram Bot Token from BotFather.
3. Ensure the bot has appropriate permissions in your Telegram chat (e.g., sending messages, managing content).
4. Run the bot: `python main.py`

### 📜 License
MIT License

---

## 🌟 Русский

Мини социальная сеть с историями пользователей.
Бот для Telegram на Python для создания, публикации и управления историями, построенный на **aiogram 3.x** и **SQLite**. 
Этот бот позволяет пользователям публиковать истории с текстом и изображениями, просматривать ленту с пагинацией, управлять своим профилем и взаимодействовать с контентом через лайки и комментарии. 
Включает админ-панель для модерации постов и управления пользователями.

### 🚀 Возможности
- **Создание историй**: Публикуйте истории с текстом и изображениями (сжатыми или несжатыми) с настраиваемой задержкой между постами.
- **Лента с пагинацией**: Просматривайте ленту одобренных историй, подгружая по 10 за раз с кнопкой "Загрузить ещё".
- **Управление профилем**: Редактируйте имя и информацию о себе (раз в 30 дней), просматривайте свои истории (тоже с пагинацией) и рейтинг на основе постов и лайков.
- **Взаимодействие**: Ставьте лайки и комментируйте истории, комментарии отображаются в ленте и в полном виде поста.
- **Модерация**: Админ-панель для одобрения или отклонения историй, а также блокировки пользователей.
- **База данных**: Использует SQLite для хранения пользователей, постов, комментариев, реакций и настроек.

### 🛠️ Установка
1. Установите необходимую библиотеку: `pip install aiogram`
2. Обновите `BOT_TOKEN` в файле `main.py` своим токеном от BotFather.
3. Убедитесь, что бот имеет нужные права в вашем Telegram-чате (например, отправка сообщений, управление контентом).
4. Запустите бота: `python main.py`

### 📜 Лицензия
Лицензия MIT
