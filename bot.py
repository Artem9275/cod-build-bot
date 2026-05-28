import json
import os
import random
import requests
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
# НАСТРОЙКИ
# =========================
# Токен берется из переменных окружения
TOKEN = os.environ.get("BOT_TOKEN") 
ADMIN_ID = 7083142762
ADMIN_IDS = [7083142762]
DONAT_CARD = "2202208162561493"

# =========================
# НАСТРОЙКИ JSONBIN
# =========================
JSONBIN_KEY = "$2a$10$YToOVCHp5OUQNAy/9qZcE.NpzQ4.8Cxe0XD./KQeg7pU01mIzyDWG"
BIN_ID = "6a16c58ef47d5c455c3c7925"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
JSONBIN_HEADERS = {
    "X-Master-Key": JSONBIN_KEY,
    "Content-Type": "application/json"
}

def is_admin(user_id):
    return user_id in ADMIN_IDS

# =========================
# БАЗА ДАННЫХ
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
        "news": ["🎮 Добро пожаловать в CoD Build Bot!"],
        "tips": ["🎯 Используй глушитель на штурмовых винтовках"]
    }

def load_data():
    try:
        response = requests.get(JSONBIN_URL, headers=JSONBIN_HEADERS)
        if response.status_code == 200:
            return response.json().get('record', get_empty_db())
        else:
            print(f"Ошибка загрузки БД: {response.status_code}")
    except Exception as e:
        print(f"Ошибка соединения с JSONBin: {e}")
    
    return get_empty_db()

def save_data(data):
    try:
        response = requests.put(JSONBIN_URL, json=data, headers=JSONBIN_HEADERS)
        if response.status_code != 200:
            print(f"Ошибка сохранения БД: {response.text}")
    except Exception as e:
        print(f"Ошибка при сохранении в JSONBin: {e}")

builds = load_data()

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
        ["📰 Новости меты", "🎯 Советы дня", "👥 Помощь"],
        ["☕ Поддержать"]
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
        ["🗑 Управление сборками", "🔄 Очистить кэш"],
        ["⬅️ Назад в меню"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =========================
# КНОПКИ ДЛЯ СБОРОК
# =========================
def build_buttons(category, index, build, user_id=None):
    likes = build.get("likes", 0)
    dislikes = build.get("dislikes", 0)
    
    keyboard = [
        [
            InlineKeyboardButton(f"👍 {likes}", callback_data=f"like|{category}|{index}"),
            InlineKeyboardButton(f"👎 {dislikes}", callback_data=f"dislike|{category}|{index}"),
            InlineKeyboardButton(f"💬 Комментарии", callback_data=f"comments|{category}|{index}")
        ]
    ]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"del_build|{category}|{index}")])
    
    return InlineKeyboardMarkup(keyboard)

# =========================
# ОСНОВНЫЕ ФУНКЦИИ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = str(user.id)
    
    if user_id not in builds.get("users", {}):
        builds["users"][user_id] = {"name": user.first_name, "join_date": datetime.now().isoformat()}
        save_data(builds)
    
    await update.message.reply_text(
        f"🔥 *Добро пожаловать, {user.first_name}!*\n\nВыбери действие:",
        parse_mode="Markdown",
        reply_markup=main_menu(user.id)
    )

