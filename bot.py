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
# ЛОГИРОВАНИЕ ОШИБОК
# =========================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# НАСТРОЙКИ
# =========================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = ["7083142762"] 
DONAT_CARD = "2202208162561493"
MAX_DESC_LEN = 500

JSONBIN_KEY = "$2a$10$YToOVCHp5OUQNAy/9qZcE.NpzQ4.8Cxe0XD./KQeg7pU01mIzyDWG"
JSONBIN_ID = "6a16c58ef47d5c455c3c7925"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"

def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

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
    return {"users": {}, "builds": {"КБ": {}, "СИ": {}}, "sensa": {"КБ": [], "СИ": []}, "layouts": {"КБ": [], "СИ": []}, "tips": [], "news": []}

def load_data():
    headers = {"X-Master-Key": JSONBIN_KEY}
    try:
        r = requests.get(JSONBIN_URL, headers=headers)
        if r.status_code == 200:
            data = r.json().get("record", get_empty_db())
            for k in get_empty_db().keys():
                if k not in data: data[k] = get_empty_db()[k]
            return data
    except Exception as e: logger.error(f"Ошибка БД: {e}")
    return get_empty_db()

def save_data(data):
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_KEY}
    try: requests.put(JSONBIN_URL, json=data, headers=headers)
    except Exception as e: logger.error(f"Ошибка БД: {e}")

db = load_data()

async def notify_author(context, author_id, text):
    try: await context.bot.send_message(chat_id=author_id, text=text, parse_mode="Markdown")
    except: pass

# =========================
# КЛАВИАТУРЫ
# =========================
def main_menu(user_id):
    kb = [
        ["🔫 Сборки", "⚙️ Сенса", "🎮 Раскладка"],
        ["🔍 Поиск", "🔥 Мета оружие", "⭐ Избранное"],
        ["👤 Профиль", "📰 Новости сезона", "💡 Советы"],
        ["🏆 Зал славы", "☕ Поддержать", "👥 Помощь"]
    ]
    if is_admin(user_id): kb.append(["👑 АДМИН-ПАНЕЛЬ"])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def cancel_menu():
    return ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)

def mode_menu():
    return ReplyKeyboardMarkup([["🪂 КБ (Королевская битва)", "⚔️ СИ (Сетевая игра)"], ["🏠 В главное меню"]], resize_keyboard=True)

def weapons_menu():
    return ReplyKeyboardMarkup([
        ["🔫 Штурмовые", "🎯 Снайперские", "⚡ ПП"],
        ["💣 Пулеметы", "💥 Дробовики", "🏹 Пехотные"],
        ["🏠 В главное меню"]
    ], resize_keyboard=True)

def item_buttons(item_id, item_type, likes, dislikes, author_id, user_id):
    is_fav = f"{item_type}|{item_id}" in db["users"].get(str(user_id), {}).get("favs", [])
    fav_text = "🌟 Убрать из избранного" if is_fav else "⭐ В избранное"
    
    kb = [[
        InlineKeyboardButton(f"♥️ {likes}", callback_data=f"vote|{item_type}|{item_id}|like"),
        InlineKeyboardButton(f"👎 {dislikes}", callback_data=f"vote|{item_type}|{item_id}|dislike"),
    ], [
        InlineKeyboardButton(fav_text, callback_data=f"fav|{item_type}|{item_id}")
    ]]
    
    if is_admin(user_id) or str(user_id) == str(author_id):
        kb.append([InlineKeyboardButton("🗑 Удалить", callback_data=f"del|{item_type}|{item_id}")])
    return InlineKeyboardMarkup(kb)

# =========================
# ДОБАВЛЕНИЕ СБОРКИ
# =========================
async def start_add_build(update: Update, context: ContextTypes.DEFAULT_TYPE, mode, category):
    context.user_data.update({"state": "build_photo", "mode": mode, "category": category})
    await update.effective_message.reply_text(
        f"📸 *Шаг 1/3*\nДобавляем сборку в *{category}* ({mode}).\n\nДля начала отправь скриншот твоей сборки модулей:", 
        parse_mode="Markdown", reply_markup=cancel_menu()
    )

