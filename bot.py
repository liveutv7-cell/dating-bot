import telebot
from telebot import types
from pymongo import MongoClient
from datetime import datetime, timedelta
import requests

# --- CONFIGURATION ---
API_TOKEN = "8239904642:AAHy0xYu2ogMubj8kuWGtnG8_p5Y9V4eM_w"
CRYPTO_TOKEN = "522389:AAagZEOufX4vVfpNm1ArS506FqHI9DU8aom" # Your Token added
MONGO_URI = "mongodb+srv://admin:Mrpro123@cluster0.vyqetel.mongodb.net/?appName=Cluster0"
CHANNEL_USERNAME = "@GlobalHotgirls_Advertisements" 
ADMIN_ID = 8593628479 

client = MongoClient(MONGO_URI)
db = client['dating_bot_db']
users_col = db['users']
bot = telebot.TeleBot(API_TOKEN)

# --- 1. SUBSCRIPTION CHECK ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True

# --- 2. PREMIUM STATUS & EXPIRY CHECK ---
def get_status(user_id):
    if user_id == ADMIN_ID:
        return True
    user = users_col.find_one({"id": user_id})
    if user and user.get('is_premium', 0) == 1:
        expiry = user.get('expiry_date')
        if expiry and datetime.now() > expiry:
            users_col.update_one({"id": user_id}, {"$set": {"is_premium": 0, "search_count": 0}})
            bot.send_message(user_id, "⚠️ Your Premium has expired. Please renew to continue!")
            return False
        return True
    return False

# --- 3. SECURITY: ONLY PHOTOS ALLOWED ---
@bot.message_handler(content_types=['video', 'sticker', 'animation', 'document', 'voice'])
def block_media(message):
    bot.reply_to(message, "🚫 Access Denied: Only Photos are allowed for profile creation!")

# --- 4. START & MENU ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_subscribed(message.chat.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Join Channel", url="https://t.me/GlobalHotgirls_Advertisements"))
        bot.send_message(message.chat.id, "❗ Join our channel first to use the bot:", reply_markup=markup)
        return
    
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu.add("🔍 Find Matches", "👤 My Profile")
    menu.add("🌟 Buy Premium", "📊 Stats", "🎧 Support")
    bot.send_message(message.chat.id, "Welcome to Global Dating! ❤️", reply_markup=menu)

# --- 5. SEARCH WITH LIMIT ---
@bot.message_handler(func=lambda m: m.text == "🔍 Find Matches")
def find_matches(message):
    is_prem = get_status(message.chat.id)
    user = users_col.find_one({"id": message.chat.id})
    
    if not is_prem and user and user.get('search_count', 0) >= 10:
        bot.send_message(message.chat.id, "🚫 Limit Reached (10/10). Upgrade to Premium for unlimited access!")
        return

    match = list(users_col.aggregate([{"$match": {"id": {"$ne": message.chat.id}}}, {"$sample": {"size": 1}}]))
    if match:
        target = match[0]
        if not is_prem:
            users_col.update_one({"id": message.chat.id}, {"$inc": {"search_count": 1}})
        
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("😍", callback_data="l"), types.InlineKeyboardButton("❤️", callback_data="l"), types.InlineKeyboardButton("👍", callback_data="l"))
        markup.add(types.InlineKeyboardButton("➡️ Next Match", callback_data="next"))
        bot.send_photo(message.chat.id, target['photo'], caption=f"Name: {target['name']}\nAge: {target['age']}", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "No matches found!")

# --- 6. AUTOMATED PAYMENT SYSTEM ---
@bot.message_handler(func=lambda m: m.text == "🌟 Buy Premium")
def pay_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Weekly - $10", callback_data="buy_7"),
               types.InlineKeyboardButton("Monthly - $30", callback_data="buy_30"))
    markup.add(types.InlineKeyboardButton("Yearly - $200", callback_data="buy_365"))
    bot.send_message(message.chat.id, "💎 Select your Premium Plan:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def create_invoice(call):
    days = int(call.data.split("_")[1])
    price = 10 if days == 7 else (30 if days == 30 else 200)
    
    # Create Invoice via CryptoBot API
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    payload = {"asset": "USDT", "amount": str(price), "description": f"Premium {days} days"}
    res = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers).json()
    
    if res['ok']:
        pay_url = res['result']['pay_url']
        invoice_id = res['result']['invoice_id']
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Pay Now", url=pay_url))
        markup.add(types.InlineKeyboardButton("✅ Verify Payment", callback_data=f"check_{invoice_id}_{days}"))
        bot.send_message(call.message.chat.id, f"Plan: {days} Days\nPrice: ${price}\nPay and click Verify:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def verify(call):
    _, inv_id, days = call.data.split("_")
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    res = requests.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}", headers=headers).json()
    
    if res['ok'] and res['result']['items'][0]['status'] == 'paid':
        expiry = datetime.now() + timedelta(days=int(days))
        users_col.update_one({"id": call.message.chat.id}, {"$set": {"is_premium": 1, "expiry_date": expiry, "search_count": 0}})
        bot.send_message(call.message.chat.id, f"🎉 Success! Premium active until {expiry.strftime('%Y-%m-%d')}.")
    else:
        bot.answer_callback_query(call.id, "❌ Payment not detected yet.")

@bot.message_handler(func=lambda m: m.text == "🎧 Support")
def support(message):
    bot.send_message(message.chat.id, "📩 Admin: @Omar_soner")

bot.infinity_polling()