async def show_builds_in_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category):
    builds_list = builds.get(category, [])
    user_id = update.message.from_user.id
    
    if not builds_list:
        keyboard = [[InlineKeyboardButton("➕ Добавить первую сборку", callback_data=f"add_build|{category}")]]
        await update.message.reply_text(
            f"😢 В разделе *{category}* пока нет сборок.\n\nСтань первым!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    await update.message.reply_text(f"📂 *{category}* - {len(builds_list)} сборок", parse_mode="Markdown")
    
    for idx, build in enumerate(builds_list):
        text = f"⚙️ {build['description']}\n\n❤️ {build.get('likes', 0)} | 👎 {build.get('dislikes', 0)}"
        keyboard = build_buttons(category, idx, build, user_id)
        await update.message.reply_photo(
            photo=build["photo"],
            caption=text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

async def add_build_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    category = query.data.split("|")[1]
    context.user_data["temp_category"] = category
    context.user_data["state"] = "waiting_photo"
    await query.message.reply_text(
        "📸 Отправь скриншот своей сборки:",
        reply_markup=ReplyKeyboardRemove()
    )
    await query.answer()

async def save_build_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    category = context.user_data.get("temp_category")
    photo = context.user_data.get("temp_photo")
    description = update.message.text
    
    if not category or not photo:
        await update.message.reply_text("❌ Ошибка! Попробуй заново.")
        context.user_data.clear()
        return
    
    new_build = {
        "photo": photo,
        "description": description,
        "likes": 0,
        "dislikes": 0,
        "liked_users": [],
        "disliked_users": [],
        "comments": [],
        "author_id": user_id,
        "author_name": user_name,
        "created_at": datetime.now().isoformat()
    }
    builds[category].append(new_build)
    save_data(builds)
    context.user_data.clear()
    
    await update.message.reply_text(
        f"✅ Сборка добавлена!",
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "waiting_photo":
        await update.message.reply_text("❌ Сначала выбери категорию и нажми '➕ Добавить сборку'!")
        return
    
    context.user_data["temp_photo"] = update.message.photo[-1].file_id
    context.user_data["state"] = "waiting_description"
    await update.message.reply_text("✍️ Теперь напиши описание модулей:")

async def show_comments(update: Update, context: ContextTypes.DEFAULT_TYPE, category, index):
    query = update.callback_query
    build = builds[category][index]
    comms = build.get("comments", [])
    
    if not comms:
        text = "💬 *Комментариев пока нет*\n\nНапиши первый!"
    else:
        text = "💬 *Комментарии:*\n━━━━━━━━━━━━━━━\n\n"
        for i, c in enumerate(comms[-10:], 1):
            text += f"{i}. {c}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("✍️ Написать", callback_data=f"write_comment|{category}|{index}")],
        [InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_comments|{category}|{index}")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close_msg")]
    ]
    
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    await query.answer()

async def write_comment_start(update: Update, context: ContextTypes.DEFAULT_TYPE, category, index):
    query = update.callback_query
    context.user_data["comment_data"] = {"category": category, "index": index}
    context.user_data["state"] = "waiting_comment"
    await query.message.reply_text("💬 Напиши свой комментарий:", reply_markup=ReplyKeyboardRemove())
    await query.answer()

async def save_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name
    comment_text = update.message.text
    
    comment_data = context.user_data.get("comment_data")
    if not comment_data:
        context.user_data.clear()
        return
    
    category = comment_data["category"]
    index = comment_data["index"]
    
    build = builds[category][index]
    author_id = build.get("author_id")
    
    full_comment = f"*{user_name}* (id:{user_id}): {comment_text}"
    builds[category][index]["comments"].append(full_comment)
    save_data(builds)
    
    context.user_data.clear()
    await update.message.reply_text("✅ Комментарий добавлен!", reply_markup=main_menu(user_id))
    
    if author_id and author_id != user_id:
        await notify_author(context, author_id, f"💬 *{user_name}* оставил комментарий под твоей сборкой!\n\n💬 {comment_text[:100]}...")

async def show_top_builds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_builds = []
    for category, builds_list in builds.items():
        if category in ["users", "news", "tips"]:
            continue
        for build in builds_list:
            all_builds.append((category, build, build.get("likes", 0)))
    all_builds.sort(key=lambda x: x[2], reverse=True)
    top5 = all_builds[:5]
    
    if not top5:
        await update.message.reply_text("😢 Пока нет сборок")
        return
    
    text = "🏆 *ТОП-5 СБОРОК*\n━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, (category, build, likes) in enumerate(top5):
        text += f"{medals[i]} *{category}*\n📝 {build['description'][:80]}...\n❤️ {likes}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def random_build(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_builds = []
    for category, builds_list in builds.items():
        if category in ["users", "news", "tips"]:
            continue
        for build in builds_list:
            all_builds.append((category, build))
    
    if not all_builds:
        await update.message.reply_text("😢 Пока нет сборок")
        return
    
    category, build = random.choice(all_builds)
    await update.message.reply_text(
        f"🎲 *СЛУЧАЙНАЯ СБОРКА*\n━━━━━━━━━━━━━━━\n*{category}*\n\n⚙️ {build['description']}\n\n❤️ {build.get('likes', 0)} лайков",
        parse_mode="Markdown"
    )

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_list = builds.get("news", [])
    text = "📰 *НОВОСТИ*\n━━━━━━━━━━━━━━━\n\n"
    for i, news in enumerate(news_list[-5:], 1):
        text += f"{i}. {news}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def show_tips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tips_list = builds.get("tips", [])
    tip = random.choice(tips_list) if tips_list else "Скоро добавим советы!"
    await update.message.reply_text(f"🎯 *СОВЕТ ДНЯ*\n━━━━━━━━━━━━━━━\n\n{tip}", parse_mode="Markdown")

async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
🤖 *ПОМОЩЬ*
━━━━━━━━━━━━━━━

📌 *КАК ДОБАВИТЬ СБОРКУ:*
1️⃣ Нажми 🔫 Оружие
2️⃣ Выбери категорию
3️⃣ Нажми ➕ Добавить сборку
4️⃣ Отправь скриншот
5️⃣ Напиши описание

✨ *ЧТО МОЖНО ДЕЛАТЬ:*
• 👍/👎 - оценивать сборки
• 💬 - комментировать
• 🔔 - уведомления (приходят автоматически)
    """, parse_mode="Markdown")

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_name = update.message.from_user.first_name
    
    user_builds = 0
    for cat in builds:
        if cat not in ["users", "news", "tips"]:
            for b in builds[cat]:
                if b.get("author_id") == user_id:
                    user_builds += 1
    
    await update.message.reply_text(
        f"👤 *ПРОФИЛЬ*\n━━━━━━━━━━━━━━━\n\n📝 {user_name}\n📦 Сборок: {user_builds}",
        parse_mode="Markdown"
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_builds = sum(len(builds[cat]) for cat in builds if cat not in ["users", "news", "tips"])
    total_users = len(builds.get("users", {}))
    await update.message.reply_text(
        f"📊 *СТАТИСТИКА*\n━━━━━━━━━━━━━━━\n\n📦 Сборок: {total_builds}\n👥 Пользователей: {total_users}",
        parse_mode="Markdown"
    )

# =========================
# ОБРАБОТЧИК СООБЩЕНИЙ
# =========================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    user_id = update.message.from_user.id
    categories = ["🔥 Мета оружие", "🎯 Снайперские винтовки", "🔫 Штурмовые винтовки", 
                  "⚡ Пистолеты-пулеметы", "💣 Ручные пулеметы", "💥 Дробовики"]
    
    if context.user_data.get("state") == "waiting_description":
        await save_build_description(update, context)
        return
    
    if context.user_data.get("state") == "waiting_comment":
        await save_comment(update, context)
        return
    
    if text == "🔫 Оружие":
        await update.message.reply_text("🔫 *Выбери категорию:*", parse_mode="Markdown", reply_markup=weapons_menu())
        return
    
    if text in categories:
        context.user_data["temp_category"] = text
        await show_builds_in_category(update, context, text)
        return
    
    if text == "⬅️ Назад в меню":
        await update.message.reply_text("🏠 *Главное меню*", parse_mode="Markdown", reply_markup=main_menu(user_id))
        return
    
    if text == "🏆 Топ сборок":
        await show_top_builds(update, context)
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
    if text == "👤 Профиль":
        await show_profile(update, context)
        return
    if text == "📊 Статистика":
        await show_stats(update, context)
        return
    if text == "⭐ Избранное":
        await update.message.reply_text("⭐ *ИЗБРАННОЕ*\n\nСкоро здесь будут твои любимые сборки!", parse_mode="Markdown")
        return
    if text == "☕ Поддержать":
        await update.message.reply_text(f"☕ *ПОДДЕРЖАТЬ*\n━━━━━━━━━━━━━━━\n\n💳 Сбербанк: `{DONAT_CARD}`", parse_mode="Markdown")
        return
    
    if text == "👑 АДМИН-ПАНЕЛЬ" and is_admin(user_id):
        await update.message.reply_text("👑 *АДМИН-ПАНЕЛЬ*", parse_mode="Markdown", reply_markup=admin_panel_menu())
        return
    
    await update.message.reply_text("🔫 Выбери действие в меню!", reply_markup=main_menu(user_id))

# =========================
# ОБРАБОТЧИК КНОПОК
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    data = query.data
    
    if data == "close_msg":
        try:
            await query.message.delete()
        except:
            pass
        return
    
    # Добавление сборки
    if data.startswith("add_build|"):
        await add_build_start(update, context)
        return
    
    # Комментарии
    if data.startswith("comments|"):
        parts = data.split("|")
        category, index = parts[1], int(parts[2])
        await show_comments(update, context, category, index)
        return
    
    if data.startswith("refresh_comments|"):
        parts = data.split("|")
        category, index = parts[1], int(parts[2])
        await show_comments(update, context, category, index)
        return
    
    if data.startswith("write_comment|"):
        parts = data.split("|")
        category, index = parts[1], int(parts[2])
        await write_comment_start(update, context, category, index)
        return
    
    # Лайк
    if data.startswith("like|"):
        parts = data.split("|")
        category, index = parts[1], int(parts[2])
        build = builds[category][index]
        author_id = build.get("author_id")
        
        if user_id == author_id:
            await query.answer("❌ Нельзя лайкать свою сборку!", show_alert=True)
            return
        
        if "liked_users" not in build:
            build["liked_users"] = []
        if "disliked_users" not in build:
            build["disliked_users"] = []
        
        if user_id in build["disliked_users"]:
            build["disliked_users"].remove(user_id)
            build["dislikes"] = build.get("dislikes", 0) - 1
        
        if user_id in build["liked_users"]:
            build["liked_users"].remove(user_id)
            build["likes"] = build.get("likes", 0) - 1
            action = "🔴 Убрал лайк"
            notif = None
        else:
            build["liked_users"].append(user_id)
            build["likes"] = build.get("likes", 0) + 1
            action = "👍 Поставил лайк"
            notif = f"👍 *{user_name}* лайкнул твою сборку!"
        
        save_data(builds)
        if notif and author_id and author_id != user_id:
            await notify_author(context, author_id, notif)
        
        keyboard = build_buttons(category, index, build, user_id)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        await query.answer(action)
        return
    
    # Дизлайк
    if data.startswith("dislike|"):
        parts = data.split("|")
        category, index = parts[1], int(parts[2])
        build = builds[category][index]
        author_id = build.get("author_id")
        
        if user_id == author_id:
            await query.answer("❌ Нельзя дизлайкать свою сборку!", show_alert=True)
            return
        
        if "disliked_users" not in build:
            build["disliked_users"] = []
        if "liked_users" not in build:
            build["liked_users"] = []
        
        if user_id in build["liked_users"]:
            build["liked_users"].remove(user_id)
            build["likes"] = build.get("likes", 0) - 1
        
        if user_id in build["disliked_users"]:
            build["disliked_users"].remove(user_id)
            build["dislikes"] = build.get("dislikes", 0) - 1
            action = "🟢 Убрал дизлайк"
            notif = None
        else:
            build["disliked_users"].append(user_id)
            build["dislikes"] = build.get("dislikes", 0) + 1
            action = "👎 Поставил дизлайк"
            notif = f"👎 *{user_name}* дизлайкнул твою сборку!"
        
        save_data(builds)
        if notif and author_id and author_id != user_id:
            await notify_author(context, author_id, notif)
        
        keyboard = build_buttons(category, index, build, user_id)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        await query.answer(action)
        return
    
    # Удаление сборки (админ)
    if data.startswith("del_build|") and is_admin(user_id):
        parts = data.split("|")
        category, index = parts[1], int(parts[2])
        del builds[category][index]
        save_data(builds)
        await query.message.delete()
        await query.answer("✅ Сборка удалена!")
        return

# =========================
# ЗАПУСК
# =========================
def main():
    if not TOKEN:
        print("❌ ОШИБКА: Токен бота не найден. Убедись, что переменная BOT_TOKEN задана в окружении.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущен! Ожидание сообщений...")
    app.run_polling()

if __name__ == "__main__":
    main()
    
