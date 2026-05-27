import json
import os
import urllib.request
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
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
# НАСТРОЙКИ БОТА И АДМИНА
# =========================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 7083142762

# =========================
# НАСТРОЙКИ ОБЛАЧНОЙ БАЗЫ JSONBIN
# =========================
JSONBIN_API_KEY = "$2a$10$YToOVCHp5OUQNAy/9qZcE.NpzQ4.8Cxe0XD./KQeg7pU01mIzyDWG"
JSONBIN_BIN_ID = "6a16c58ef47d5c455c3c7925"

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
        "💥 Дробовики": []
    }

def load_data():
    if JSONBIN_API_KEY == "СЮДА_ВСТАВЬ_ДЛИННЫЙ_КЛЮЧ" or not JSONBIN_BIN_ID:
        print("База не настроена! Бот будет работать без облака.")
        return get_empty_db()

    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    headers = {"X-Master-Key": JSONBIN_API_KEY}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('record', get_empty_db())
    except Exception as e:
        print("Ошибка загрузки из облака:", e)
        return get_empty_db()

def save_data(data):
    if JSONBIN_API_KEY == "СЮДА_ВСТАВЬ_ДЛИННЫЙ_КЛЮЧ":
        return
    url = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": JSONBIN_API_KEY
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='PUT')
    try:
        urllib.request.urlopen(req)
    except Exception as e:
        print("Ошибка сохранения в облако:", e)

builds = load_data()

