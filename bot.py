import telebot
from telebot import types
from pymongo import MongoClient
from datetime import datetime, timedelta
import requests

# --- CONFIGURATION ---
API_TOKEN = "8239904642:AAHy0xYu2ogMubj8kuWGtnG8_p5Y9V4eM_w"
CRYPTO_TOKEN = "522389:AAagZEOufX4vVfpNm1ArS506FqHI9DU8aom"
MONGO_URI = "mongodb+srv://admin:Mrpro123@cluster0.vyqetel.mongodb.net/?appName=Cluster0"
CHANNEL_USERNAME = "@GlobalHotgirls_Advertisements" 
ADMIN_ID = 8590099043 

client = MongoClient(MONGO_URI)
db = client['dating_bot_db']
users_col = db['users']
bot = telebot.TeleBot(API_TOKEN)

# --- 1. ACCESS CONTROL ---
def is_joined(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def is_premium(user_id):
    if user_id == ADMIN_ID: return True
    u = users_col.find_one({"id": user_id})
    if u and u.get('is_premium') == 1:
        if datetime.now() > u.get('expiry_date', datetime.min):
            users_col.update_one({"id": user_id}, {"$set": {"is_premium": 0}})
            return False
        return True
    return False

# --- 2. DYNAMIC MENUS ---
def send_menu(chat_id):
    user = users_col.find_one({"id": chat_id})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if not user:
        markup.add("🆕 Create Profile")
    else:
        markup.add("🔍 Find Matches", "👤 My Profile")
        markup.add("🌟 Buy Premium", "🎧 Support")
        if chat_id == ADMIN_ID: markup.add("📊 Stats")
    
    bot.send_message(chat_id, "Main Menu:", reply_markup=markup)

# --- 3. REGISTRATION FLOW ---
@bot.message_handler(func=lambda m: m.text == "🆕 Create Profile")
def start_reg(message):
    if not is_joined(message.chat.id): return start(message)
    bot.send_message(message.chat.id, "Welcome! Enter your Name:")
    bot.register_next_step_handler(message, get_name)

def get_name(message):
    name = message.text
    bot.send_message(message.chat.id, f"Hi {name}, how old are you?")
    bot.register_next_step_handler(message, lambda m: get_photo(m, name))

def get_photo(message, name):
    age = message.text
    bot.send_message(message.chat.id, "Send one profile Photo (Required):")
    bot.register_next_step_handler(message, lambda m: finish_reg(m, name, age))

def finish_reg(message, name, age):
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "🚫 Photo only! Start over.")
        return send_menu(message.chat.id)
    
    users_col.update_one({"id": message.chat.id}, 
                         {"$set": {"name": name, "age": age, "photo": message.photo[-1].file_id, "is_premium": 0, "search_count": 0}}, 
                         upsert=True)
    bot.send_message(message.chat.id, "✅ Profile Created!")
    send_menu(message.chat.id)

# --- 4. COMMANDS & BUTTONS ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_joined(message.chat.id):
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        kb.add(types.InlineKeyboardButton("Verify ✅", callback_data="verify"))
        return bot.send_message(message.chat.id, "🚫 Join our channel first!", reply_markup=kb)
    send_menu(message.chat.id)

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if not is_joined(message.chat.id): return start(message)
    user = users_col.find_one({"id": message.chat.id})

    if message.text == "🔍 Find Matches":
        if not user: return start_reg(message)
        if not is_premium(message.chat.id) and user.get('search_count', 0) >= 10:
            return bot.send_message(message.chat.id, "🚫 Limit reached (10/10). Buy Premium!")
        
        match = list(users_col.aggregate([{"$match": {"id": {"$ne": message.chat.id}}}, {"$sample": {"size": 1}}]))
        if match:
            target = match[0]
            if message.chat.id != ADMIN_ID: users_col.update_one({"id": message.chat.id}, {"$inc": {"search_count": 1}})
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton("👍", callback_data="l"), types.InlineKeyboardButton("❤️", callback_data="l"), types.InlineKeyboardButton("😍", callback_data="l"))
            kb.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="next"))
            bot.send_photo(message.chat.id, target['photo'], caption=f"Name: {target['name']}\nAge: {target['age']}", reply_markup=kb)

    elif message.text == "📊 Stats" and message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, f"📊 Total Users: {users_col.count_documents({})}")

    elif message.text == "👤 My Profile":
        if not user: return start_reg(message)
        is_p = "Yes 🌟" if is_premium(message.chat.id) else "No"
        bot.send_message(message.chat.id, f"👤 **Profile**\nName: {user['name']}\nAge: {user['age']}\nPremium: {is_p}", parse_mode="Markdown")

    elif message.text == "🌟 Buy Premium":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Weekly - $10", callback_data="p_7_10"),
               types.InlineKeyboardButton("Monthly - $30", callback_data="p_30_30"),
               types.InlineKeyboardButton("Yearly - $200", callback_data="p_365_200"))
        bot.send_message(message.chat.id, "💎 Select Plan:", reply_markup=kb)

    elif message.text == "🎧 Support":
        bot.send_message(message.chat.id, "📩 Admin: @Eva_x33")

# --- 5. CALLBACKS (PAYMENT & VERIFY) ---
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "verify":
        if is_joined(call.message.chat.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            send_menu(call.message.chat.id)
    elif call.data.startswith("p_"):
        _, d, p = call.data.split("_")
        res = requests.post("https://pay.crypt.bot/api/createInvoice", json={"asset": "USDT", "amount": p, "description": f"Prem {d}d"}, headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok']:
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Pay", url=res['result']['pay_url']),
                                                  types.InlineKeyboardButton("✅ Verify Payment", callback_data=f"v_{res['result']['invoice_id']}_{d}"))
            bot.send_message(call.message.chat.id, f"Pay ${p} for {d} days:", reply_markup=kb)
    elif call.data.startswith("v_"):
        _, inv_id, d = call.data.split("_")
        res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok'] and res['result']['items'][0]['status'] == 'paid':
            exp = datetime.now() + timedelta(days=int(d))
            users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": exp, "search_count": 0}})
            bot.send_message(call.message.chat.id, "🎉 Premium Active!")

bot.infinity_polling()
