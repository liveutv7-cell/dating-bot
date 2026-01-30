import telebot
from telebot import types
from pymongo import MongoClient
import random
import time
import os
import requests
import threading

# --- Configuration ---
# Your provided tokens are now integrated
API_TOKEN = "8239904642:AAHy0xYu2ogMubj8kuWGtnG8_p5Y9V4eM_w"
CRYPTO_PAY_TOKEN = "522389:AAagZEOufX4vVfpNm1ArS506FqHI9DU8aom"

# MongoDB Connection String
MONGO_URI = "mongodb+srv://admin:Mrpro123@cluster0.vyqetel.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['dating_bot_db']
users_col = db['users']

CHANNEL_ID = '@Globalhotgirls_Advertisements'
CHANNEL_LINK = 'https://t.me/Globalhotgirls_Advertisements'
SUPPORT_USER = "@Eva_x33"
ADMIN_ID = 8590099043 

bot = telebot.TeleBot(API_TOKEN)
user_search_data = {} 

# --- Automatic Payment Checker ---
def check_payments():
    while True:
        try:
            headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
            response = requests.get("https://pay.crypt.bot/api/getInvoices?status=paid", headers=headers)
            res_data = response.json()
            
            if res_data.get('ok'):
                items = res_data['result'].get('items', [])
                for inv in items:
                    user_id = int(inv['payload'])
                    # Update to Premium in MongoDB
                    users_col.update_one({"id": user_id}, {"$set": {"is_premium": 1}})
                    try:
                        bot.send_message(user_id, "🌟 PAYMENT CONFIRMED! Your account is now PREMIUM!")
                    except: pass
        except Exception as e:
            print(f"Payment error: {e}")
        time.sleep(30)

# --- CryptoPay Logic ---
def create_invoice(amount, user_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    payload = {'asset': 'USDT', 'amount': str(amount), 'payload': str(user_id)}
    try:
        response = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers)
        return response.json()['result']
    except: return None

# --- Subscription Check ---
def is_subscribed(chat_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, chat_id).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# --- Profile Management ---
@bot.message_handler(func=lambda m: m.text in ["📝 Edit Profile", "Create Profile"])
def create_profile(message):
    bot.send_message(message.chat.id, "What is your Name?")
    bot.register_next_step_handler(message, process_name)

def process_name(message):
    name = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add("Male", "Female")
    bot.send_message(message.chat.id, "Select Gender:", reply_markup=markup)
    bot.register_next_step_handler(message, process_gender, name)

def process_gender(message, name):
    gender = message.text
    bot.send_message(message.chat.id, "Age?")
    bot.register_next_step_handler(message, process_age, name, gender)

def process_age(message, name, gender):
    age = message.text
    bot.send_message(message.chat.id, "City/Location?")
    bot.register_next_step_handler(message, process_location, name, gender, age)

def process_location(message, name, gender, age):
    location = message.text
    bot.send_message(message.chat.id, "Send your Profile Photo:")
    bot.register_next_step_handler(message, process_photo_final, name, gender, age, location)

def process_photo_final(message, name, gender, age, location):
    if message.content_type == 'photo':
        photo_id = message.photo[-1].file_id
        users_col.update_one(
            {"id": message.chat.id},
            {"$set": {"id": message.chat.id, "name": name, "gender": gender, "age": age, "location": location, "photo": photo_id, "is_premium": 0}},
            upsert=True
        )
        bot.send_message(message.chat.id, "✅ Profile Created/Updated Successfully!")
        show_main_menu(message)
    else:
        bot.send_message(message.chat.id, "🚫 Send a photo!")
        bot.register_next_step_handler(message, process_photo_final, name, gender, age, location)

# --- Matching Logic ---
@bot.message_handler(func=lambda m: m.text in ["🔍 Find Matches", "🎲 Random Match"])
def handle_matching(message):
    user_id = message.chat.id
    if not is_subscribed(user_id):
        start(message)
        return

    user_data = users_col.find_one({"id": user_id})
    if not user_data:
        bot.send_message(user_id, "Please create a profile first!", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Create Profile"))
        return

    is_premium = user_data.get('is_premium', 0)
    me_gender = user_data.get('gender')
    
    if not is_premium:
        now = time.time()
        if user_id not in user_search_data:
            user_search_data[user_id] = {'count': 0, 'last_reset': now}
        if user_search_data[user_id]['count'] >= 10:
            bot.send_message(user_id, "🚫 Free limit reached! Upgrade to 🌟 Premium for unlimited matches.")
            return
        user_search_data[user_id]['count'] += 1

    target = "Female" if me_gender == "Male" else "Male"
    matches = list(users_col.find({"id": {"$ne": user_id}, "gender": target}))
    
    if matches:
        row = random.choice(matches)
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("❤️", callback_data=f"react_like_{row['id']}"),
            types.InlineKeyboardButton("👍", callback_data=f"react_thumb_{row['id']}"),
            types.InlineKeyboardButton("😍", callback_data=f"react_fire_{row['id']}")
        )
        markup.add(types.InlineKeyboardButton("💬 Send Message", url=f"tg://user?id={row['id']}"))
        bot.send_photo(user_id, row['photo'], caption=f"Name: {row['name']}\nAge: {row['age']}\nLoc: {row['location']}", reply_markup=markup)
    else:
        bot.send_message(user_id, "No users found. Try again later!")

# --- Premium & Support ---
@bot.message_handler(func=lambda m: m.text == "🌟 Buy Premium")
def premium_plans(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Weekly - $2", callback_data="buy_2"))
    markup.add(types.InlineKeyboardButton("Monthly - $7", callback_data="buy_7"))
    bot.send_message(message.chat.id, "💎 Upgrade for Unlimited Matches!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_buy(call):
    amount = call.data.split("_")[1]
    invoice = create_invoice(amount, call.message.chat.id)
    if invoice:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Pay via CryptoBot", url=invoice['pay_url']))
        bot.send_message(call.message.chat.id, f"✅ Pay ${amount} to unlock Unlimited Access:", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ Error creating invoice.")

@bot.message_handler(func=lambda m: m.text == "📊 Stats")
def show_stats(message):
    count = users_col.count_documents({})
    bot.reply_to(message, f"📊 Total Active Users: {count}")

@bot.message_handler(func=lambda m: m.text == "🛠 Support")
def support_info(message):
    bot.send_message(message.chat.id, f"Need help? Contact Admin: {SUPPORT_USER}")

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Find Matches", "🎲 Random Match")
    markup.add("👤 My Profile", "🌟 Buy Premium")
    markup.add("📊 Stats", "🛠 Support")
    bot.send_message(message.chat.id, "🌟 Main Menu:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    if is_subscribed(message.chat.id):
        show_main_menu(message)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Join Channel", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("I have joined ✅", callback_data="check_sub"))
        bot.send_message(message.chat.id, "Welcome! Please join our channel to use the bot.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if is_subscribed(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Join the channel first!", show_alert=True)

# --- START BOT ---
print("Dating Bot is LIVE with MongoDB...")
threading.Thread(target=check_payments, daemon=True).start()
bot.infinity_polling()