# =========================
# ОБРАБОТКА ТЕКСТА
# =========================
async def process_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get("state")
    uid = str(update.message.from_user.id)
    uname = update.message.from_user.first_name

    if state in ["build_photo", "layout_photo"]:
        await update.message.reply_text("❌ Ошибка: Сейчас я жду от тебя картинку (скриншот), а не текст.", reply_markup=cancel_menu())
        return

    if state == "search":
        tag = normalize_weapon(text)
        results = []
        for m in db["builds"]:
            for cat in db["builds"][m]:
                for b in db["builds"][m][cat]:
                    if tag in b["tag"] or b["tag"] in tag: results.append(b)
        
        context.user_data.clear()
        if not results:
            await update.message.reply_text("К сожалению, сборок на это оружие пока нет.", reply_markup=main_menu(uid))
        else:
            await update.message.reply_text(f"🔍 Найдено сборок: {len(results)}", reply_markup=main_menu(uid))
            for b in results[-5:]:
                kb = item_buttons(b["id"], "builds", b["likes"], b["dislikes"], b["author_id"], uid)
                cap = f"🔫 *{b['weapon']}*\n📝 {b['desc']}\n👤 Автор: {b['author_name']}"
                await update.message.reply_photo(photo=b["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)
        return

    if state == "tip_add":
        tip = {"id": str(uuid.uuid4())[:8], "text": text, "author_name": uname, "author_id": uid, "likes": 0, "dislikes": 0, "voters": {}}
        db["tips"].append(tip)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Твой совет успешно опубликован!", reply_markup=main_menu(uid))
        return

    if state == "adm_news_text":
        news_item = {"id": str(uuid.uuid4())[:8], "type": "news", "text": text, "photo": None}
        db["news"].append(news_item)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Текстовая новость сезона успешно опубликована!", reply_markup=main_menu(uid))
        return

    if state == "build_name":
        context.user_data["w_name"] = text
        context.user_data["w_tag"] = normalize_weapon(text)
        context.user_data["state"] = "build_desc"
        await update.message.reply_text("✍️ *Шаг 3/3*\nСупер! Напиши описание сборки (как работает, какие плюсы, макс 500 символов):", parse_mode="Markdown", reply_markup=cancel_menu())
        return

    if state == "build_desc":
        mode, cat = context.user_data["mode"], context.user_data["category"]
        build = {"id": str(uuid.uuid4())[:8], "type": "build", "mode": mode, "category": cat, "weapon": context.user_data["w_name"], "tag": context.user_data["w_tag"], "photo": context.user_data["photo"], "desc": text[:MAX_DESC_LEN], "author_id": uid, "author_name": uname, "likes": 0, "dislikes": 0, "voters": {}}
        if cat not in db["builds"][mode]: db["builds"][mode][cat] = []
        db["builds"][mode][cat].append(build)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Сборка успешно загружена в базу!", reply_markup=main_menu(uid))
        return

    if state == "sens_code":
        context.user_data["code"] = text
        context.user_data["state"] = "sens_desc"
        await update.message.reply_text("✍️ *Шаг 2/2*\nДобавь описание или нажми 'Пропустить':", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup([["⏭ Пропустить"], ["❌ Отмена"]], resize_keyboard=True))
        return

    if state == "sens_desc":
        mode = context.user_data["mode"]
        item = {"id": str(uuid.uuid4())[:8], "type": "sensa", "mode": mode, "os": context.user_data["os"], "device": context.user_data["dev"], "gyro": context.user_data["gyro"], "code": context.user_data["code"], "desc": "" if text == "⏭ Пропустить" else text[:MAX_DESC_LEN], "author_id": uid, "author_name": uname, "likes": 0, "dislikes": 0, "voters": {}}
        db["sensa"][mode].append(item)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Код сенсы успешно добавлен!", reply_markup=main_menu(uid))
        return

    if state == "layout_code":
        context.user_data["code"] = text
        context.user_data["state"] = "layout_desc"
        await update.message.reply_text("✍️ *Шаг 3/3*\nДобавь описание или нажми 'Пропустить':", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup([["⏭ Пропустить"], ["❌ Отмена"]], resize_keyboard=True))
        return

    if state == "layout_desc":
        mode = context.user_data["mode"]
        item = {"id": str(uuid.uuid4())[:8], "type": "layout", "mode": mode, "fingers": context.user_data.get("fingers", "Не указано"), "photo": context.user_data["photo"], "code": context.user_data["code"], "desc": "" if text == "⏭ Пропустить" else text[:MAX_DESC_LEN], "author_id": uid, "author_name": uname, "likes": 0, "dislikes": 0, "voters": {}}
        db["layouts"][mode].append(item)
        save_data(db)
        context.user_data.clear()
        await update.message.reply_text("✅ Раскладка успешно добавлена!", reply_markup=main_menu(uid))
        return

# =========================
# ОБРАБОТКА ФОТО
# =========================
async def process_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    
    if state in ["build_name", "build_desc", "sens_code", "sens_desc", "layout_code", "layout_desc", "tip_add", "search", "adm_news_text"]:
        await update.message.reply_text("❌ Ошибка: Сейчас я жду текст, а не скриншот.", reply_markup=cancel_menu())
        return

    if state == "build_photo":
        context.user_data["photo"] = update.message.photo[-1].file_id
        context.user_data["state"] = "build_name"
        await update.message.reply_text("✍️ *Шаг 2/3*\nПосмотри на свой скриншот и напиши точное название оружия (например: AK47):", parse_mode="Markdown", reply_markup=cancel_menu())
    
    elif state == "layout_photo":
        context.user_data["photo"] = update.message.photo[-1].file_id
        context.user_data["state"] = "layout_code"
        await update.message.reply_text("🔢 *Шаг 2/3*\nТеперь отправь цифровой код раскладки (например: 7326154...):", parse_mode="Markdown", reply_markup=cancel_menu())

# =========================
# ГЛАВНЫЙ РОУТЕР
# =========================
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = str(update.message.from_user.id)
    
    if text in ["❌ Отмена", "🏠 В главное меню", "/start"]:
        context.user_data.clear()
        if uid not in db["users"]:
            db["users"][uid] = {"name": update.message.from_user.first_name, "likes_received": 0, "favs": []}
            save_data(db)
        await update.message.reply_text("🏠 Главное меню. Выбирай раздел:", reply_markup=main_menu(uid))
        return

    if context.user_data.get("state"):
        await process_text_inputs(update, context)
        return
        
    if text == "🔫 Сборки":
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
    
    if text == "🔍 Поиск":
        context.user_data["state"] = "search"
        await update.message.reply_text("🔍 Введи точное название оружия (например, AK47):", reply_markup=cancel_menu())
        return

    if text == "🔥 Мета оружие":
        await show_auto_meta(update, context)
        return

    if text in ["🪂 КБ (Королевская битва)", "⚔️ СИ (Сетевая игра)"]:
        mode = "КБ" if "КБ" in text else "СИ"
        sec = context.user_data.get("section")
        if sec == "builds":
            context.user_data["mode"] = mode
            await update.message.reply_text(f"Оружие для {mode}. Выбери класс:", reply_markup=weapons_menu())
        elif sec == "sensa":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("👀 Смотреть сенсу", callback_data=f"view|sensa|{mode}")], [InlineKeyboardButton("➕ Добавить свою", callback_data=f"add|sensa|{mode}")]])
            await update.message.reply_text(f"⚙️ Сенса ({mode})", reply_markup=kb)
        elif sec == "layouts":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("👀 Смотреть раскладки", callback_data=f"view|layouts|{mode}")], [InlineKeyboardButton("➕ Добавить свою", callback_data=f"add|layouts|{mode}")]])
            await update.message.reply_text(f"🎮 Раскладка ({mode})", reply_markup=kb)
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
            
        await update.message.reply_text(f"📂 *{text} ({mode})*", parse_mode="Markdown")
        
        for b in builds_list[-10:]: 
            kb = item_buttons(b["id"], "builds", b["likes"], b["dislikes"], b["author_id"], uid)
            cap = f"🔫 *{b['weapon']}*\n📝 {b['desc']}\n👤 Автор: {b['author_name']}"
            await update.message.reply_photo(photo=b["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)
            
        await update.message.reply_text(f"👇 Добавить свою сборку в *{cat_name}* ({mode}):", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btn))
        return

    # === ПРОФИЛЬ С АВТО-ОЧИСТКОЙ ===
    if text == "👤 Профиль":
        u_info = db["users"].get(uid, {})
        likes = u_info.get("likes_received", 0)
        rank = get_rank(likes)
        
        valid_favs = []
        for fav in u_info.get("favs", []):
            try:
                it_type, it_id = fav.split("|")
                item_exists = False
                if it_type == "builds":
                    for m in db["builds"]:
                        for c in db["builds"][m]:
                            if any(i["id"] == it_id for i in db["builds"][m][c]): item_exists = True
                else:
                    for m in db[it_type]:
                        if isinstance(db[it_type], dict) and isinstance(db[it_type][m], list):
                            if any(i["id"] == it_id for i in db[it_type][m]): item_exists = True
                        elif isinstance(db[it_type], list):
                            if any(m_tip["id"] == it_id for m_tip in db[it_type]): item_exists = True
                            
                if item_exists and fav not in valid_favs:
                    valid_favs.append(fav)
            except: pass

        if len(u_info.get("favs", [])) != len(valid_favs):
            db["users"][uid]["favs"] = valid_favs
            save_data(db)

        favs_count = len(valid_favs)
        
        posts_count = 0
        for m in db["builds"]:
            for c in db["builds"][m]:
                posts_count += len([b for b in db["builds"][m][c] if str(b.get("author_id")) == uid])
        for m in db["sensa"]:
            posts_count += len([b for b in db["sensa"][m] if str(b.get("author_id")) == uid])
        for m in db["layouts"]:
            posts_count += len([b for b in db["layouts"][m] if str(b.get("author_id")) == uid])
        posts_count += len([t for t in db["tips"] if str(t.get("author_id")) == uid])

        await update.message.reply_text(
            f"👤 *ТВОЙ ПРОФИЛЬ*\n━━━━━━━━━━━━━━━\n📝 Имя: {u_info.get('name', 'Боец')}\n🏆 Ранг: {rank}\n♥️ Собранных лайков: {likes}\n📦 Опубликовано постов: {posts_count}\n⭐ В избранном: {favs_count}", 
            parse_mode="Markdown"
        )
        return

    # === ИЗБРАННОЕ ===
    if text == "⭐ Избранное":
        favs = db["users"].get(uid, {}).get("favs", [])
        if not favs:
            await update.message.reply_text("Твое избранное пока пусто! Нажимай '⭐ В избранное' под крутыми сборками, сенсой или советами.")
            return
        
        await update.message.reply_text("⭐ *ТВОЕ ИЗБРАННОЕ (Последние 5)*", parse_mode="Markdown")
        
        for fav in favs[-5:]:
            try: item_type, item_id = fav.split("|")
            except: continue
            
            item = None
            if item_type == "builds":
                for m in db["builds"]:
                    for c in db["builds"][m]:
                        for i in db["builds"][m][c]:
                            if i["id"] == item_id: item = i
            else:
                for m in db[item_type]:
                    if isinstance(db[item_type], dict) and isinstance(db[item_type][m], list):
                        for i in db[item_type][m]:
                            if i["id"] == item_id: item = i
                    elif isinstance(db[item_type], list):
                        if m["id"] == item_id: item = m
                        
            if not item: continue
            
            kb = item_buttons(item["id"], item_type, item.get("likes",0), item.get("dislikes",0), item["author_id"], uid)
            
            if item_type == "builds":
                cap = f"🔫 *{item['weapon']}* ({item['category']})\n📝 {item['desc']}\n👤 Автор: {item['author_name']}"
                await update.message.reply_photo(photo=item["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)
            elif item_type == "sensa":
                cap = f"⚙️ *Сенса ({item['mode']})*\n📱 {item['os']} | {item['device']}\n⚖️ {item['gyro']}\n\n🔢 Код: `{item['code']}`\n📝 {item['desc']}\n👤 Автор: {item['author_name']}"
                await update.message.reply_text(cap, parse_mode="Markdown", reply_markup=kb)
            elif item_type == "layouts":
                cap = f"🎮 *Раскладка ({item['mode']})*\n🤞 {item.get('fingers', 'Не указано')}\n🔢 Код: `{item['code']}`\n📝 {item['desc']}\n👤 Автор: {item['author_name']}"
                await update.message.reply_photo(photo=item["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)
            elif item_type == "tips":
                await update.message.reply_text(f"💡 *Совет от {item['author_name']}*\n\n{item['text']}", parse_mode="Markdown", reply_markup=kb)
        return

    # === ИНФО-РАЗДЕЛЫ ===
    if text == "👥 Помощь":
        guide = "📖 *ГАЙД ПО БОТУ*\n\n1️⃣ *Сборки, Сенса, Раскладка* - здесь ты можешь найти или загрузить свои варианты настройки игры. Разделены на КБ и СИ.\n2️⃣ *Добавление* - следуй инструкциям бота на экране. Если ошибся - жми 'Отмена'.\n3️⃣ *Оценки* - ставь ♥️ или 👎. Автор с наибольшим количеством лайков получает высокие ранги (до Легенды).\n4️⃣ *Поиск* - ищи лучшие сборки на конкретную пушку по её названию.\n5️⃣ *Мета* - автоматический ТОП-3 самых залайканных пушек в боте."
        await update.message.reply_text(guide, parse_mode="Markdown")
        return

    if text == "☕ Поддержать":
        await update.message.reply_text(f"Спасибо за поддержку проекта! 🙏\nТвои донаты помогают оплачивать сервера.\n\n💳 Карта Сбербанк (нажми на цифры, чтобы скопировать):\n`{DONAT_CARD}`", parse_mode="Markdown")
        return

    if text == "💡 Советы":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Написать совет", callback_data="add_tip")]])
        if not db["tips"]:
            await update.message.reply_text("Советов пока нет. Будь первым!", reply_markup=kb)
        else:
            await update.message.reply_text("💡 *СОВЕТЫ ОТ ИГРОКОВ*", parse_mode="Markdown")
            for t in db["tips"][-5:]:
                tkb = item_buttons(t["id"], "tips", t.get("likes",0), t.get("dislikes",0), t["author_id"], uid)
                await update.message.reply_text(f"👤 *{t['author_name']}* пишет:\n\n{t['text']}", parse_mode="Markdown", reply_markup=tkb)
            await update.message.reply_text("👇 Добавить свой совет:", reply_markup=kb)
        return

    if text == "📰 Новости сезона":
        if not db["news"]:
            await update.message.reply_text("Новостей пока нет.")
        else:
            for n in db["news"][-3:]:
                # Умная отправка длинных текстов
                text_to_send = n["text"]
                if n.get("photo"):
                    if len(text_to_send) > 1000:
                        await update.message.reply_photo(photo=n["photo"])
                        # Режем на куски по 4000 символов
                        chunks = [text_to_send[i:i+4000] for i in range(0, len(text_to_send), 4000)]
                        for chunk in chunks:
                            await update.message.reply_text(chunk)
                    else:
                        await update.message.reply_photo(photo=n["photo"], caption=text_to_send)
                else:
                    chunks = [text_to_send[i:i+4000] for i in range(0, len(text_to_send), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
        return
        
    if text == "🏆 Зал славы":
        users_list = list(db["users"].values())
        top_users = sorted(users_list, key=lambda x: x.get("likes_received", 0), reverse=True)
        top_users = [u for u in top_users if u.get("likes_received", 0) > 0][:5]
        
        if not top_users:
            await update.message.reply_text("🏆 Зал славы пока пуст. Собирай лайки и стань первым!")
            return
            
        res = "🏆 *ЗАЛ СЛАВЫ (Топ авторов)*\n━━━━━━━━━━━━━━━\n\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, u in enumerate(top_users):
            rank = get_rank(u.get('likes_received', 0))
            res += f"{medals[i]} *{u.get('name', 'Аноним')}* — {u.get('likes_received', 0)} ♥️ ({rank})\n"
        await update.message.reply_text(res, parse_mode="Markdown")
        return

    if text == "👑 АДМИН-ПАНЕЛЬ" and is_admin(uid):
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📰 Добавить новость сезона (Текст)", callback_data="adm_news")]])
        await update.message.reply_text("👑 Пульт Администратора\n(Удаление постов доступно прямо под самими постами по кнопке '🗑 Удалить')", reply_markup=kb)
        return

async def show_auto_meta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    has_meta = False
    
    for mode in ["КБ", "СИ"]:
        all_builds = []
        for cat in db["builds"][mode]:
            all_builds.extend(db["builds"][mode][cat])
        
        top3 = sorted(all_builds, key=lambda x: x["likes"], reverse=True)[:3]
        top3 = [b for b in top3 if b["likes"] > 0]
        
        if not top3: continue
        has_meta = True
        
        await update.message.reply_text(f"🔥 *АБСОЛЮТНАЯ МЕТА - {mode}*", parse_mode="Markdown")
        medals = ["🥇", "🥈", "🥉"]
        for i, b in enumerate(top3):
            kb = item_buttons(b["id"], "builds", b["likes"], b["dislikes"], b["author_id"], uid)
            cap = f"{medals[i]} *{b['weapon']}* ({b['category']})\n📝 {b['desc']}\n👤 Автор: {b['author_name']}"
            await update.message.reply_photo(photo=b["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)
            
    if not has_meta:
        await update.message.reply_text("🔥 Мета-оружие еще формируется! Ставьте лайки лучшим сборкам, чтобы они попали в этот ТОП.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = str(query.from_user.id)
    uname = query.from_user.first_name
    data = query.data.split("|")

    if data[0] == "fav":
        item_type, item_id = data[1], data[2]
        fav_str = f"{item_type}|{item_id}"
        
        u_info = db["users"].get(uid)
        if not u_info:
            await query.answer("Профиль не найден! Отправь /start", show_alert=True)
            return
            
        if "favs" not in u_info: u_info["favs"] = []
            
        if fav_str in u_info["favs"]:
            u_info["favs"] = [f for f in u_info["favs"] if f != fav_str]
            action = "❌ Убрано из избранного"
        else:
            u_info["favs"].append(fav_str)
            action = "⭐ Добавлено в избранное"
            
        u_info["favs"] = list(dict.fromkeys(u_info["favs"]))
        save_data(db)
        
        item = None
        if item_type == "builds":
            for m in db["builds"]:
                for c in db["builds"][m]:
                    for i in db["builds"][m][c]:
                        if i["id"] == item_id: item = i
        else:
            for m in db[item_type]:
                if isinstance(db[item_type], dict) and isinstance(db[item_type][m], list):
                    for i in db[item_type][m]:
                        if i["id"] == item_id: item = i
                elif isinstance(db[item_type], list):
                    if m["id"] == item_id: item = m
                    
        if item:
            kb = item_buttons(item_id, item_type, item.get("likes",0), item.get("dislikes",0), item["author_id"], uid)
            await query.edit_message_reply_markup(reply_markup=kb)
            
            if action == "⭐ Добавлено в избранное" and str(item["author_id"]) != uid:
                await notify_author(context, item["author_id"], f"⭐ Кто-то сохранил твой контент в Избранное!")

        await query.answer(action)
        return

    if data[0] == "view":
        item_type, mode = data[1], data[2]
        items = db[item_type][mode]
        
        if not items:
            await query.message.reply_text("Пока ничего не загружено.")
        else:
            for i in items[-5:]:
                kb = item_buttons(i["id"], item_type, i.get("likes",0), i.get("dislikes",0), i["author_id"], uid)
                if item_type == "sensa":
                    cap = f"⚙️ *Сенса ({mode})*\n📱 {i['os']} | {i['device']}\n⚖️ {i['gyro']}\n\n🔢 Код: `{i['code']}`\n📝 {i['desc']}\n👤 Автор: {i['author_name']}"
                    await query.message.reply_text(cap, parse_mode="Markdown", reply_markup=kb)
                elif item_type == "layouts":
                    cap = f"🎮 *Раскладка ({mode})*\n🤞 {i.get('fingers', 'Не указано')}\n🔢 Код: `{i['code']}`\n📝 {i['desc']}\n👤 Автор: {i['author_name']}"
                    await query.message.reply_photo(photo=i["photo"], caption=cap, parse_mode="Markdown", reply_markup=kb)
                    
            add_btn = [[InlineKeyboardButton("➕ Добавить свою", callback_data=f"add|{item_type}|{mode}")]]
            name = "сенсу" if item_type == "sensa" else "раскладку"
            await query.message.reply_text(f"👇 Добавить свою {name} ({mode}):", reply_markup=InlineKeyboardMarkup(add_btn))
            
        await query.answer()
        return

    if data[0] == "add":
        item_type, mode = data[1], data[2]
        context.user_data["mode"] = mode
        if item_type == "sensa":
            context.user_data["state"] = "sens_os"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Android", callback_data="sens|os|Android"), InlineKeyboardButton("🍏 iOS", callback_data="sens|os|iOS")]])
            await query.message.reply_text(f"⚙️ Добавление сенсы ({mode})\nВыбери платформу:", reply_markup=kb)
        elif item_type == "layouts":
            context.user_data["state"] = "layout_fingers"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{i} 🤞", callback_data=f"layout|fingers|{i} пальцев") for i in range(2, 7)]])
            await query.message.reply_text(f"🎮 Добавление раскладки ({mode})\nВыбери хват (сколько пальцев):", reply_markup=kb)
        await query.answer()
        return

    if data[0] == "add_tip":
        context.user_data["state"] = "tip_add"
        await query.message.reply_text("Напиши свой совет для игроков:", reply_markup=cancel_menu())
        await query.answer()
        return

    if data[0] == "adm_news":
        context.user_data["state"] = "adm_news_text"
        await query.message.reply_text("Отправь текст новости сезона.\n(Если текст очень длинный, бот сам разобьет его на части):", reply_markup=cancel_menu())
        await query.answer()
        return

    if data[0] == "addb": 
        await start_add_build(update, context, data[1], data[2])
        await query.answer()
        return

    if data[0] == "layout" and data[1] == "fingers":
        context.user_data["fingers"] = data[2]
        context.user_data["state"] = "layout_photo"
        await query.message.delete()
        await query.message.reply_text("📸 *Шаг 1/3*\nОтправь скриншот твоего HUD (экрана):", parse_mode="Markdown", reply_markup=cancel_menu())
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
            context.user_data["state"] = "sens_code"
            await query.message.delete()
            await query.message.reply_text("🔢 *Шаг 1/2*\nОтлично! Отправь цифровой код сенсы:", parse_mode="Markdown", reply_markup=cancel_menu())
        return

    if data[0] == "vote":
        item_type, item_id, vote_type = data[1], data[2], data[3]
        item = None
        
        if item_type == "builds":
            for m in db["builds"]:
                for c in db["builds"][m]:
                    for i in db["builds"][m][c]:
                        if i["id"] == item_id: item = i
        else:
            for m in db[item_type]:
                if isinstance(db[item_type], dict) and isinstance(db[item_type][m], list):
                    for i in db[item_type][m]:
                        if i["id"] == item_id: item = i
                elif isinstance(db[item_type], list):
                    if m["id"] == item_id: item = m

        if not item:
            await query.answer("Пост не найден", show_alert=True)
            return

        auth_id = str(item["author_id"])
        if uid == auth_id:
            await query.answer("❌ Свой контент оценивать нельзя!", show_alert=True)
            return

        cv = item.get("voters", {}).get(uid)
        notif = ""
        
        if cv == vote_type:
            item["voters"].pop(uid)
            item[vote_type + "s"] -= 1
            if vote_type == "like" and auth_id in db["users"]: 
                db["users"][auth_id]["likes_received"] -= 1
        else:
            if cv: 
                item[cv + "s"] -= 1
                if cv == "like" and auth_id in db["users"]: 
                    db["users"][auth_id]["likes_received"] -= 1
                    
            item["voters"][uid] = vote_type
            item[vote_type + "s"] += 1
            
            if vote_type == "like": 
                if auth_id in db["users"]: db["users"][auth_id]["likes_received"] += 1
                notif = f"♥️ *{uname}* оценил твой пост!"
            else:
                notif = f"👎 *{uname}* поставил дизлайк твоему посту."

        save_data(db)
        kb = item_buttons(item_id, item_type, item.get("likes",0), item.get("dislikes",0), auth_id, uid)
        await query.edit_message_reply_markup(reply_markup=kb)
        
        if notif: await notify_author(context, auth_id, notif)
        await query.answer("Голос учтен!")
        return

    if data[0] == "del":
        item_type, item_id = data[1], data[2]
        if item_type == "builds":
            for m in db["builds"]:
                for c in db["builds"][m]:
                    db["builds"][m][c] = [i for i in db["builds"][m][c] if i["id"] != item_id]
        elif isinstance(db[item_type], dict):
            for m in db[item_type]:
                db[item_type][m] = [i for i in db[item_type][m] if i["id"] != item_id]
        else:
            db[item_type] = [i for i in db[item_type] if i["id"] != item_id]
        save_data(db)
        await query.message.delete()
        await query.answer("Удалено!")

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"CoDM Bot Active!")
    def log_message(self, format, *args): return

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    try: HTTPServer(('0.0.0.0', port), DummyHandler).serve_forever()
    except Exception as e: logger.error(f"Ошибка сервера: {e}")

def main():
    if not TOKEN: return
    threading.Thread(target=keep_alive, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", message_router))
    app.add_handler(MessageHandler(filters.PHOTO, process_photos))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
