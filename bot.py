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

# --- SECURITY CHECKS ---
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

# --- DYNAMIC KEYBOARD CONTROL (STRICT LOCK) ---
def get_user_keyboard(chat_id):
    user = users_col.find_one({"id": chat_id})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    # 🚨 LOCK: If user doesn't exist in DB, show ONLY registration button
    if not user:
        markup.add("🏞🆕 Create Profile")
    else:
        # Show full menu ONLY for registered users
        markup.add("🔍 Find Matches", "👤 My Profile")
        markup.add("🌟 Buy Premium", "🎧 Support")
        if chat_id == ADMIN_ID:
            markup.add("📊 Stats")
    return markup

# --- REGISTRATION PROCESS (MANDATORY) ---
@bot.message_handler(func=lambda m: m.text == "🏞🆕 Create Profile")
def start_reg(message):
    if not is_joined(message.chat.id): return start_command(message)
    msg = bot.send_message(message.chat.id, "Welcome! Please enter your **Full Name**:")
    bot.register_next_step_handler(msg, reg_age)

def reg_age(message):
    name = message.text
    msg = bot.send_message(message.chat.id, f"Nice to meet you {name}! How **old** are you?")
    bot.register_next_step_handler(msg, lambda m: reg_location(m, name))

def reg_location(message, name):
    age = message.text
    msg = bot.send_message(message.chat.id, "🌎 **Where are you from?** (City/Country):")
    bot.register_next_step_handler(msg, lambda m: reg_photo(m, name, age))

def reg_photo(message, name, age):
    location = message.text
    msg = bot.send_message(message.chat.id, "📸 **Last Step!** Send your Profile Photo (Photos ONLY! No Videos/GIFs):")
    bot.register_next_step_handler(msg, lambda m: finalize_reg(m, name, age, location))

def finalize_reg(message, name, age, location):
    # 🚫 BLOCK: Check if the message content is strictly a photo
    if message.content_type != 'photo':
        msg = bot.send_message(message.chat.id, "🚫 **STRICT RULE:** Only photos are allowed! Send a photo:")
        bot.register_next_step_handler(msg, lambda m: finalize_reg(m, name, age, location))
        return
    
    users_col.update_one({"id": message.chat.id}, 
                         {"$set": {"name": name, "age": age, "location": location, "photo": message.photo[-1].file_id, "is_premium": 0, "search_count": 0}}, 
                         upsert=True)
    bot.send_message(message.chat.id, "🎉 Success! Profile Created. You can now use the bot.", reply_markup=get_user_keyboard(message.chat.id))

# --- CORE HANDLERS ---
@bot.message_handler(commands=['start'])
def start_command(message):
    if not is_joined(message.chat.id):
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Join Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        kb.add(types.InlineKeyboardButton("I have joined ✅", callback_data="verify_join"))
        return bot.send_message(message.chat.id, "🔒 **Access Denied!** You must join our channel first to use this bot.", reply_markup=kb)
    
    bot.send_message(message.chat.id, "Welcome to Global Dating! Please create your profile to continue.", reply_markup=get_user_keyboard(message.chat.id))

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    if not is_joined(message.chat.id): return start_command(message)
    user = users_col.find_one({"id": message.chat.id})

    if message.text == "🔍 Find Matches":
        if not user:
            return bot.send_message(message.chat.id, "❌ **Access Denied!** You must create a profile first.", reply_markup=get_user_keyboard(message.chat.id))
        
        is_p = check_premium(message.chat.id)
        count = user.get('search_count', 0)
        
        # 📊 LIMIT TRACKER
        if not is_p and count >= 10:
            return bot.send_message(message.chat.id, "🚫 **Free Limit Reached (10/10).** Buy Premium to find more matches!")
        
        match = list(users_col.aggregate([{"$match": {"id": {"$ne": message.chat.id}, "photo": {"$exists": True}}}, {"$sample": {"size": 1}}]))
        if match:
            target = match[0]
            if message.chat.id != ADMIN_ID:
                count += 1
                users_col.update_one({"id": message.chat.id}, {"$set": {"search_count": count}})
            
            kb = types.InlineKeyboardMarkup()
            kb.row(types.InlineKeyboardButton("👍", callback_data="l"), types.InlineKeyboardButton("❤️", callback_data="l"), types.InlineKeyboardButton("😍", callback_data="l"))
            kb.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="next_search"))
            
            caption = f"👤 Name: {target['name']}\n🎂 Age: {target['age']}\n📍 Location: {target['location']}"
            if not is_p:
                caption += f"\n\n📊 **Usage:** {count} used, {10-count} searches remaining."
            bot.send_photo(message.chat.id, target['photo'], caption=caption, reply_markup=kb)

    elif message.text == "📊 Stats" and message.chat.id == ADMIN_ID:
        total = users_col.count_documents({})
        bot.send_message(message.chat.id, f"📊 **Bot Stats**\nTotal Users: {total}")

    elif message.text == "🌟 Buy Premium":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Weekly - $2", callback_data="pay_7_2"),
               types.InlineKeyboardButton("Monthly - $7", callback_data="pay_30_7"),
               types.InlineKeyboardButton("Yearly - $200", callback_data="pay_365_200"))
        bot.send_message(message.chat.id, "💎 **Premium Upgrade:**\nGet unlimited searches and full access!", reply_markup=kb)

# --- AUTO-PAYMENT & CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "verify_join":
        if is_joined(call.message.chat.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "✅ Access Granted!", reply_markup=get_user_keyboard(call.message.chat.id))
        else: bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)
    
    elif call.data.startswith("pay_"):
        _, days, price = call.data.split("_")
        res = requests.post("https://pay.crypt.bot/api/createInvoice", json={"asset": "USDT", "amount": price, "description": f"Premium {days}d"}, headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok']:
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("💳 Pay via CryptoBot", url=res['result']['pay_url']),
                                                  types.InlineKeyboardButton("✅ Verify Payment", callback_data=f"checkpay_{res['result']['invoice_id']}_{days}"))
            bot.send_message(call.message.chat.id, f"Upgrade to Premium for {days} days. Price: ${price}", reply_markup=kb)

    elif call.data.startswith("checkpay_"):
        _, inv_id, days = call.data.split("_")
        res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if res['ok'] and res['result']['items'][0]['status'] == 'paid':
            expiry = datetime.now() + timedelta(days=int(days))
            users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": expiry, "search_count": 0}})
            bot.send_message(call.message.chat.id, f"🎉 **Congratulations!** Premium activated until {expiry.strftime('%Y-%m-%d')}.")
        else: bot.answer_callback_query(call.id, "❌ Payment not detected yet.", show_alert=True)

bot.infinity_polling()
