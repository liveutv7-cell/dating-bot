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

# --- SECURITY & PERMISSIONS ---
def is_joined(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def is_banned(user_id):
    user = users_col.find_one({"id": user_id})
    return user.get('banned', False) if user else False

def check_premium(user_id):
    if user_id == ADMIN_ID: return True
    u = users_col.find_one({"id": user_id})
    if u and u.get('is_premium') == 1:
        if datetime.now() > u.get('expiry_date', datetime.min):
            users_col.update_one({"id": user_id}, {"$set": {"is_premium": 0}})
            return False
        return True
    return False

# --- DYNAMIC KEYBOARD (THE LOCK SYSTEM) ---
def get_main_keyboard(chat_id):
    user = users_col.find_one({"id": chat_id})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # Force profile creation for EVERYONE (Old and New)
    if not user or "photo" not in user or "gender" not in user:
        markup.add("🏞🆕 Create Profile")
    else:
        markup.add("🔍 Find Matches", "👤 My Profile")
        markup.add("🌟 Buy Premium", "🎧 Support")
        if chat_id == ADMIN_ID: markup.add("📊 Stats")
    return markup

# --- REGISTRATION FLOW (STRICT) ---
@bot.message_handler(func=lambda m: m.text == "🏞🆕 Create Profile")
def start_registration(message):
    if is_banned(message.chat.id): return
    msg = bot.send_message(message.chat.id, "Welcome! Please enter your **Full Name**:")
    bot.register_next_step_handler(msg, process_name)

def process_name(message):
    name = message.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Male 🧑", "Female 👩")
    msg = bot.send_message(message.chat.id, "Select your Gender:", reply_markup=kb)
    bot.register_next_step_handler(msg, lambda m: process_gender(m, name))

def process_gender(message, name):
    gender = message.text
    if gender not in ["Male 🧑", "Female 👩"]:
        return start_registration(message)
    msg = bot.send_message(message.chat.id, "How old are you?", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, lambda m: process_age(m, name, gender))

def process_age(message, name, gender):
    age = message.text
    msg = bot.send_message(message.chat.id, "🌎 Where are you from? (Location):")
    bot.register_next_step_handler(msg, lambda m: process_location(m, name, gender, age))

def process_location(message, name, gender, age):
    loc = message.text
    msg = bot.send_message(message.chat.id, "📸 Send your Profile Photo (Photos only! No Video/GIF):")
    bot.register_next_step_handler(msg, lambda m: process_photo(m, name, gender, age, loc))

def process_photo(message, name, gender, age, loc):
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "🚫 ERROR: Only Photos allowed! Send a photo:")
        bot.register_next_step_handler(msg, lambda m: process_photo(m, name, gender, age, loc))
        return
    
    users_col.update_one({"id": message.chat.id}, 
                         {"$set": {"name": name, "gender": gender, "age": age, "location": loc, "photo": message.photo[-1].file_id, "search_count": 0, "is_premium": 0, "banned": False}}, 
                         upsert=True)
    bot.send_message(message.chat.id, "✅ Profile Created Successfully!", reply_markup=get_main_keyboard(message.chat.id))

# --- MATCHING LOGIC ---
def send_match(chat_id):
    user = users_col.find_one({"id": chat_id})
    is_p = check_premium(chat_id)
    count = user.get('search_count', 0)

    if not is_p and count >= 10:
        return bot.send_message(chat_id, "🚫 Free Limit Reached (10/10). Upgrade to Premium!")

    match = list(users_col.aggregate([{"$match": {"id": {"$ne": chat_id}, "photo": {"$exists": True}, "banned": {"$ne": True}}}, {"$sample": {"size": 1}}]))
    
    if match:
        target = match[0]
        if chat_id != ADMIN_ID:
            count += 1
            users_col.update_one({"id": chat_id}, {"$set": {"search_count": count}})

        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("👍", callback_data="like"), types.InlineKeyboardButton("❤️", callback_data="like"), types.InlineKeyboardButton("😍", callback_data="like"))
        kb.add(types.InlineKeyboardButton("🗨️ Send Message", url=f"tg://user?id={target['id']}"))
        kb.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="btn_next"))
        
        if chat_id == ADMIN_ID:
            kb.add(types.InlineKeyboardButton("🚫 BAN USER", callback_data=f"admin_ban_{target['id']}"))

        cap = f"👤 Name: {target['name']}\n⚧ Gender: {target['gender']}\n🎂 Age: {target['age']}\n📍 Location: {target['location']}"
        if not is_p: cap += f"\n\n📊 Usage: {count}/10 used. ({10-count} remaining)"
        
        bot.send_photo(chat_id, target['photo'], caption=cap, reply_markup=kb)
    else:
        bot.send_message(chat_id, "No matches found. Try again later.")

