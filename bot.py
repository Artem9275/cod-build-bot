import json
import os
import urllib.request
import logging
import random
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)

# =========================
# НАСТРОЙКИ ЛОГИРОВАНИЯ
# =========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== 🙏 ЗАПОЛНИ ЭТИ ПОЛЯ 🙏 ====================
# 1. ТОКЕН БОТА (получить у @BotFather)
TOKEN = os.environ.get("BOT_TOKEN")  # ← ТВОЙ ТОКЕН (уже есть)

# 2. ТВОЙ TELEGRAM ID (узнать у @userinfobot)
ADMIN_ID = 7083142762  # ← ТВОЙ ID (уже есть)
ADMIN_IDS = [7083142762]  # ← ТВОЙ ID (уже есть)

# 3. ОБЛАЧНАЯ БАЗА JSONBIN (зарегистрироваться на jsonbin.io)
JSONBIN_API_KEY = "$2a$10$YToOVCHp5OUQNAy/9qZcE.NpzQ4.8Cxe0XD./KQeg7pU01mIzyDWG"  # ← ВСТАВЬ СВОЙ API КЛЮЧ
JSONBIN_BIN_ID = "6a16c58ef47d5c455c3c7925"        # ← ВСТАВЬ СВОЙ BIN ID

# 4. НОМЕР КАРТЫ ДЛЯ ДОНАТА (Сбербанк)
DONAT_CARD = "2202 2081 6256 1493"  # ← ВСТАВЬ НОМЕР КАРТЫ
# ================================================================

def is_admin(user_id):
    return user_id in ADMIN_IDS

# =========================
# РАБОТА С БАЗОЙ ДАННЫХ
# =========================
def get_empty_db():
    return {
        "🔥 Мета оружие": [],
        "🎯 Снайперские винтовки": [],
        "🔫 Штурмовые винтовки": [],
        "⚡ Пистолеты-пулеметы": [],
        "💣 Ручные пулеметы": [],
        "💥 Дробовики": [],
        "users": {},
        "news": [
            "🎮 Добро пожаловать в CoD Build Bot!",
            "🔥 Добавляй свои сборки и получай лайки!",
            "📊 Мета постоянно обновляется"
        ],
        "tips": [
            "🎯 Используй глушитель на штурмовых винтовках",
            "💨 Пистолеты-пулеметы лучше на коротких дистанциях",
            "🔭 Снайперка + тактический прицел = отлично"
        ]
    }

def load_data():
    if JSONBIN_API_KEY == "СЮДА_ВСТАВЬ_ДЛИННЫЙ_КЛЮЧ" or not JSONBIN_BIN_ID:
        if os.path.exists("data.json"):
            with open("data.json", "r", encoding='utf-8') as f:
                return json.load(f)
        return get_empty_db()
    
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('record', get_empty_db())
    except:
        if os.path.exists("data.json"):
            with open("data.json", "r", encoding='utf-8') as f:
                return json.load(f)
        return get_empty_db()

def save_data(data):
    with open("data.json", "w", encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    if JSONBIN_API_KEY != "СЮДА_ВСТАВЬ_ДЛИННЫЙ_КЛЮЧ" and JSONBIN_BIN_ID:
        url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
        headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY}
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='PUT')
        try:
            urllib.request.urlopen(req)
        except:
            pass

builds = load_data()

# =========================
# ФУНКЦИИ ДЛЯ КОММЕНТАРИЕВ (С ПРАВАМИ ПОЛЬЗОВАТЕЛЕЙ)
# =========================
def can_edit_comment(comment_text, user_id):
    if is_admin(user_id):
        return True
    if "id:" in comment_text:
        try:
            author_id = int(comment_text.split("id:")[1].split(")")[0])
            return author_id == user_id
        except:
            pass
    return False

def can_delete_comment(comment_text, user_id):
    if is_admin(user_id):
        return True
    if "id:" in comment_text:
        try:
            author_id = int(comment_text.split("id:")[1].split(")")[0])
            return author_id == user_id
        except:
            pass
    return False

def get_author_id_from_build(build):
    return build.get("author_id")

# =========================
# УВЕДОМЛЕНИЯ
# =========================
async def notify_author(context, author_id, message):
    if author_id and author_id != ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=author_id, text=message, parse_mode="Markdown")
        except:
            pass

