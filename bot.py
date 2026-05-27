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
# =========================
TOKEN="8912189908:AAHRiflwZb6ZCL1pOQXoXQ-aY3QF1YtIzsQ"


# =========================
# СОСТОЯНИЯ
# =========================
user_state = {}
temp_photo = {}
temp_category = {}

# =========================
# БАЗА СБОРОК
# =========================
builds = {
    "🔥 Мета оружие": [],
    "🎯 Снайперские винтовки": [],
    "🔫 Штурмовые винтовки": [],
    "⚡ Пистолеты-пулеметы": [],
    "💣 Ручные пулеметы": [],
    "💥 Дробовики": []
}


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

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =========================
# МЕНЮ КАТЕГОРИИ
# =========================
def category_menu():

    keyboard = [
        ["➕ Добавить сборку"],
        ["📂 Посмотреть сборки"],
        ["⬅️ Назад"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# =========================
# КНОПКИ ЛАЙКОВ И КОММЕНТОВ
# =========================
def build_buttons(category, index, likes, comments):

    keyboard = [
        [
            InlineKeyboardButton(
                f"❤️ {likes}",
                callback_data=f"like|{category}|{index}"
            ),

            InlineKeyboardButton(
                f"💬 {comments}",
                callback_data=f"comment|{category}|{index}"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🔥 Добро пожаловать в CoD Build Bot!\n\n"
        "Выбери раздел:",
        reply_markup=main_menu()
    )


# =========================
# ОБРАБОТКА ТЕКСТА
# =========================
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    user_id = update.message.from_user.id
    text = update.message.text

    if text is None:
        return

    categories = list(builds.keys())

    # =========================
    # ЖДЕМ ОПИСАНИЕ
    # =========================
    if user_state.get(user_id) == "waiting_description":

        category = temp_category.get(user_id)
        photo = temp_photo.get(user_id)

        if not category or not photo:

            user_state[user_id] = None
            temp_photo[user_id] = None

            await update.message.reply_text(
                "❌ Ошибка. Попробуй снова."
            )

            return

        # СОХРАНЯЕМ СБОРКУ
        builds[category].append({
            "photo": photo,
            "description": text,
            "likes": 0,
            "comments": []
        })

        # СБРАСЫВАЕМ СОСТОЯНИЯ
        user_state[user_id] = None
        temp_photo[user_id] = None

        # ПОКАЗЫВАЕМ СБОРКУ
        await update.message.reply_photo(
            photo=photo,
            caption=f"🔥 Новая сборка\n\n{text}"
        )

        # СООБЩЕНИЕ ОБ УСПЕХЕ
        await update.message.reply_text(
            "✅ Сборка успешно добавлена!",
            reply_markup=category_menu()
        )

        return

    # =========================
    # ЖДЕМ КОММЕНТАРИЙ
    # =========================
    if user_state.get(user_id) == "waiting_comment":

        category = context.user_data.get("comment_category")
        index = context.user_data.get("comment_index")

        if category is None:
            return

        builds[category][index]["comments"].append(text)

        user_state[user_id] = None

        await update.message.reply_text(
            "✅ Комментарий добавлен!"
        )

        return

    # =========================
    # ВЫБОР КАТЕГОРИИ
    # =========================
    if text in categories:

        temp_category[user_id] = text

        await update.message.reply_text(
            f"📂 Раздел: {text}",
            reply_markup=category_menu()
        )

        return

    # =========================
    # НАЗАД
    # =========================
    if text == "⬅️ Назад":

        user_state[user_id] = None

        await update.message.reply_text(
            "🏠 Главное меню",
            reply_markup=main_menu()
        )

        return

    # =========================
    # ДОБАВИТЬ СБОРКУ
    # =========================
    if text == "➕ Добавить сборку":

        if user_id not in temp_category:

            await update.message.reply_text(
                "❌ Сначала выбери раздел"
            )

            return

        user_state[user_id] = "waiting_photo"

        await update.message.reply_text(
            "📸 Отправь скриншот своей сборки"
        )

        return

    # =========================
    # ПОКАЗАТЬ СБОРКИ
    # =========================
    if text == "📂 Посмотреть сборки":

        category = temp_category.get(user_id)

        if not category:

            await update.message.reply_text(
                "❌ Сначала выбери раздел"
            )

            return

        category_builds = builds[category]

        if len(category_builds) == 0:

            await update.message.reply_text(
                "😢 В этом разделе пока нет сборок"
            )

            return

        for index, build in enumerate(category_builds):

            keyboard = build_buttons(
                category,
                index,
                build["likes"],
                len(build["comments"])
            )

            comments_text = ""

            if len(build["comments"]) > 0:

                comments_text = "\n\n💬 Комментарии:\n"

                for comment in build["comments"]:
                    comments_text += f"\n• {comment}"

            await update.message.reply_photo(
                photo=build["photo"],
                caption=(
                    f"{build['description']}\n\n"
                    f"❤️ Лайков: {build['likes']}"
                    f"{comments_text}"
                ),
                reply_markup=keyboard
            )

        return


# =========================
# ОБРАБОТКА ФОТО
# =========================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    user_id = update.message.from_user.id

    # НЕ ЖДЕМ ФОТО
    if user_state.get(user_id) != "waiting_photo":
        return

    # ЕСЛИ НЕ ФОТО
    if not update.message.photo:

        await update.message.reply_text(
            "❌ Отправь именно фото"
        )

        return

    # СОХРАНЯЕМ ФОТО
    photo = update.message.photo[-1].file_id

    temp_photo[user_id] = photo

    # МЕНЯЕМ СОСТОЯНИЕ
    user_state[user_id] = "waiting_description"

    await update.message.reply_text(
        "✍️ Теперь отправь описание сборки"
    )


# =========================
# КНОПКИ
# =========================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    data = query.data

    parts = data.split("|")

    action = parts[0]
    category = parts[1]
    index = int(parts[2])

    build = builds[category][index]

    # =========================
    # ЛАЙК
    # =========================
    if action == "like":

        build["likes"] += 1

        keyboard = build_buttons(
            category,
            index,
            build["likes"],
            len(build["comments"])
        )

        await query.edit_message_reply_markup(
            reply_markup=keyboard
        )

        return

    # =========================
    # КОММЕНТ
    # =========================
    if action == "comment":

        user_id = query.from_user.id

        user_state[user_id] = "waiting_comment"

        context.user_data["comment_category"] = category
        context.user_data["comment_index"] = index

        await query.message.reply_text(
            "💬 Напиши комментарий к сборке"
        )

        return


# =========================
# ЗАПУСК БОТА
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))

app.add_handler(
    MessageHandler(filters.PHOTO, photo_handler)
)

app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
)

app.add_handler(
    CallbackQueryHandler(button_handler)
)

print("Бот запущен!")

app.run_polling()