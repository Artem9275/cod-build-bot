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
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 7083142762
ADMIN_IDS = [7083142762]

# JSONBIN (если не настроен - бот использует локальный файл data.json)
JSONBIN_API_KEY = "$2a$10$YToOVCHp5OUQNAy/9qZcE.NpzQ4.8Cxe0XD./KQeg7pU01mIzyDWG"
JSONBIN_BIN_ID = "6a16c58ef47d5c455c3c7925"

# Номер карты для доната
DONAT_CARD = "2202 2081 6256 1493"
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
# ФУНКЦИИ ДЛЯ КОММЕНТАРИЕВ
# =========================
def get_comment_author_id(comment_text):
    if "id:" in comment_text:
        try:
            return int(comment_text.split("id:")[1].split(")")[0])
        except:
            pass
    return None

def can_edit_comment(comment_text, user_id):
    if is_admin(user_id):
        return True
    author_id = get_comment_author_id(comment_text)
    return author_id == user_id

def can_delete_comment(comment_text, user_id):
    if is_admin(user_id):
        return True
    author_id = get_comment_author_id(comment_text)
    return author_id == user_id

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
            InlineKeyboardButton(f"💬 {comments}", callback_data=f"show_chat|{category}|{index}")
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
# ПОЛНОЦЕННЫЙ ЧАТ
# =========================
async def show_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, category, index, message_id=None):
    build = builds[category][index]
    comms = build.get("comments", [])
    
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    header = f"💬 *ЧАТ ОБСУЖДЕНИЯ*\n━━━━━━━━━━━━━━━\n📁 {category}\n📝 {build['description'][:50]}...\n👥 Сообщений: {len(comms)}\n━━━━━━━━━━━━━━━\n\n"
    
    if not comms:
        chat_text = header + "📭 Сообщений пока нет\n\nНапиши первый комментарий!"
    else:
        chat_text = header
        for i, comment in enumerate(comms[-15:], max(1, len(comms)-14)):
            chat_text += f"*#{i}* {comment}\n━━━━━━━━━━━━━━━\n"
    
    keyboard = [
        [InlineKeyboardButton("✍️ Написать", callback_data=f"write_msg|{category}|{index}"),
         InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_chat|{category}|{index}")],
        [InlineKeyboardButton("📜 Все сообщения", callback_data=f"full_chat|{category}|{index}"),
         InlineKeyboardButton("❌ Закрыть", callback_data="close_msg")]
    ]
    
    if is_admin(user_id):
        keyboard.insert(0, [InlineKeyboardButton("🗑 ОЧИСТИТЬ ЧАТ", callback_data=f"clear_chat|{category}|{index}")])
    
    if message_id:
        try:
            await context.bot.edit_message_text(text=chat_text, chat_id=update.effective_chat.id, message_id=message_id, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            pass
    else:
        if update.callback_query:
            await update.callback_query.message.reply_text(chat_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            await update.callback_query.answer()
        else:
            await update.message.reply_text(chat_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def full_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, category, index):
    query = update.callback_query
    build = builds[category][index]
    comms = build.get("comments", [])
    user_id = query.from_user.id
    
    if not comms:
        await query.message.reply_text("📭 Сообщений пока нет")
        await query.answer()
        return
    
    text = f"💬 *ВСЕ СООБЩЕНИЯ* ({len(comms)} шт.)\n━━━━━━━━━━━━━━━\n\n"
    for i, comment in enumerate(comms):
        text += f"*#{i+1}* {comment}\n━━━━━━━━━━━━━━━\n"
    
    keyboard = []
    for i in range(min(len(comms), 20)):
        keyboard.append([InlineKeyboardButton(f"💬 К #{i+1}", callback_data=f"select_msg|{category}|{index}|{i}")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад в чат", callback_data=f"back_to_chat|{category}|{index}")])
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close_msg")])
    
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()

async def select_message_action(update, context, category, index, comment_index):
    query = update.callback_query
    user_id = query.from_user.id
    build = builds[category][index]
    comms = build.get("comments", [])
    
    if comment_index >= len(comms):
        await query.answer("❌ Сообщение не найдено!")
        return
    
    comment = comms[comment_index]
    
    text = f"📝 *СООБЩЕНИЕ #{comment_index+1}*\n━━━━━━━━━━━━━━━\n\n{comment}"
    
    keyboard = []
    keyboard.append([InlineKeyboardButton("💬 Ответить", callback_data=f"reply_to_msg|{category}|{index}|{comment_index}")])
    
    if can_edit_comment(comment, user_id):
        keyboard.append([InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_msg|{category}|{index}|{comment_index}")])
    
    if can_delete_comment(comment, user_id):
        keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_msg|{category}|{index}|{comment_index}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_full_chat|{category}|{index}")])
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="close_msg")])
    
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()

async def write_message_start(update, context, category, index, reply_to=None):
    query = update.callback_query
    context.user_data["chat_data"] = {"category": category, "index": index, "reply_to": reply_to}
    context.user_data["state"] = "waiting_chat_message"
    
    if reply_to is not None:
        await query.message.reply_text(f"💬 *Ответ на сообщение #{reply_to+1}*\n\nНапиши свой ответ:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    else:
        await query.message.reply_text("💬 *Новое сообщение*\n\nНапиши свой комментарий:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    await query.answer()

async def save_chat_message(update, context):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    message_text = update.message.text
    
    if message_text == "/cancel":
        context.user_data.clear()
        await update.message.reply_text("❌ Отменено!", reply_markup=main_menu(user_id))
        return
    
    chat_data = context.user_data.get("chat_data")
    if not chat_data:
        context.user_data.clear()
        return
    
    category = chat_data["category"]
    index = chat_data["index"]
    reply_to = chat_data.get("reply_to")
    
    build = builds[category][index]
    author_id = build.get("author_id")
    
    if reply_to is not None:
        full_message = f"**{user_name}** (id:{user_id}) [в ответ на #{reply_to+1}]: {message_text}"
    else:
        full_message = f"**{user_name}** (id:{user_id}): {message_text}"
    
    builds[category][index]["comments"].append(full_message)
    save_data(builds)
    
    context.user_data.clear()
    await update.message.reply_text("✅ Сообщение отправлено!", reply_markup=main_menu(user_id))
    
    if author_id and author_id != user_id:
        await notify_author(context, author_id, f"💬 *{user_name}* написал в чат под твоей сборкой!\n\n💬 {message_text[:100]}...")
    
    if reply_to is not None and reply_to < len(builds[category][index]["comments"]) - 1:
        replied_msg = builds[category][index]["comments"][reply_to]
        replied_author_id = get_comment_author_id(replied_msg)
        if replied_author_id and replied_author_id != user_id and replied_author_id != author_id:
            await notify_author(context, replied_author_id, f"💬 *{user_name}* ответил на твой комментарий!\n\n💬 {message_text[:100]}...")

# =========================
# ОСНОВНЫЕ ФУНКЦИИ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = str(user.id)
    
    if user_id not in builds.get("users", {}):
        if "users" not in builds:
            builds["users"] = {}
        builds["users"][user_id] = {"name": user.first_name, "builds_count": 0, "join_date": datetime.now().isoformat(), "notifications": []}
        save_data(builds)
        await update.message.reply_text(f"🎉 *Добро пожаловать в CoD Build Bot, {user.first_name}!*\n\n🔥 Выбери действие в меню!", parse_mode="Markdown", reply_markup=main_menu(user.id))
    else:
        await update.message.reply_text(f"🔥 *С возвращением, {user.first_name}!*", parse_mode="Markdown", reply_markup=main_menu(user.id))

async def show_builds_in_category(update, context, category):
    builds_list = builds.get(category, [])
    user_id = update.message.from_user.id
    
    if not builds_list:
        keyboard = [[InlineKeyboardButton("➕ Добавить первую сборку", callback_data=f"add_build|{category}")]]
        await update.message.reply_text(f"😢 В разделе *{category}* пока нет сборок.\n\nСтань первым!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    sorted_builds = sorted(enumerate(builds_list), key=lambda x: x[1].get("likes", 0), reverse=True)
    await update.message.reply_text(f"📂 *{category}*\n📊 Всего сборок: {len(builds_list)}", parse_mode="Markdown")
    
    for idx, build in sorted_builds[:10]:
        text = f"⚙️ {build['description']}\n\n❤️ {build.get('likes', 0)} | 👎 {build.get('dislikes', 0)} | 💬 {len(build.get('comments', []))}"
        keyboard = build_buttons(category, idx, build, user_id)
        await update.message.reply_photo(photo=build["photo"], caption=text, parse_mode="Markdown", reply_markup=keyboard)

async def add_build_start(update, context):
    query = update.callback_query
    category = query.data.split("|")[1]
    context.user_data["temp_category"] = category
    context.user_data["state"] = "waiting_photo"
    await query.message.reply_text(f"📸 *Добавление сборки в:* {category}\n\nОтправь скриншот:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    await query.answer()

async def save_build_description(update, context):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    category = context.user_data.get("temp_category")
    photo = context.user_data.get("temp_photo")
    description = update.message.text
    
    if not category or not photo:
        await update.message.reply_text("❌ Ошибка! Попробуй заново.")
        context.user_data.clear()
        return
    
    new_build = {"photo": photo, "description": description, "likes": 0, "dislikes": 0, "liked_users": [], "disliked_users": [], "comments": [], "author_id": user_id, "author_name": user_name, "created_at": datetime.now().isoformat()}
    builds[category].append(new_build)
    save_data(builds)
    context.user_data.clear()
    
    await update.message.reply_text(f"✅ *Сборка добавлена!*\n\n📁 {category}\n⚙️ {description}", parse_mode="Markdown", reply_markup=main_menu(user_id))
    
    index = len(builds[category]) - 1
    keyboard = build_buttons(category, index, new_build, user_id)
    await update.message.reply_photo(photo=photo, caption=f"⚙️ {description}", parse_mode="Markdown", reply_markup=keyboard)

async def show_top_builds(update, context):
    all_builds = []
    for category, builds_list in builds.items():
        if category in ["users", "news", "tips"]:
            continue
        for idx, build in enumerate(builds_list):
            all_builds.append((category, idx, build, build.get("likes", 0)))
    all_builds.sort(key=lambda x: x[3], reverse=True)
    top10 = all_builds[:10]
    
    if not top10:
        await update.message.reply_text("😢 Пока нет сборок")
        return
    
    text = "🏆 *ТОП-10 СБОРОК* 🏆\n━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, (category, idx, build, likes) in enumerate(top10):
        text += f"{medals[i]} *{category}*\n📝 {build['description'][:80]}...\n❤️ {likes}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def random_build(update, context):
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

async def show_news(update, context):
    news_list = builds.get("news", [])
    text = "📰 *НОВОСТИ МЕТЫ*\n━━━━━━━━━━━━━━━\n\n"
    for i, news in enumerate(news_list[-5:], 1):
        text += f"{i}. {news}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def show_tips(update, context):
    tips_list = builds.get("tips", [])
    tip = random.choice(tips_list) if tips_list else "Скоро добавим советы!"
    await update.message.reply_text(f"🎯 *СОВЕТ ДНЯ*\n━━━━━━━━━━━━━━━\n\n{tip}", parse_mode="Markdown")

async def help_menu(update, context):
    help_text = """
🤖 *ПОМОЩЬ ПО БОТУ*
━━━━━━━━━━━━━━━

📌 *КАК ДОБАВИТЬ СБОРКУ:*
1️⃣ Нажми *🔫 Оружие*
2️⃣ Выбери категорию
3️⃣ Нажми *➕ Добавить сборку*
4️⃣ Отправь скриншот
5️⃣ Напиши описание

✨ *ЧТО МОЖНО ДЕЛАТЬ:*
• 👍/👎 - оценивать
• 💬 - комментировать
• ⭐ - избранное
• 🔔 - уведомления

⚡ *Совет:* Чем подробнее описание, тем больше лайков!
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def show_profile(update, context):
    user_id = str(update.message.from_user.id)
    user_name = update.message.from_user.first_name
    user_data = builds.get("users", {}).get(user_id, {})
    
    user_builds = 0
    for cat in builds:
        if cat not in ["users", "news", "tips"]:
            for b in builds[cat]:
                if b.get("author_id") == user_id:
                    user_builds += 1
    
    await update.message.repl