# =========================
# МЕНЮ
# =========================
def main_menu():
    # Добавили кнопку для доната в самый низ главного меню
    keyboard = [
        ["🔥 Мета оружие"],
        ["🎯 Снайперские винтовки"],
        ["🔫 Штурмовые винтовки"],
        ["⚡ Пистолеты-пулеметы"],
        ["💣 Ручные пулеметы"],
        ["💥 Дробовики"],
        ["☕ Поддержать автора"] 
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def category_menu():
    keyboard = [
        ["➕ Добавить сборку"],
        ["📂 Посмотреть сборки"],
        ["⬅️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =========================
# КНОПКИ (С ПРОВЕРКОЙ НА АДМИНА)
# =========================
def build_buttons(category, index, likes, comments, user_id=None):
    keyboard = [
        [
            InlineKeyboardButton(f"❤️ {likes}", callback_data=f"like|{category}|{index}"),
            InlineKeyboardButton(f"💬 Читать/Писать ({comments})", callback_data=f"view_comms|{category}|{index}")
        ]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🗑 Удалить сборку", callback_data=f"del_build|{category}|{index}")])
        keyboard.append([
            InlineKeyboardButton("✏️ Стереть описание", callback_data=f"del_desc|{category}|{index}"),
            InlineKeyboardButton("🧹 Очистить комменты", callback_data=f"del_comms|{category}|{index}")
        ])
    return InlineKeyboardMarkup(keyboard)

# =========================
# СТАРТ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🔥 Добро пожаловать в CoD Build Bot!\n\nВыбери раздел оружия для КБ:",
        reply_markup=main_menu()
    )

# =========================
# ОБРАБОТКА ТЕКСТА И СОЗДАНИЕ СБОРОК
# =========================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text
    categories = list(builds.keys())
    current_state = context.user_data.get("state")
    user_id = update.message.from_user.id

    # Сброс состояния при случайном нажатии кнопок меню
    if current_state in ["waiting_comment", "waiting_description"]:
        if text in ["⬅️ Назад", "➕ Добавить сборку", "📂 Посмотреть сборки", "☕ Поддержать автора"] or text in categories:
            context.user_data["state"] = None
            current_state = None

    # --- КНОПКА ДОНАТА ---
    if text == "☕ Поддержать автора":
        context.user_data["state"] = None
        donate_msg = (
            "👋 Привет! Я создатель этого бота.\n\n"
            "Если тебе заходят наши меты для КБ и ты хочешь поддержать проект копеечкой на энергетик, "
            "можешь закинуть донат по реквизитам ниже. Любая поддержка помогает делать бота еще круче! 🚀\n\n"
            "💳 **Карта (Сбербанк/Тинькофф/и тд):**\n"
            "`2202 2081 6256 1493` (Тёма)\n\n"
            "Спасибо за поддержку, братишка! 🤝"
        )
        await update.message.reply_text(donate_msg, parse_mode="Markdown", reply_markup=main_menu())
        return

    if current_state == "waiting_description":
        category = context.user_data.get("temp_category")
        photo = context.user_data.get("temp_photo")
        if not category or not photo:
            context.user_data.clear()
            await update.message.reply_text("❌ Ошибка сессии. Выбери раздел заново.")
            return

        new_build = {"photo": photo, "description": text, "likes": 0, "liked_users": [], "comments": []}
        builds[category].append(new_build)
        save_data(builds)
        index = len(builds[category]) - 1
        context.user_data["state"] = None
        context.user_data["temp_photo"] = None

        await update.message.reply_photo(
            photo=photo, caption=f"⚙️ *Описание модулей:*\n{text}",
            parse_mode="Markdown", reply_markup=build_buttons(category, index, 0, 0, user_id)
        )
        await update.message.reply_text("✅ Сборка успешно добавлена в базу!", reply_markup=category_menu())
        return

    if current_state == "waiting_comment":
        category = context.user_data.get("comment_category")
        index = context.user_data.get("comment_index")
        if category is None or category not in builds or index >= len(builds[category]):
            context.user_data["state"] = None
            await update.message.reply_text("❌ Ошибка. Сборка не найдена.")
            return

        full_comment = f"{update.message.from_user.first_name}: {text}"
        builds[category][index]["comments"].append(full_comment)
        save_data(builds)
        context.user_data["state"] = None
        await update.message.reply_text("✅ Комментарий добавлен! Нажми 'Читать/Писать', чтобы увидеть его.", reply_markup=category_menu())
        return

    if text == "⬅️ Назад":
        context.user_data["state"] = None
        await update.message.reply_text("🏠 Главное меню. Выбирай пушки:", reply_markup=main_menu())
        return

    if text in categories:
        context.user_data["temp_category"] = text
        context.user_data["state"] = None
        await update.message.reply_text(f"📂 Раздел: *{text}*\nВыбери действие ниже:", parse_mode="Markdown", reply_markup=category_menu())
        return

    if text == "➕ Добавить сборку":
        if "temp_category" not in context.user_data:
            await update.message.reply_text("❌ Сначала выбери раздел в главном меню!")
            return
        context.user_data["state"] = "waiting_photo"
        await update.message.reply_text("📸 Отправь скриншот своей сборки модулей из игры:")
        return

    if text == "📂 Посмотреть сборки":
        category = context.user_data.get("temp_category")
        if not category:
            await update.message.reply_text("❌ Сначала выбери раздел")
            return
        if not builds[category]:
            await update.message.reply_text("😢 В этом разделе пока нет сборок. Будь первым!")
            return
        await update.message.reply_text(f"📦 Загружаю кастомы для раздела: {category}...")
        for index, build in enumerate(builds[category]):
            keyboard = build_buttons(category, index, build["likes"], len(build["comments"]), user_id)
            await update.message.reply_photo(
                photo=build["photo"], caption=f"⚙️ *Описание модулей:*\n{build['description']}",
                parse_mode="Markdown", reply_markup=keyboard
            )
        return

# =========================
# ОБРАБОТКА ФОТО
# =========================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or context.user_data.get("state") != "waiting_photo": return
    if not update.message.photo:
        await update.message.reply_text("❌ Отправь именно фотографию (скриншот)")
        return
    context.user_data["temp_photo"] = update.message.photo[-1].file_id
    context.user_data["state"] = "waiting_description"
    await update.message.reply_text("✍️ Отлично! Теперь напиши описание модулей:")

# =========================
# ИНЛАЙН КНОПКИ
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if query.data == "close_msg":
        try:
            await query.message.delete()
        except: pass
        return

    parts = query.data.split("|")
    if len(parts) < 3: return
    
    action, category, index = parts[0], parts[1], int(parts[2])

    if category not in builds or index >= len(builds[category]):
        await query.answer("❌ Сборка не найдена!", show_alert=True)
        try: await query.message.delete()
        except: pass
        return

    build = builds[category][index]
    if "liked_users" not in build: build["liked_users"] = []

    if action == "like":
        if user_id in build["liked_users"]:
            build["likes"] -= 1
            build["liked_users"].remove(user_id)
        else:
            build["likes"] += 1
            build["liked_users"].append(user_id)
        save_data(builds)
        await query.edit_message_reply_markup(reply_markup=build_buttons(category, index, build["likes"], len(build["comments"]), user_id))
        return

    if action == "view_comms":
        comms = build.get("comments", [])
        if not comms:
            text_comms = "📭 *Здесь пока нет комментариев.*\nНажми кнопку ниже, чтобы стать первым!"
        else:
            text_comms = "💬 *Комментарии игроков:*\n\n" + "\n".join([f"• {c}" for c in comms])
        
        keyboard = [
            [InlineKeyboardButton("✍️ Написать комментарий", callback_data=f"add_comm|{category}|{index}")],
            [InlineKeyboardButton("❌ Закрыть", callback_data="close_msg")]
        ]
        await query.message.reply_text(text=text_comms, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        await query.answer()
        return

    if action == "add_comm":
        context.user_data["state"] = "waiting_comment"
        context.user_data["comment_category"] = category
        context.user_data["comment_index"] = index
        await query.answer()
        await context.bot.send_message(chat_id=user_id, text=f"💬 Напиши свой комментарий текстом и отправь его мне:")
        return

    if action in ["del_build", "del_desc", "del_comms"]:
        if user_id != ADMIN_ID:
            await query.answer("❌ Доступ запрещен!", show_alert=True)
            return
        if action == "del_build":
            del builds[category][index]
            save_data(builds)
            await query.message.delete()
            await query.answer("✅ Сборка уничтожена!")
            return
        if action == "del_desc": builds[category][index]["description"] = "🚫 _Описание удалено._"
        if action == "del_comms": builds[category][index]["comments"] = []
        save_data(builds)
        
        await query.edit_message_caption(
            caption=f"⚙️ *Описание модулей:*\n{builds[category][index]['description']}",
            parse_mode="Markdown",
            reply_markup=build_buttons(category, index, build["likes"], len(build["comments"]), user_id)
        )
        if action == "del_desc": await query.answer("✅ Описание стерто!")
        elif action == "del_comms": await query.answer("✅ Комменты очищены!")
        return

# =========================
# ЗАПУСК
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Бот запущен! Кнопка доната добавлена. ☁️🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
                              
