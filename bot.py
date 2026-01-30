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
ADMIN_ID = 8590099043 # Your Correct ID (@Eva_x33)

client = MongoClient(MONGO_URI)
db = client['dating_bot_db']
users_col = db['users']
bot = telebot.TeleBot(API_TOKEN)

# --- HELPER: CHECK JOIN & PREMIUM EXPIRE ---
def is_member(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def check_and_get_premium(user_id):
    if user_id == ADMIN_ID: return True
    user = users_col.find_one({"id": user_id})
    if user and user.get('is_premium', 0) == 1:
        expiry = user.get('expiry_date')
        if expiry and datetime.now() > expiry:
            users_col.update_one({"id": user_id}, {"$set": {"is_premium": 0, "search_count": 0}})
            bot.send_message(user_id, "⚠️ Your Premium has expired. Please renew.")
            return False
        return True
    return False

# --- MAIN MENU (STATS IS ADMIN ONLY) ---
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Find Matches", "👤 My Profile")
    markup.add("🌟 Buy Premium", "🎧 Support")
    if chat_id == ADMIN_ID: markup.add("📊 Stats")
    bot.send_message(chat_id, "Welcome! Select an option:", reply_markup=markup)

# --- START & PROFILE CREATION ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_member(message.chat.id):
        btn = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Join Channel 📢", url="https://t.me/GlobalHotgirls_Advertisements"))
        return bot.send_message(message.chat.id, "🚫 Join our channel first to use the bot!", reply_markup=btn)
    
    user = users_col.find_one({"id": message.chat.id})
    if not user:
        msg = bot.send_message(message.chat.id, "Welcome! What is your name?")
        bot.register_next_step_handler(msg, reg_age)
    else: main_menu(message.chat.id)

def reg_age(message):
    name = message.text
    msg = bot.send_message(message.chat.id, f"Hello {name}, how old are you?")
    bot.register_next_step_handler(msg, lambda m: reg_photo(m, name))

def reg_photo(message, name):
    age = message.text
    msg = bot.send_message(message.chat.id, "Send one profile Photo (Required):")
    bot.register_next_step_handler(msg, lambda m: save_user(m, name, age))

def save_user(message, name, age):
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "🚫 Error: Send a photo!")
        bot.register_next_step_handler(msg, lambda m: save_user(m, name, age))
        return
    users_col.update_one({"id": message.chat.id}, {"$set": {"name": name, "age": age, "photo": message.photo[-1].file_id, "is_premium": 0, "search_count": 0}}, upsert=True)
    bot.send_message(message.chat.id, "✅ Profile Created!")
    main_menu(message.chat.id)

# --- ADVANCED PAYMENT SYSTEM ---
@bot.message_handler(func=lambda m: m.text == "🌟 Buy Premium")
def pay_plans(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Weekly - $10", callback_data="buy_7_10"),
           types.InlineKeyboardButton("Monthly - $30", callback_data="buy_30_30"))
    kb.add(types.InlineKeyboardButton("Yearly - $200", callback_data="buy_365_200"))
    bot.send_message(message.chat.id, "💎 Select a Plan:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def create_invoice(call):
    _, days, price = call.data.split("_")
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    payload = {"asset": "USDT", "amount": price, "description": f"Premium {days} days"}
    res = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers).json()
    if res['ok']:
        btn = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Pay Now", url=res['result']['pay_url']),
                                              types.InlineKeyboardButton("✅ Verify", callback_data=f"v_{res['result']['invoice_id']}_{days}"))
        bot.send_message(call.message.chat.id, f"Plan: {days} Days\nPrice: ${price}\nAfter paying, click Verify.", reply_markup=btn)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_"))
def verify_p(call):
    _, inv_id, days = call.data.split("_")
    res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
    if res['ok'] and res['result']['items'][0]['status'] == 'paid':
        exp = datetime.now() + timedelta(days=int(days))
        users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": exp, "search_count": 0}})
        bot.send_message(call.message.chat.id, f"🎉 Premium Activated until {exp.strftime('%Y-%m-%d')}!")
    else: bot.answer_callback_query(call.id, "❌ Not paid yet.", show_alert=True)

# --- ADMIN STATS & RESTRICTIONS ---
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if not is_member(message.chat.id): return
    if message.text == "📊 Stats" and message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, f"📊 Total Users: {users_col.count_documents({})}")
    elif message.text == "👤 My Profile":
        u = users_col.find_one({"id": message.chat.id})
        is_p = "Yes 🌟" if check_and_get_premium(message.chat.id) else "No"
        bot.send_message(message.chat.id, f"👤 **Profile**\nName: {u['name']}\nPremium: {is_p}")
    elif message.text == "🎧 Support":
        bot.send_message(message.chat.id, "📩 Admin: @Eva_x33")
    elif message.text == "🔍 Find Matches":
        # Search logic with 10 limit (previous version)
        bot.send_message(message.chat.id, "Searching...")

bot.infinity_polling()
