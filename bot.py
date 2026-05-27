import json
import os
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
# ТОКЕН БОТА
# ВНИМАНИЕ: Обязательно смени токен в BotFather, так как старый скомпрометирован!
# =========================
TOKEN = os.environ.get("BOT_TOKEN")
# =========================
# БАЗА СБОРОК И ЕЁ СОХРАНЕНИЕ
# =========================
DATA_FILE = "builds_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Начальная пустая база, если файла ещё нет
    return {
        "🔥 Мета оружие": [],
        "🎯 Снайперские винтовки": [],
        "🔫 Штурмовые винтовки": [],
        "⚡ Пистолеты-пулеметы": [],
        "💣 Ручные пулеметы": [],
        "💥 Дробовики": []
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

builds = load_data()

# =========================
# ГЛАВНОЕ МЕНЮ
# =========================
def main_menu():
    keyboard = [
        ["🔥 Мета оружие"],
        ["🎯 Снайперские винтовки"],
        ["🔫 Штурмовые винтовки"],
        ["⚡ Пистолеты-пулеметы"],
        ["💣 Ручные пулеметы"],
        ["💥 Дробовики"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =========================
# МЕНЮ КАТЕГОРИИ
# =========================
def category_menu():
    keyboard = [
        ["➕ Добавить сборку"],
        ["📂 Посмотреть сборки"],
        ["⬅️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =========================
# КНОПКИ ЛАЙКОВ И КОММЕНТОВ
# =========================
def build_buttons(category, index, likes, comments):
    keyboard = [
        [
            InlineKeyboardButton(f"❤️ {likes}", callback_data=f"like|{category}|{index}"),
            InlineKeyboardButton(f"💬 {comments}", callback_data=f"comment|{category}|{index}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # Полный сброс состояний юзера
    await update.message.reply_text(
        "🔥 Добро пожаловать в CoD Build Bot!\n\n"
        "Выбери раздел оружия для КБ:",
        reply_markup=main_menu()
    )

# =========================
# ОБРАБОТКА ТЕКСТА
# =========================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    categories = list(builds.keys())
    
    current_state = context.user_data.get("state")

    # =========================
    # ЖДЕМ ОПИСАНИЕ СБОРКИ
    # =========================
    if current_state == "waiting_description":
        category = context.user_data.get("temp_category")
        photo = context.user_data.get("temp_photo")

        if not category or not photo:
            context.user_data.clear()
            await update.message.reply_text("❌ Ошибка сессии. Выбери раздел заново.")
            return

        new_build = {
            "photo": photo,
            "description": text,
            "likes": 0,
            "liked_users": [], 
            "comments": []
        }
        builds[category].append(new_build)
        save_data(builds)

        index = len(builds[category]) - 1

        # Сбрасываем состояния
        context.user_data["state"] = None
        context.user_data["temp_photo"] = None

        await update.message.reply_photo(
            photo=photo,
            caption=f"🔥 *Новая сборка в разделе {category}*!\n\n{text}",
            parse_mode="Markdown",
            reply_markup=build_buttons(category, index, 0, 0)
        )

        await update.message.reply_text(
            "✅ Сборка успешно добавлена в базу!",
            reply_markup=category_menu()
        )
        return

    # =========================
    # ЖДЕМ КОММЕНТАРИЙ
    # =========================
    if current_state == "waiting_comment":
        category = context.user_data.get("comment_category")
        index = context.user_data.get("comment_index")

        if category is None or category not in builds or index >= len(builds[category]):
            context.user_data["state"] = None
            await update.message.reply_text("❌ Ошибка. Сборка не найдена.")
            return

        user_name = update.message.from_user.first_name
        full_comment = f"{user_name}: {text}"
        
        builds[category][index]["comments"].append(full_comment)
        save_data(builds)

        context.user_data["state"] = None

        await update.message.reply_text("✅ Комментарий добавлен!", reply_markup=category_menu())
        return

    # =========================
    # НАЗАД
    # =========================
    if text == "⬅️ Назад":
        context.user_data["state"] = None
        await update.message.reply_text(
            "🏠 Главное меню. Выбирай пушки:",
            reply_markup=main_menu()
        )
        return

    # =========================
    # ВЫБОР КАТЕГОРИИ
    # =========================
    if text in categories:
        context.user_data["temp_category"] = text
        context.user_data["state"] = None
        await update.message.reply_text(
            f"📂 Раздел: *{text}*\nВыбери действие ниже:",
            parse_mode="Markdown",
            reply_markup=category_menu()
        )
        return

    # =========================
    # ДОБАВИТЬ СБОРКУ
    # =========================
    if text == "➕ Добавить сборку":
        if "temp_category" not in context.user_data:
            await update.message.reply_text("❌ Сначала выбери раздел в главном меню!")
            return

        context.user_data["state"] = "waiting_photo"
        await update.message.reply_text("📸 Отправь скриншот своей сборки модулей из игры:")
        return

    # =========================
    # ПОКАЗАТЬ СБОРКИ
    # =========================
    if text == "📂 Посмотреть сборки":
        category = context.user_data.get("temp_category")
        if not category:
            await update.message.reply_text("❌ Сначала выбери раздел")
            return

        category_builds = builds[category]
        if not category_builds:
            await update.message.reply_text("😢 В этом разделе пока нет сборок. Будь первым!")
            return

        await update.message.reply_text(f"📦 Загружаю кастомы для раздела: {category}...")

        for index, build in enumerate(category_builds):
            keyboard = build_buttons(
                category,
                index,
                build["likes"],
                len(build["comments"])
            )

            comments_text = ""
            if build["comments"]:
                comments_text = "\n\n💬 *Комментарии игроков:*\n"
                for comment in build["comments"][-5:]:
                    comments_text += f"\n• {comment}"

            await update.message.reply_photo(
                photo=build["photo"],
                caption=(
                    f"⚙️ *Описание модулей:*\n{build['description']}"
                    f"{comments_text}"
                ),
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        return

# =========================
# ОБРАБОТКА ФОТО
# =========================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if context.user_data.get("state") != "waiting_photo":
        return

    if not update.message.photo:
        await update.message.reply_text("❌ Отправь именно фотографию (скриншот)")
        return

    photo = update.message.photo[-1].file_id
    context.user_data["temp_photo"] = photo
    context.user_data["state"] = "waiting_description"
    
    await update.message.reply_text("✍️ Отлично! Теперь напиши описание модулей (какие перки, стволы и приклады стоят):")

# =========================
# ОБРАБОТКА ИНЛАЙН КНОПОК
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    parts = query.data.split("|")

    action = parts[0]
    category = parts[1]
    index = int(parts[2])

    if category not in builds or index >= len(builds[category]):
        return

    build = builds[category][index]

    if "liked_users" not in build:
        build["liked_users"] = []

    # =========================
    # ЛАЙК
    # =========================
    if action == "like":
        if user_id in build["liked_users"]:
            build["likes"] -= 1
            build["liked_users"].remove(user_id)
        else:
            build["likes"] += 1
            build["liked_users"].append(user_id)

        save_data(builds)

        keyboard = build_buttons(
            category,
            index,
            build["likes"],
            len(build["comments"])
        )

        await query.edit_message_reply_markup(reply_markup=keyboard)
        return

    # =========================
    # КОММЕНТ
    # =========================
    if action == "comment":
        context.user_data["state"] = "waiting_comment"
        context.user_data["comment_category"] = category
        context.user_data["comment_index"] = index

        await context.bot.send_message(
            chat_id=user_id,
            text=f"💬 Напиши свой комментарий для этой сборки и отправь его мне текстовым сообщением:"
        )
        return

# =========================
# ЗАПУСК БОТА
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Бот запущен на полную мощность! Данные застрахованы. 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()
