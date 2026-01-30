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
ADMIN_ID = 8590099043  # Your Correct ID

client = MongoClient(MONGO_URI)
db = client['dating_bot_db']
users_col = db['users']
bot = telebot.TeleBot(API_TOKEN)

# --- 1. JOIN CHECK ---
def check_join(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

def force_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Join Channel First 📢", url="https://t.me/GlobalHotgirls_Advertisements"))
    markup.add(types.InlineKeyboardButton("I have joined ✅", callback_data="verify_member"))
    bot.send_message(chat_id, "🚫 **Access Denied!**\nYou must join our channel to use any feature.", reply_markup=markup, parse_mode="Markdown")

# --- 2. PREMIUM & EXPIRY LOGIC ---
def is_premium_user(user_id):
    if user_id == ADMIN_ID: return True
    user = users_col.find_one({"id": user_id})
    if user and user.get('is_premium', 0) == 1:
        expiry = user.get('expiry_date')
        if expiry and datetime.now() > expiry:
            users_col.update_one({"id": user_id}, {"$set": {"is_premium": 0, "search_count": 0}})
            bot.send_message(user_id, "⚠️ Your Premium subscription has expired!")
            return False
        return True
    return False

# --- 3. PHOTO ONLY SECURITY ---
@bot.message_handler(content_types=['video', 'sticker', 'animation', 'document', 'voice', 'video_note'])
def block_media(message):
    bot.reply_to(message, "🚫 **Error:** Only photos are allowed! Videos, GIFs, and stickers are prohibited.")

# --- 4. START & MENU ---
@bot.message_handler(commands=['start'])
def start(message):
    if not check_join(message.chat.id):
        return force_join_msg(message.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Find Matches", "👤 My Profile")
    markup.add("🌟 Buy Premium", "📊 Stats", "🎧 Support")
    bot.send_message(message.chat.id, "Welcome! ❤️ Choose an option:", reply_markup=markup)

# --- 5. SEARCH WITH LIMIT & LIKE BUTTONS ---
@bot.message_handler(func=lambda m: m.text == "🔍 Find Matches")
def find_matches(message):
    if not check_join(message.chat.id): return force_join_msg(message.chat.id)
    
    is_prem = is_premium_user(message.chat.id)
    user = users_col.find_one({"id": message.chat.id})
    search_count = user.get('search_count', 0) if user else 0

    if not is_prem and search_count >= 10:
        bot.send_message(message.chat.id, "🚫 **Limit Reached!** (10/10). Buy Premium for unlimited access.")
        return

    match = list(users_col.aggregate([{"$match": {"id": {"$ne": message.chat.id}}}, {"$sample": {"size": 1}}]))
    if match:
        target = match[0]
        if not is_prem:
            users_col.update_one({"id": message.chat.id}, {"$inc": {"search_count": 1}}, upsert=True)
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("👍", callback_data="l"), types.InlineKeyboardButton("❤️", callback_data="l"), types.InlineKeyboardButton("😍", callback_data="l"))
        markup.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="next_match"))
        
        bot.send_photo(message.chat.id, target['photo'], caption=f"Name: {target['name']}\nAge: {target['age']}", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "No matches found yet!")

# --- 6. AUTOMATED PAYMENT SYSTEM ---
@bot.message_handler(func=lambda m: m.text == "🌟 Buy Premium")
def pay_menu(message):
    if not check_join(message.chat.id): return force_join_msg(message.chat.id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Weekly - $10", callback_data="buy_7"), types.InlineKeyboardButton("Monthly - $30", callback_data="buy_30"))
    markup.add(types.InlineKeyboardButton("Yearly - $200", callback_data="buy_365"))
    bot.send_message(message.chat.id, "💎 **Premium Plans:** Select a plan to upgrade:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def create_invoice(call):
    days = int(call.data.split("_")[1])
    price = 10 if days == 7 else (30 if days == 30 else 200)
    
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    payload = {"asset": "USDT", "amount": str(price), "description": f"Premium {days} days"}
    res = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers).json()
    
    if res['ok']:
        pay_url = res['result']['pay_url']
        inv_id = res['result']['invoice_id']
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Pay via CryptoBot", url=pay_url))
        markup.add(types.InlineKeyboardButton("✅ Check Payment", callback_data=f"check_{inv_id}_{days}"))
        bot.send_message(call.message.chat.id, f"Plan: {days} Days - Price: ${price}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def verify_payment(call):
    _, inv_id, days = call.data.split("_")
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers=headers).json()
    
    if res['ok'] and res['result']['items'][0]['status'] == 'paid':
        expiry = datetime.now() + timedelta(days=int(days))
        users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": expiry, "search_count": 0}}, upsert=True)
        bot.send_message(call.message.chat.id, f"🎉 Success! Premium active until {expiry.strftime('%Y-%m-%d')}.")
    else:
        bot.answer_callback_query(call.id, "❌ Payment not found.", show_alert=True)

# --- 7. OTHER BUTTONS ---
@bot.message_handler(func=lambda m: True)
def other_buttons(message):
    if not check_join(message.chat.id): return force_join_msg(message.chat.id)

    if message.text == "👤 My Profile":
        user = users_col.find_one({"id": message.chat.id})
        is_prem = "Yes 🌟 (Owner)" if message.chat.id == ADMIN_ID else ("Yes 🌟" if is_premium_user(message.chat.id) else "No")
        bot.send_message(message.chat.id, f"👤 **Profile Info**\nName: {user['name'] if user else 'New'}\nPremium: {is_prem}", parse_mode="Markdown")
    
    elif message.text == "📊 Stats":
        bot.send_message(message.chat.id, f"📊 Total Users: {users_col.count_documents({})}")
    
    elif message.text == "🎧 Support":
        bot.send_message(message.chat.id, "📩 Contact Admin: @Eva_x33")

@bot.callback_query_handler(func=lambda call: call.data == "verify_member")
def verify_member(call):
    if check_join(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Join the channel first!", show_alert=True)

bot.infinity_polling()
