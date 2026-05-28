import os
import json
import random
import requests
import threading
import uuid
import re
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ContextTypes, filters, CallbackQueryHandler
)

# =========================
# ВКЛЮЧАЕМ ЛОГИРОВАНИЕ ОШИБОК
# =========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =========================
# НАСТРОЙКИ
# =========================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = [7083142762]
DONAT_CARD = "2202208162561493"
MAX_DESC_LEN = 500

JSONBIN_KEY = "$2a$10$YToOVCHp5OUQNAy/9qZcE.NpzQ4.8Cxe0XD./KQeg7pU01mIzyDWG"
JSONBIN_ID = "6a16c58ef47d5c455c3c7925"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_rank(likes):
    if likes >= 150: return "🏆 Легенда"
    if likes >= 50: return "💎 Мастер"
    if likes >= 10: return "🔥 Профи"
    return "🔰 Новичок"

def normalize_weapon(name):
    return re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', name).upper()

# =========================
# БАЗА ДАННЫХ
# =========================
def get_empty_db():
    return {
        "users": {},
        "builds": {"КБ": {}, "СИ": {}}, 
        "sensa": {"КБ": [], "СИ": []},
        "layouts": {"КБ": [], "СИ": []},
        "tips": [],
        "news": []
    }

def load_data():
    headers = {"X-Master-Key": JSONBIN_KEY}
    try:
        r = requests.get(JSONBIN_URL, headers=headers)
        if r.status_code == 200:
            data = r.json().get("record", get_empty_db())
            
            if "users" not in data: data["users"] = {}
            if "builds" not in data: data["builds"] = {"КБ": {}, "СИ": {}}
            if "sensa" not in data: data["sensa"] = {"КБ": [], "СИ": []}
            if "layouts" not in data: data["layouts"] = {"КБ": [], "СИ": []}
            if "tips" not in data: data["tips"] = []
            if "news" not in data: data["news"] = []
            return data
    except Exception as e:
        logger.error(f"Ошибка загрузки БД: {e}")
    return get_empty_db()

def save_data(data):
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_KEY}
    try: 
        requests.put(JSONBIN_URL, json=data, headers=headers)
    except Exception as e: 
        logger.error(f"Ошибка сохранения БД: {e}")

db = load_data()

async def notify_author(context, author_id, text):
    try:
        await context.bot.send_message(chat_id=author_id, text=text, parse_mode="Markdown")
    except: pass

# =========================
# КЛАВИАТУРЫ
# =========================
def main_menu(user_id):
    kb = [
        ["🔫 Сборки (Оружие)", "🎮 Раскладка", "⚙️ Сенса"],
        ["🔥 Мета оружие", "🏆 Зал славы", "⭐ Избранное"],
        ["👤 Профиль", "📰 Новости сезона", "💡 Советы"],
        ["☕ Поддержать", "👥 Помощь"]
    ]
    if is_admin(user_id): kb.append(["👑 АДМИН-ПАНЕЛЬ"])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def mode_menu():
    return ReplyKeyboardMarkup([["🪂 КБ (Королевская битва)", "⚔️ СИ (Сетевая игра)"], ["🏠 В главное меню"]], resize_keyboard=True)

def weapons_menu():
    return ReplyKeyboardMarkup([
        ["🔫 Штурмовые", "🎯 Снайперские", "⚡ ПП"],
        ["💣 Пулеметы", "💥 Дробовики", "🏹 Пехотные"],
        ["🏠 В главное меню"]
    ], resize_keyboard=True)

def item_buttons(item_id, item_type, likes, dislikes, author_id, user_id):
    kb = [[
        InlineKeyboardButton(f"♥️ {likes}", callback_data=f"vote|{item_type}|{item_id}|like"),
        InlineKeyboardButton(f"👎 {dislikes}", callback_data=f"vote|{item_type}|{item_id}|dislike"),
        InlineKeyboardButton("⭐ В избранное", callback_data=f"fav|{item_type}|{item_id}")
    ]]
    if is_admin(user_id) or str(user_id) == str(author_id):
        kb.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"del|{item_type}|{item_id}")])
    return InlineKeyboardMarkup(kb)

