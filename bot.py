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

# --- SECURITY HELPERS ---
def is_joined(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

def check_premium(user_id):
    if user_id == ADMIN_ID: return True
    u = users_col.find_one({"id": user_id})
    if u and u.get('is_premium') == 1:
        if datetime.now() > u.get('expiry_date', datetime.min):
            users_col.update_one({"id": user_id}, {"$set": {"is_premium": 0}})
            return False
        return True
    return False

# --- DYNAMIC KEYBOARD (THE LOCK) ---
def get_user_keyboard(chat_id):
    user = users_col.find_one({"id": chat_id})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # 🚨 STRICT LOCK: If user has NO photo or NO gender, force "Create Profile"
    if not user or "photo" not in user or "gender" not in user:
        markup.add("🏞🆕 Create Profile")
    else:
        # Full menu ONLY for registered users
        markup.add("🔍 Find Matches", "👤 My Profile")
        markup.add("🌟 Buy Premium", "🎧 Support")
        if chat_id == ADMIN_ID: markup.add("📊 Stats")
    return markup

# --- CORE MATCH FUNCTION ---
def send_match(chat_id):
    user = users_col.find_one({"id": chat_id})
    is_p = check_premium(chat_id)
    count = user.get('search_count', 0)

    if not is_p and count >= 10:
        return bot.send_message(chat_id, "🚫 Limit reached (10/10). Buy Premium to find more!")

    # Find random user with photo and gender
    match = list(users_col.aggregate([{"$match": {"id": {"$ne": chat_id}, "photo": {"$exists": True}, "gender": {"$exists": True}}}, {"$sample": {"size": 1}}]))
    
    if match:
        target = match[0]
        if chat_id != ADMIN_ID:
            count += 1
            users_col.update_one({"id": chat_id}, {"$set": {"search_count": count}})
        
        kb = types.InlineKeyboardMarkup()
        # ❤️ Like Buttons Fix
        kb.row(types.InlineKeyboardButton("👍", callback_data="l_act"), 
               types.InlineKeyboardButton("❤️", callback_data="l_act"), 
               types.InlineKeyboardButton("😍", callback_data="l_act"))
        # ➡️ Next Match Button Fix
        kb.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="next_p"))
        
        caption = f"👤 Name: {target['name']}\n⚧ Gender: {target['gender']}\n🎂 Age: {target['age']}\n📍 Location: {target['location']}"
        if not is_p:
            caption += f"\n\n📊 Usage: {count}/10 used. {10-count} remaining."
        bot.send_photo(chat_id, target['photo'], caption=caption, reply_markup=kb)
    else:
        bot.send_message(chat_id, "No more matches found.")

# --- REGISTRATION (MANDATORY FOR ALL) ---
@bot.message_handler(func=lambda m: m.text == "🏞🆕 Create Profile")
def start_reg(message):
    if not is_joined(message.chat.id): return start_command(message)
    msg = bot.send_message(message.chat.id, "Welcome! Please enter your **Full Name**:")
    bot.register_next_step_handler(msg, reg_gender)

def reg_gender(message):
    name = message.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Male 👨", "Female 👩")
    msg = bot.send_message(message.chat.id, f"Nice to meet you {name}! Please select your **Gender**:", reply_markup=kb)
    bot.register_next_step_handler(msg, lambda m: reg_age(m, name))

def reg_age(message, name):
    gender = message.text
    msg = bot.send_message(message.chat.id, "How **old** are you?", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, lambda m: reg_location(m, name, gender))

def reg_location(message, name, gender):
    age = message.text
    msg = bot.send_message(message.chat.id, "🌎 **Where are you from?** (City/Country):")
    bot.register_next_step_handler(msg, lambda m: reg_photo(m, name, gender, age))

def reg_photo(message, name, gender, age):
    location = message.text
    msg = bot.send_message(message.chat.id, "📸 **Last Step!** Send your Profile Photo (Photos ONLY!):")
    bot.register_next_step_handler(msg, lambda m: finalize_reg(m, name, gender, age, location))

def finalize_reg(message, name, gender, age, location):
    # 🚫 NO VIDEOS/GIFS ALLOWED
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "🚫 Only Photos are allowed! Try again:")
        bot.register_next_step_handler(msg, lambda m: finalize_reg(m, name, gender, age, location))
        return
    
    users_col.update_one({"id": message.chat.id}, 
                         {"$set": {"name": name, "gender": gender, "age": age, "location": location, "photo": message.photo[-1].file_id, "is_premium": 0, "search_count": 0}}, 
                         upsert=True)
    bot.send_message(message.chat.id, "🎉 Success! Your profile is ready.", reply_markup=get_user_keyboard(message.chat.id))

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_joined(message.chat.id):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        kb.add(types.InlineKeyboardButton("I have joined ✅", callback_data="v_join"))
        return bot.send_message(message.chat.id, "🔒 **Access Denied!** Join our channel first.", reply_markup=kb)
    
    bot.send_message(message.chat.id, "Welcome to the bot!", reply_markup=get_user_keyboard(message.chat.id))

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if not is_joined(message.chat.id): return start_command(message)
    user = users_col.find_one({"id": message.chat.id})

    if message.text == "🔍 Find Matches":
        # Check if even old users have full profiles
        if not user or "photo" not in user or "gender" not in user:
            return bot.send_message(message.chat.id, "❌ Profile Incomplete! Please create one.", reply_markup=get_user_keyboard(message.chat.id))
        send_match(message.chat.id)

    elif message.text == "📊 Stats" and message.chat.id == ADMIN_ID:
        total = users_col.count_documents({})
        bot.send_message(message.chat.id, f"📊 Total Users: {total}")

    elif message.text == "🌟 Buy Premium":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Weekly - $2", callback_data="pay_7_2"),
               types.InlineKeyboardButton("Monthly - $7", callback_data="pay_30_7"),
               types.InlineKeyboardButton("Yearly - $200", callback_data="pay_365_200"))
        bot.send_message(message.chat.id, "💎 Upgrade for Unlimited Matches:", reply_markup=kb)

# --- CALLBACKS (FIXED BUTTONS) ---
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "v_join":
        if is_joined(call.message.chat.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ Access Granted!", reply_markup=get_user_keyboard(call.message.chat.id))
    
    elif call.data == "next_p":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_match(call.message.chat.id)
    
    elif call.data == "l_act":
        bot.answer_callback_query(call.id, "You liked this profile! ❤️")

    elif call.data.startswith("pay_"):
        _, d, p = call.data.split("_")
        res = requests.post("https://pay.crypt.bot/api/createInvoice", json={"asset": "USDT", "amount": p, "description": f"Premium {d}d"}, headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok']:
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Pay via CryptoBot", url=res['result']['pay_url']),
                                                  types.InlineKeyboardButton("✅ Verify Payment", callback_data=f"chk_{res['result']['invoice_id']}_{d}"))
            bot.send_message(call.message.chat.id, f"Pay ${p} for {d} days:", reply_markup=kb)

    elif call.data.startswith("chk_"):
        _, inv_id, d = call.data.split("_")
        res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok'] and res['result']['items'][0]['status'] == 'paid':
            expiry = datetime.now() + timedelta(days=int(d))
            users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": expiry, "search_count": 0}})
            bot.send_message(call.message.chat.id, "🎉 Premium Activated! Unlimited searches unlocked.")

bot.infinity_polling()
