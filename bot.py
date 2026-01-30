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

# --- ACCESS CONTROL ---
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

# --- DYNAMIC MENUS ---
def send_main_menu(chat_id):
    user = users_col.find_one({"id": chat_id})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    if not user:
        markup.add("🆕 Create Profile")
    else:
        markup.add("🔍 Find Matches", "👤 My Profile")
        markup.add("🌟 Buy Premium", "🎧 Support")
        if chat_id == ADMIN_ID: markup.add("📊 Stats")
    
    bot.send_message(chat_id, "✨ Main Menu:", reply_markup=markup)

# --- REGISTRATION PROCESS ---
@bot.message_handler(func=lambda m: m.text == "🆕 Create Profile")
def reg_start(message):
    if not is_joined(message.chat.id): return start(message)
    msg = bot.send_message(message.chat.id, "Welcome! What is your Name?")
    bot.register_next_step_handler(msg, reg_age)

def reg_age(message):
    name = message.text
    msg = bot.send_message(message.chat.id, f"Nice to meet you {name}! How old are you?")
    bot.register_next_step_handler(msg, lambda m: reg_location(m, name))

def reg_location(message, name):
    age = message.text
    msg = bot.send_message(message.chat.id, "🌎 Which city/location are you from?")
    bot.register_next_step_handler(msg, lambda m: reg_photo(m, name, age))

def reg_photo(message, name, age):
    location = message.text
    msg = bot.send_message(message.chat.id, "📸 Send your Profile Photo (Photos only!):")
    bot.register_next_step_handler(msg, lambda m: reg_finish(m, name, age, location))

def reg_finish(message, name, age, location):
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "🚫 Error: Only photos are allowed! Send a photo:")
        bot.register_next_step_handler(msg, lambda m: reg_finish(m, name, age, location))
        return
    
    users_col.update_one({"id": message.chat.id}, 
                         {"$set": {"name": name, "age": age, "location": location, "photo": message.photo[-1].file_id, "is_premium": 0, "search_count": 0}}, 
                         upsert=True)
    bot.send_message(message.chat.id, "✅ Profile Created Successfully!")
    send_main_menu(message.chat.id)

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_joined(message.chat.id):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        kb.add(types.InlineKeyboardButton("I have joined ✅", callback_data="verify"))
        return bot.send_message(message.chat.id, "🔒 Access Locked! Please join our channel first to use this bot.", reply_markup=kb)
    send_main_menu(message.chat.id)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if not is_joined(message.chat.id): return start(message)
    user = users_col.find_one({"id": message.chat.id})

    if message.text == "🔍 Find Matches":
        if not user: return bot.send_message(message.chat.id, "⚠️ Please create a profile first!", reply_markup=get_main_menu(message.chat.id))
        
        is_p = is_premium(message.chat.id)
        count = user.get('search_count', 0)
        if not is_p and count >= 10:
            return bot.send_message(message.chat.id, "🚫 Free limit reached (10/10). Please buy Premium for unlimited access!")
        
        match = list(users_col.aggregate([{"$match": {"id": {"$ne": message.chat.id}}}, {"$sample": {"size": 1}}]))
        if match:
            target = match[0]
            if message.chat.id != ADMIN_ID:
                count += 1
                users_col.update_one({"id": message.chat.id}, {"$set": {"search_count": count}})
            
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton("👍", callback_data="l"), types.InlineKeyboardButton("❤️", callback_data="l"), types.InlineKeyboardButton("😍", callback_data="l"))
            kb.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="next"))
            
            caption = f"👤 Name: {target['name']}\n🎂 Age: {target['age']}\n📍 Location: {target['location']}"
            if not is_p: caption += f"\n\n📊 Usage: {count}/10 searches used."
            
            bot.send_photo(message.chat.id, target['photo'], caption=caption, reply_markup=kb)
        else:
            bot.send_message(message.chat.id, "No matches found yet.")

    elif message.text == "📊 Stats" and message.chat.id == ADMIN_ID:
        bot.send_message(message.chat.id, f"📊 Total Bot Users: {users_col.count_documents({})}")

    elif message.text == "👤 My Profile":
        if not user: return reg_start(message)
        status = "Premium 🌟" if is_premium(message.chat.id) else "Free User"
        bot.send_message(message.chat.id, f"👤 **My Profile**\nName: {user['name']}\nAge: {user['age']}\nLocation: {user['location']}\nStatus: {status}")

    elif message.text == "🌟 Buy Premium":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Weekly - $10", callback_data="p_7_10"),
               types.InlineKeyboardButton("Monthly - $30", callback_data="p_30_30"),
               types.InlineKeyboardButton("Yearly - $200", callback_data="p_365_200"))
        bot.send_message(message.chat.id, "💎 Upgrade to Premium for unlimited matches:", reply_markup=kb)

    elif message.text == "🎧 Support":
        bot.send_message(message.chat.id, "📩 For help, contact: @Eva_x33")

# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_calls(call):
    if call.data == "verify":
        if is_joined(call.message.chat.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            send_main_menu(call.message.chat.id)
    elif call.data.startswith("p_"):
        _, d, p = call.data.split("_")
        res = requests.post("https://pay.crypt.bot/api/createInvoice", json={"asset": "USDT", "amount": p, "description": f"Premium {d} days"}, headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok']:
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Pay via CryptoBot", url=res['result']['pay_url']),
                                                  types.InlineKeyboardButton("✅ Verify Payment", callback_data=f"v_{res['result']['invoice_id']}_{d}"))
            bot.send_message(call.message.chat.id, f"Upgrade to Premium ({d} days) for ${p}:", reply_markup=kb)
    elif call.data.startswith("v_"):
        _, inv_id, d = call.data.split("_")
        res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok'] and res['result']['items'][0]['status'] == 'paid':
            expiry = datetime.now() + timedelta(days=int(d))
            users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": expiry, "search_count": 0}})
            bot.send_message(call.message.chat.id, f"🎉 Success! Premium active until {expiry.strftime('%Y-%m-%d')}.")

bot.infinity_polling()
