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
ADMIN_ID = 8590099043 # Your Correct ID

client = MongoClient(MONGO_URI)
db = client['dating_bot_db']
users_col = db['users']
bot = telebot.TeleBot(API_TOKEN)

# --- 1. STRICT JOIN FORCE CHECK ---
def is_joined(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def send_join_request(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Join Channel 📢", url="https://t.me/GlobalHotgirls_Advertisements"))
    markup.add(types.InlineKeyboardButton("I have joined ✅", callback_data="verify_member"))
    bot.send_message(chat_id, "Welcome! Please join our channel to use the bot.", reply_markup=markup)

# --- 2. PREMIUM & EXPIRY LOGIC ---
def get_premium_status(user_id):
    if user_id == ADMIN_ID: return True
    user = users_col.find_one({"id": user_id})
    if user and user.get('is_premium', 0) == 1:
        expiry = user.get('expiry_date')
        if expiry and datetime.now() > expiry:
            users_col.update_one({"id": user_id}, {"$set": {"is_premium": 0, "search_count": 0}})
            bot.send_message(user_id, "⚠️ Your Premium has expired. Please renew!")
            return False
        return True
    return False

# --- 3. DYNAMIC MENU (STATS ONLY FOR ADMIN) ---
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    user = users_col.find_one({"id": chat_id})
    
    if not user:
        markup.add("🆕 Create Profile")
    else:
        markup.add("🔍 Find Matches", "👤 My Profile")
        markup.add("🌟 Buy Premium", "🎧 Support")
        if chat_id == ADMIN_ID: # Only you see this
            markup.add("📊 Stats")
    bot.send_message(chat_id, "Main Menu:", reply_markup=markup)

# --- 4. START & REGISTRATION ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_joined(message.chat.id):
        return send_join_request(message.chat.id)
    main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🆕 Create Profile")
def start_reg(message):
    msg = bot.send_message(message.chat.id, "What is your Name?")
    bot.register_next_step_handler(msg, get_name)

def get_name(message):
    name = message.text
    msg = bot.send_message(message.chat.id, "How old are you?")
    bot.register_next_step_handler(msg, lambda m: get_age(m, name))

def get_age(message, name):
    age = message.text
    msg = bot.send_message(message.chat.id, "Send your Profile Photo (Photos only!):")
    bot.register_next_step_handler(msg, lambda m: save_profile(m, name, age))

def save_profile(message, name, age):
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "🚫 Error: Please send a Photo only!")
        bot.register_next_step_handler(msg, lambda m: save_profile(m, name, age))
        return
    users_col.update_one({"id": message.chat.id}, {"$set": {"name": name, "age": age, "photo": message.photo[-1].file_id, "is_premium": 0, "search_count": 0}}, upsert=True)
    bot.send_message(message.chat.id, "✅ Profile Created!")
    main_menu(message.chat.id)

# --- 5. SEARCH WITH LIMIT & LIKE BUTTONS ---
@bot.message_handler(func=lambda m: m.text == "🔍 Find Matches")
def search(message):
    if not is_joined(message.chat.id): return send_join_request(message.chat.id)
    
    is_prem = get_premium_status(message.chat.id)
    user = users_col.find_one({"id": message.chat.id})
    if not is_prem and user.get('search_count', 0) >= 10:
        return bot.send_message(message.chat.id, "🚫 Limit reached (10/10). Buy Premium!")

    match = list(users_col.aggregate([{"$match": {"id": {"$ne": message.chat.id}}}, {"$sample": {"size": 1}}]))
    if match:
        target = match[0]
        if not is_prem: users_col.update_one({"id": message.chat.id}, {"$inc": {"search_count": 1}})
        
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("👍", callback_data="l"), types.InlineKeyboardButton("❤️", callback_data="l"), types.InlineKeyboardButton("😍", callback_data="l"))
        kb.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="next_match"))
        bot.send_photo(message.chat.id, target['photo'], caption=f"Name: {target['name']}\nAge: {target['age']}", reply_markup=kb)

# --- 6. ADVANCED AUTO-PAYMENT ---
@bot.message_handler(func=lambda m: m.text == "🌟 Buy Premium")
def pay_plans(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Weekly - $10", callback_data="p_7_10"),
           types.InlineKeyboardButton("Monthly - $30", callback_data="p_30_30"))
    kb.add(types.InlineKeyboardButton("Yearly - $200", callback_data="p_365_200"))
    bot.send_message(message.chat.id, "💎 Select your plan:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("p_"))
def create_inv(call):
    _, days, price = call.data.split("_")
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    payload = {"asset": "USDT", "amount": price, "description": f"Premium {days} days"}
    res = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers).json()
    if res['ok']:
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Pay Now", url=res['result']['pay_url']),
                                              types.InlineKeyboardButton("✅ Verify", callback_data=f"v_{res['result']['invoice_id']}_{days}"))
        bot.send_message(call.message.chat.id, f"Plan: {days} Days. Price: ${price}. Pay and click Verify:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("v_"))
def check_pay(call):
    _, inv_id, days = call.data.split("_")
    res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
    if res['ok'] and res['result']['items'][0]['status'] == 'paid':
        exp = datetime.now() + timedelta(days=int(days))
        users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": exp, "search_count": 0}})
        bot.send_message(call.message.chat.id, f"🎉 Premium Activated until {exp.strftime('%Y-%m-%d')}!")
    else: bot.answer_callback_query(call.id, "❌ Not paid yet.", show_alert=True)

# --- 7. ADMIN STATS & HANDLER ---
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    if not is_joined(message.chat.id): return
    if message.text == "📊 Stats" and message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, f"📊 Total Users: {users_col.count_documents({})}")
    elif message.text == "👤 My Profile":
        u = users_col.find_one({"id": message.chat.id})
        is_p = "Yes 🌟" if get_premium_status(message.chat.id) else "No"
        bot.send_message(message.chat.id, f"👤 Profile: {u['name']}\nAge: {u['age']}\nPremium: {is_p}")
    elif message.text == "🎧 Support":
        bot.send_message(message.chat.id, "📩 Support: @Eva_x33")

@bot.callback_query_handler(func=lambda call: call.data == "verify_member")
def verify_m(call):
    if is_joined(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        main_menu(call.message.chat.id)
    else: bot.answer_callback_query(call.id, "❌ Join the channel first!", show_alert=True)

bot.infinity_polling()