# --- BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def start(message):
    if is_banned(message.chat.id):
        return bot.send_message(message.chat.id, "🚫 You are banned.")
    if not is_joined(message.chat.id):
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"), types.InlineKeyboardButton("I have joined ✅", callback_data="check_v"))
        return bot.send_message(message.chat.id, "🔒 Join our channel to use the bot:", reply_markup=kb)
    
    bot.send_message(message.chat.id, "Welcome back!", reply_markup=get_main_keyboard(message.chat.id))

@bot.message_handler(func=lambda m: True)
def handle_all_text(message):
    if is_banned(message.chat.id): return
    if not is_joined(message.chat.id): return start(message)
    
    user = users_col.find_one({"id": message.chat.id})
    # STRICT CHECK: If no profile, they can only see "Create Profile" button
    if not user or "photo" not in user:
        if message.text == "🏞🆕 Create Profile": return start_registration(message)
        return bot.send_message(message.chat.id, "🔒 You must create a profile first!", reply_markup=get_main_keyboard(message.chat.id))

    if message.text == "🔍 Find Matches":
        send_match(message.chat.id)
    elif message.text == "👤 My Profile":
        bot.send_photo(message.chat.id, user['photo'], caption=f"Your Profile:\nName: {user['name']}\nStatus: {'Premium' if check_premium(message.chat.id) else 'Free'}")
    elif message.text == "📊 Stats" and message.chat.id == ADMIN_ID:
        total = users_col.count_documents({})
        bot.send_message(ADMIN_ID, f"📊 Total Bot Users: {total}")
    elif message.text == "🌟 Buy Premium":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Weekly - $2", callback_data="pay_7_2"),
               types.InlineKeyboardButton("Monthly - $7", callback_data="pay_30_7"),
               types.InlineKeyboardButton("Yearly - $200", callback_data="pay_365_200"))
        bot.send_message(message.chat.id, "💎 Choose your Premium Plan:", reply_markup=kb)

# --- CALLBACK ACTIONS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "check_v":
        if is_joined(call.message.chat.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ Access Granted!", reply_markup=get_main_keyboard(call.message.chat.id))
    
    elif call.data == "btn_next":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_match(call.message.chat.id)
    
    elif call.data == "like":
        bot.answer_callback_query(call.id, "Reaction Sent! ✨")

    elif call.data.startswith("admin_ban_"):
        uid = int(call.data.split("_")[2])
        users_col.update_one({"id": uid}, {"$set": {"banned": True}})
        bot.answer_callback_query(call.id, "User Banned & Removed! ❌", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_match(call.message.chat.id)

    elif call.data.startswith("pay_"):
        _, days, price = call.data.split("_")
        res = requests.post("https://pay.crypt.bot/api/createInvoice", json={"asset": "USDT", "amount": price, "description": f"Premium {days} Days"}, headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok']:
            inv_id = res['result']['invoice_id']
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Pay Now", url=res['result']['pay_url']), types.InlineKeyboardButton("✅ Verify Payment", callback_data=f"chk_{inv_id}_{days}"))
            bot.send_message(call.message.chat.id, f"To upgrade, pay ${price} USDT:", reply_markup=kb)

    elif call.data.startswith("chk_"):
        _, inv_id, days = call.data.split("_")
        check = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if check['ok'] and check['result']['items'][0]['status'] == 'paid':
            expiry = datetime.now() + timedelta(days=int(days))
            users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": expiry, "search_count": 0}})
            bot.send_message(call.message.chat.id, "🎉 Congratulations! You are now a Premium Member! 🌟")

bot.infinity_polling()