# =========================
# ОСНОВНЫЕ ФУНКЦИИ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = str(user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"name": user.first_name, "likes_received": 0, "favs": []}
        save_data(db)
    context.user_data.clear()
    await update.message.reply_text(f"Салют, {user.first_name}! 🪂\nГотов разваливать кабины? Выбирай раздел:", reply_markup=main_menu(uid))

async def start_add_build(update: Update, context: ContextTypes.DEFAULT_TYPE, mode, category):
    context.user_data.update({"state": "build_name", "mode": mode, "category": category})
    await update.message.reply_text(f"Добавляем сборку в *{category}* ({mode}).\nНапиши точное название оружия (например: AK-47, DLQ33):", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

async def process_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get("state")
    uid = str(update.message.from_user.id)
    uname = update.message.from_user.first_name

    if state == "build_name":
        context.user_data["w_name"] = text
        context.user_data["w_tag"] = normalize_weapon(text)
        context.user_data["state"] = "build_photo"
        await update.message.reply_text("📸 Отлично! Теперь отправь скриншот сборки модулей:")
        return

    if state == "build_desc":
        if len(text) > MAX_DESC_LEN:
            await update.message.reply_text(f"❌ Текст слишком длинный (макс {MAX_DESC_LEN} символов). Сократи и отправь снова:")
            return
        
        mode, cat = context.user_data["mode"], context.user_data["category"]
        build = {
            "id": str(uuid.uuid4())[:8], "type": "build", "mode": mode, "category": cat,
            "weapon": context.user_data["w_name"], "tag": context.user_data["w_tag"],
            "photo": context.user_data["photo"], "desc": text,
            "author_id": uid, "author_name": uname, "likes": 0, "dislikes": 0, "voters": {}
        }
        if cat not in db["builds"][mode]: db["builds"][mode][cat] = []
        db["builds"][mode][cat].append(build)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Сборка успешно загружена в базу!", reply_markup=main_menu(uid))
        return

    if state == "sens_code":
        context.user_data["code"] = text
        context.user_data["state"] = "sens_desc"
        kb = ReplyKeyboardMarkup([["⏭ Пропустить"]], resize_keyboard=True)
        await update.message.reply_text("✍️ Добавь описание (макс 500 симв.) или нажми 'Пропустить':", reply_markup=kb)
        return

    if state == "sens_desc":
        if text != "⏭ Пропустить" and len(text) > MAX_DESC_LEN:
            await update.message.reply_text("❌ Слишком длинное описание. Сократи:")
            return
        
        mode = context.user_data["mode"]
        item = {
            "id": str(uuid.uuid4())[:8], "type": "sensa", "mode": mode,
            "os": context.user_data["os"], "device": context.user_data["dev"],
            "gyro": context.user_data["gyro"], "fingers": context.user_data["fingers"],
            "code": context.user_data["code"], "desc": "" if text == "⏭ Пропустить" else text,
            "author_id": uid, "author_name": uname, "likes": 0, "dislikes": 0, "voters": {}
        }
        db["sensa"][mode].append(item)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Код сенсы успешно добавлен!", reply_markup=main_menu(uid))
        return

    if state == "layout_code":
        context.user_data["code"] = text
        context.user_data["state"] = "layout_desc"
        kb = ReplyKeyboardMarkup([["⏭ Пропустить"]], resize_keyboard=True)
        await update.message.reply_text("✍️ Добавь описание (макс 500 симв.) или нажми 'Пропустить':", reply_markup=kb)
        return

    if state == "layout_desc":
        if text != "⏭ Пропустить" and len(text) > MAX_DESC_LEN:
            await update.message.reply_text("❌ Слишком длинное описание:")
            return
        mode = context.user_data["mode"]
        item = {
            "id": str(uuid.uuid4())[:8], "type": "layout", "mode": mode,
            "photo": context.user_data["photo"], "code": context.user_data["code"],
            "desc": "" if text == "⏭ Пропустить" else text,
            "author_id": uid, "author_name": uname, "likes": 0, "dislikes": 0, "voters": {}
        }
        db["layouts"][mode].append(item)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Раскладка успешно добавлена!", reply_markup=main_menu(uid))
        return

async def process_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if state == "build_photo":
        context.user_data["photo"] = update.message.photo[-1].file_id
        context.user_data["state"] = "build_desc"
        await update.message.reply_text("✍️ Напиши описание сборки модулей (макс 500 символов):")
    elif state == "layout_photo":
        context.user_data["photo"] = update.message.photo[-1].file_id
        context.user_data["state"] = "layout_code"
        await update.message.reply_text("🔢 Теперь отправь код раскладки (например: 7326154...):")

# === МЕНЮ И НАВИГАЦИЯ ===
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = str(update.message.from_user.id)
    
    # ЖЕСТКИЙ ПЕРЕХВАТЧИК: Возврат в меню моментально прерывает любые зависшие ожидания
    if text in ["🏠 В главное меню", "/start"]:
        context.user_data.clear()
        await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu(uid))
        return

    if context.user_data.get("state"):
        await process_text_inputs(update, context)
        return
        
    if text == "🔫 Сборки (Оружие)":
        context.user_data["section"] = "builds"
        await update.message.reply_text("Выбери режим:", reply_markup=mode_menu())
        return
    if text == "⚙️ Сенса":
        context.user_data["section"] = "sensa"
        await update.message.reply_text("Выбери режим для сенсы:", reply_markup=mode_menu())
        return
    if text == "🎮 Раскладка":
        context.user_data["section"] = "layouts"
        await update.message.reply_text("Выбери режим для раскладки:", reply_markup=mode_menu())
        return

    if text in ["🪂 КБ (Королевская битва)", "⚔️ СИ (Сетевая игра)"]:
        mode = "КБ" if "КБ" in text else "СИ"
        sec = context.user_data.get("section")
        if sec == "builds":
            context.user_data["mode"] = mode
            await update.message.reply_text(f"Оружие для {mode}. Выбери класс:", reply_markup=weapons_menu())
        elif sec == "sensa":
            context.user_data.update({"state": "sens_os", "mode": mode})
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Android", callback_data="sens|os|Android"), InlineKeyboardButton("🍏 iOS", callback_data="sens|os|iOS")]])
            await update.message.reply_text(f"⚙️ Сенса ({mode})\nВыбери платформу:", reply_markup=kb)
        elif sec == "layouts":
            context.user_data.update({"state": "layout_photo", "mode": mode})
            await update.message.reply_text(f"🎮 Раскладка ({mode})\nОтправь скриншот твоего HUD (экрана):", reply_markup=ReplyKeyboardRemove())
        return

    categories = ["🔫 Штурмовые", "🎯 Снайперские", "⚡ ПП", "💣 Пулеметы", "💥 Дробовики", "🏹 Пехотные"]
    if text in categories:
        mode = context.user_data.get("mode", "КБ")
        cat_name = text.split(" ")[1] 
        builds_list = db["builds"][mode].get(cat_name, [])
        
        btn = [[InlineKeyboardButton("➕ Добавить сборку", callback_data=f"addb|{mode}|{cat_name}")]]
        if not builds_list:
            await update.message.reply_text(f"В категории {text} ({mode}) пока пусто.", reply_markup=InlineKeyboardMarkup(btn))
            return
            
        await update.message.reply_text(f"📂 *{text} ({mode})*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btn))
        for b in builds_list[-10:]: 
            kb = item_buttons(b["id"], "builds", b["likes"], b["dislikes"], b["author_id"], uid)
            cap = f"🔫 *{b['weapon']}*\n📝 {b['desc']}\n👤 Автор: {b['author_name']}"
            await update.message.reply_photo(photo=b["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)
        return

    if text == "🔥 Мета оружие":
        await show_auto_meta(update, context)
        return
        
    if text == "👤 Профиль":
        u_info = db["users"].get(uid, {})
        likes = u_info.get("likes_received", 0)
        rank = get_rank(likes)
        await update.message.reply_text(f"👤 *ТВОЙ ПРОФИЛЬ*\n━━━━━━━━━━━━━━━\nИмя: {u_info.get('name')}\nРанг: {rank}\nСобрано ♥️: {likes}", parse_mode="Markdown")
        return

async def show_auto_meta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    for mode in ["КБ", "СИ"]:
        all_builds = []
        for cat in db["builds"][mode]:
            all_builds.extend(db["builds"][mode][cat])
        
        top3 = sorted(all_builds, key=lambda x: x["likes"], reverse=True)[:3]
        if not top3: continue
        
        await update.message.reply_text(f"🔥 *АБСОЛЮТНАЯ МЕТА - {mode}*", parse_mode="Markdown")
        medals = ["🥇", "🥈", "🥉"]
        for i, b in enumerate(top3):
            kb = item_buttons(b["id"], "builds", b["likes"], b["dislikes"], b["author_id"], uid)
            cap = f"{medals[i]} *{b['weapon']}* ({b['category']})\n📝 {b['desc']}\n👤 Автор: {b['author_name']}"
            await update.message.reply_photo(photo=b["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(query.from_user.id)
    uname = query.from_user.first_name
    data = query.data.split("|")

    if data[0] == "addb": 
        await start_add_build(update, context, data[1], data[2])
        await query.answer()
        return

    if data[0] == "sens":
        step, val = data[1], data[2]
        context.user_data[step] = val
        if step == "os":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📱 Телефон", callback_data="sens|dev|Телефон"), InlineKeyboardButton("🖥 Планшет", callback_data="sens|dev|Планшет")]])
            await query.edit_message_text("Выбери устройство:", reply_markup=kb)
        elif step == "dev":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Включен", callback_data="sens|gyro|С гироскопом"), InlineKeyboardButton("Выключен", callback_data="sens|gyro|Без гироскопа")]])
            await query.edit_message_text("Гироскоп:", reply_markup=kb)
        elif step == "gyro":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{i} 🤞", callback_data=f"sens|fingers|{i} пальцев") for i in range(2, 7)]])
            await query.edit_message_text("Сколько пальцев хват?", reply_markup=kb)
        elif step == "fingers":
            context.user_data["state"] = "sens_code"
            await query.message.delete()
            await query.message.reply_text("🔢 Отлично! Отправь цифровой код сенсы:")
        return

    if data[0] == "vote":
        item_type, item_id, vote_type = data[1], data[2], data[3]
        item = None
        for mode in db[item_type]:
            if isinstance(db[item_type][mode], dict):
                for cat in db[item_type][mode]:
                    for i in db[item_type][mode][cat]:
                        if i["id"] == item_id: item = i
            else:
                for i in db[item_type][mode]:
                    if i["id"] == item_id: item = i
        
        if not item:
            await query.answer("Пост не найден или удален", show_alert=True)
            return

        auth_id = str(item["author_id"])
        if uid == auth_id:
            await query.answer("❌ Свой контент оценивать нельзя!", show_alert=True)
            return

        current_vote = item["voters"].get(uid)
        notif = ""
        if current_vote == vote_type:
            item["voters"].pop(uid)
            item[vote_type + "s"] -= 1
            if vote_type == "like" and auth_id in db["users"]: db["users"][auth_id]["likes_received"] -= 1
        else:
            if current_vote:
                item[current_vote + "s"] -= 1
                if current_vote == "like" and auth_id in db["users"]: db["users"][auth_id]["likes_received"] -= 1
            
            item["voters"][uid] = vote_type
            item[vote_type + "s"] += 1
            if vote_type == "like": 
                if auth_id in db["users"]: db["users"][auth_id]["likes_received"] += 1
                notif = f"♥️ *{uname}* оценил твой пост!"
            else:
                notif = f"👎 *{uname}* поставил дизлайк."

        save_data(db)
        kb = item_buttons(item_id, item_type, item["likes"], item["dislikes"], auth_id, uid)
        await query.edit_message_reply_markup(reply_markup=kb)
        if notif: await notify_author(context, auth_id, notif)
        await query.answer("Голос учтен!")

    if data[0] == "del":
        item_type, item_id = data[1], data[2]
        for mode in db[item_type]:
            if isinstance(db[item_type][mode], dict):
                for cat in db[item_type][mode]:
                    db[item_type][mode][cat] = [i for i in db[item_type][mode][cat] if i["id"] != item_id]
            else:
                db[item_type][mode] = [i for i in db[item_type][mode] if i["id"] != item_id]
        save_data(db)
        await query.message.delete()
        await query.answer("Удалено!")

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"CoDM Bot Active!")
    def log_message(self, format, *args):
        return

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    try:
        HTTPServer(('0.0.0.0', port), DummyHandler).serve_forever()
    except Exception as e:
        logger.error(f"Ошибка сервера: {e}")

def main():
    if not TOKEN:
        logger.error("❌ ОШИБКА: Токен не найден!")
        return

    threading.Thread(target=keep_alive, daemon=True).start()
    logger.info("✅ Запуск бота...")
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, process_photos))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