# =========================
# МЕНЮ
# =========================
def main_menu(user_id=None):
    keyboard = [
        ["🔫 Оружие", "🏆 Топ сборок", "⭐ Избранное"],
        ["👤 Профиль", "📊 Статистика", "🎲 Случайная сборка"],
        ["📰 Новости меты", "🎯 Советы дня", "🔔 Уведомления"],
        ["👥 Помощь", "☕ Поддержать"]
    ]
    if is_admin(user_id):
        keyboard.append(["👑 АДМИН-ПАНЕЛЬ"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def weapons_menu():
    keyboard = [
        ["🔥 Мета оружие", "🎯 Снайперские винтовки"],
        ["🔫 Штурмовые винтовки", "⚡ Пистолеты-пулеметы"],
        ["💣 Ручные пулеметы", "💥 Дробовики"],
        ["⬅️ Назад в меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_panel_menu():
    keyboard = [
        ["📰 Управление новостями", "💡 Управление советами"],
        ["📊 Статистика бота", "👥 Список пользователей"],
        ["🗑 Управление сборками", "🏅 Выдать достижение"],
        ["📤 Экспорт данных", "🔄 Очистить кэш"],
        ["⬅️ Назад в меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =========================
# КНОПКИ ДЛЯ СБОРОК
# =========================
def build_buttons(category, index, build, user_id=None):
    likes = build.get("likes", 0)
    dislikes = build.get("dislikes", 0)
    comments = len(build.get("comments", []))
    author_name = build.get("author_name", "Неизвестный")
    
    keyboard = [
        [
            InlineKeyboardButton(f"👍 {likes}", callback_data=f"like|{category}|{index}"),
            InlineKeyboardButton(f"👎 {dislikes}", callback_data=f"dislike|{category}|{index}"),
            InlineKeyboardButton(f"💬 {comments}", callback_data=f"comms|{category}|{index}")
        ],
        [InlineKeyboardButton(f"👤 Автор: {author_name[:15]}", callback_data=f"author_info|{category}|{index}")]
    ]
    
    if build.get("author_id") == user_id:
        keyboard.append([InlineKeyboardButton("🗑 Удалить мою сборку", callback_data=f"delete_my_build|{category}|{index}")])
    
    if is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("🗑 Удалить (админ)", callback_data=f"del_build|{category}|{index}"),
            InlineKeyboardButton("✏️ Стереть описание", callback_data=f"del_desc|{category}|{index}")
        ])
        keyboard.append([InlineKeyboardButton("🧹 Очистить комменты", callback_data=f"del_comms|{category}|{index}")])
    
    return InlineKeyboardMarkup(keyboard)

# =========================
# ОСНОВНЫЕ ФУНКЦИИ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = str(user.id)
    
    if user_id not in builds.get("users", {}):
        if "users" not in builds:
            builds["users"] = {}
        builds["users"][user_id] = {
            "name": user.first_name,
            "builds_count": 0,
            "join_date": datetime.now().isoformat(),
            "notifications": []
        }
        save_data(builds)
        
        await update.message.reply_text(
            f"🎉 *Добро пожаловать в CoD Build Bot, {user.first_name}!*\n\n"
            f"🤖 Здесь ты можешь:\n"
            f"• Добавлять свои сборки\n"
            f"• Оценивать чужие\n"
            f"• Общаться в комментариях\n\n"
            f"🔥 *Выбери действие в меню!*",
            parse_mode="Markdown",
            reply_markup=main_menu(user.id)
        )
    else:
        await update.message.reply_text(
            f"🔥 *С возвращением, {user.first_name}!*",
            parse_mode="Markdown",
            reply_markup=main_menu(user.id)
        )

async def show_top_builds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_builds = []
    for category, builds_list in builds.items():
        if category in ["users", "news", "tips"]:
            continue
        for idx, build in enumerate(builds_list):
            all_builds.append((category, idx, build, build.get("likes", 0)))
    
    all_builds.sort(key=lambda x: x[3], reverse=True)
    top10 = all_builds[:10]
    
    if not top10:
        await update.message.reply_text("😢 Пока нет сборок для рейтинга")
        return
    
    text = "🏆 *ТОП-10 ЛУЧШИХ СБОРОК* 🏆\n━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (category, idx, build, likes) in enumerate(top10):
        text += f"{medals[i]} *{category}*\n📝 {build['description'][:80]}...\n❤️ {likes} лайков\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def random_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_builds = []
    for category, builds_list in builds.items():
        if category in ["users", "news", "tips"]:
            continue
        for idx, build in enumerate(builds_list):
            all_builds.append((category, idx, build))
    
    if not all_builds:
        await update.message.reply_text("😢 Пока нет сборок")
        return
    
    category, idx, build = random.choice(all_builds)
    text = f"🎲 *СЛУЧАЙНАЯ СБОРКА*\n━━━━━━━━━━━━━━━\n*{category}*\n\n⚙️ {build['description']}\n\n❤️ {build.get('likes', 0)} лайков"
    
    keyboard = build_buttons(category, idx, build, update.message.from_user.id)
    await update.message.reply_photo(photo=build["photo"], caption=text, parse_mode="Markdown", reply_markup=keyboard)

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_list = builds.get("news", [])
    text = "📰 *НОВОСТИ МЕТЫ*\n━━━━━━━━━━━━━━━\n\n"
    for i, news in enumerate(news_list[-5:], 1):
        text += f"{i}. {news}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def show_tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tips_list = builds.get("tips", [])
    tip = random.choice(tips_list) if tips_list else "Скоро добавим советы!"
    text = f"🎯 *СОВЕТ ДНЯ*\n━━━━━━━━━━━━━━━\n\n{tip}"
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 *ПОМОЩЬ ПО БОТУ*
━━━━━━━━━━━━━━━

📌 *КАК ДОБАВИТЬ СБОРКУ:*
1️⃣ Выбери "🔫 Оружие" → категорию
2️⃣ Нажми "➕ Добавить сборку"
3️⃣ Отправь скриншот
4️⃣ Напиши описание

✨ *ВОЗМОЖНОСТИ:*
• 👍/👎 - оценка сборок
• 💬 - комментарии
• ⭐ - избранное
• 🏆 - топ сборок
• 🎲 - случайная сборка

❓ Вопросы: @CodBuild_Admin
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")

# =========================
# ОБРАБОТЧИК СООБЩЕНИЙ
# =========================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    
    # ДОНАТ
    if text == "☕ Поддержать":
        donate_msg = f"☕ *ПОДДЕРЖАТЬ ПРОЕКТ*\n━━━━━━━━━━━━━━━\n\n💳 Сбербанк: `{DONAT_CARD}`\n\n✨ Спасибо за поддержку! 🚀"
        await update.message.reply_text(donate_msg, parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    # УВЕДОМЛЕНИЯ
    if text == "🔔 Уведомления":
        user_data = builds.get("users", {}).get(str(user_id), {})
        notifs = user_data.get("notifications", [])
        if not notifs:
            await update.message.reply_text("🔔 У тебя пока нет уведомлений", reply_markup=main_menu(user_id))
            return
        notif_text = "🔔 *ТВОИ УВЕДОМЛЕНИЯ*\n━━━━━━━━━━━━━━━\n\n"
        for n in notifs[-10:]:
            notif_text += f"• {n}\n"
        await update.message.reply_text(notif_text, parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    # СТАТИСТИКА
    if text == "📊 Статистика":
        total_builds = sum(len(builds[cat]) for cat in builds if cat not in ["users", "news", "tips"])
        total_users = len(builds.get("users", {}))
        stats = f"📊 *СТАТИСТИКА*\n━━━━━━━━━━━━━━━\n\n📦 Сборок: {total_builds}\n👥 Пользователей: {total_users}"
        await update.message.reply_text(stats, parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    # ПРОФИЛЬ
    if text == "👤 Профиль":
        user_data = builds.get("users", {}).get(str(user_id), {})
        user_builds = 0
        for cat in builds:
            if cat not in ["users", "news", "tips"]:
                for b in builds[cat]:
                    if b.get("author_id") == user_id:
                        user_builds += 1
        profile = f"👤 *ПРОФИЛЬ*\n━━━━━━━━━━━━━━━\n\n📝 Имя: {user_name}\n📦 Сборок: {user_builds}\n📅 С нами: с {user_data.get('join_date', datetime.now().isoformat())[:10]}"
        await update.message.reply_text(profile, parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    # ИЗБРАННОЕ
    if text == "⭐ Избранное":
        await update.message.reply_text("⭐ *ИЗБРАННОЕ*\n━━━━━━━━━━━━━━━\n\nСкоро здесь будут твои любимые сборки!", parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    # ОРУЖИЕ
    if text == "🔫 Оружие":
        await update.message.reply_text("🔫 *Выбери категорию:*", parse_mode="Markdown", reply_markup=weapons_menu())
        return
    
    if text == "🏆 Топ сборок":
        await show_top_builds(update, context)
        await update.message.reply_text("🏠 *Главное меню*", parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    if text == "🎲 Случайная сборка":
        await random_build(update, context)
        return
    
    if text == "📰 Новости меты":
        await show_news(update, context)
        return
    
    if text == "🎯 Советы дня":
        await show_tips(update, context)
        return
    
    if text == "👥 Помощь":
        await help_menu(update, context)
        return
    
    if text == "⬅️ Назад в меню":
        await update.message.reply_text("🏠 *Главное меню*", parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    # АДМИН-ПАНЕЛЬ
    if text == "👑 АДМИН-ПАНЕЛЬ" and is_admin(user_id):
        await update.message.reply_text("👑 *АДМИН-ПАНЕЛЬ*", parse_mode="Markdown", reply_markup=admin_panel_menu())
        return
    
    # ВРЕМЕННЫЙ ОТВЕТ
    await update.message.reply_text("🔫 Выбери действие в меню!", reply_markup=main_menu(user_id))

# =========================
# ОБРАБОТЧИК ФОТО (ДЛЯ ДОБАВЛЕНИЯ СБОРОК)
# =========================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "waiting_photo":
        await update.message.reply_text("❌ Сначала выбери категорию и нажми '➕ Добавить сборку'!")
        return
    
    photo_file_id = update.message.photo[-1].file_id
    context.user_data["temp_photo"] = photo_file_id
    context.user_data["state"] = "waiting_description"
    await update.message.reply_text("✍️ Отлично! Теперь напиши описание модулей:")

# =========================
# ЗАПУСК
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("=" * 50)
    print("🚀 CoD Build Bot ЗАПУЩЕН!")
    print("=" * 50)
    app.run_polling()

if __name__ == "__main__":
    main()
