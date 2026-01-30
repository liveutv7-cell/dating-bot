import telebot
from telebot import types
from pymongo import MongoClient
import random
import time
import requests
import threading

# --- Configuration ---
API_TOKEN = "8239904642:AAHy0xYu2ogMubj8kuWGtnG8_p5Y9V4eM_w"
CRYPTO_PAY_TOKEN = "522389:AAagZEOufX4vVfpNm1ArS506FqHI9DU8aom"

# MONGO_URI with your confirmed password
MONGO_URI = "mongodb+srv://admin:Mrpro123@cluster0.vyqetel.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
# Note: Ensure 'dating_bot_db' is where your 66 users are stored. 
# If they are in another database, change this name.
db = client['dating_bot_db'] 
users_col = db['users']

CHANNEL_ID = '@Globalhotgirls_Advertisements'
CHANNEL_LINK = 'https://t.me/Globalhotgirls_Advertisements'
SUPPORT_USER = "@Eva_x33"

bot = telebot.TeleBot(API_TOKEN)
user_search_data = {}

# --- Payment Checker ---
def check_payments():
    while True:
        try:
            headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
            response = requests.get("https://pay.crypt.bot/api/getInvoices?status=paid", headers=headers)
            res_data = response.json()
            if res_data.get('ok'):
                for inv in res_data['result'].get('items', []):
                    user_id = int(inv['payload'])
                    users_col.update_one({"id": user_id}, {"$set": {"is_premium": 1}})
                    try: 
                        bot.send_message(user_id, "🌟 PAYMENT CONFIRMED! Your account is now PREMIUM (Unlimited Access)!")
                    except: pass
        except: pass
        time.sleep(30)

def create_invoice(amount, user_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    payload = {'asset': 'USDT', 'amount': str(amount), 'payload': str(user_id)}
    try:
        response = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers)
        return response.json()['result']
    except: return None

# --- Profile Section ---
@bot.message_handler(func=lambda m: m.text in ["👤 My Profile", "Create Profile"])
def profile_options(message):
    user = users_col.find_one({"id": message.chat.id})
    if user:
        msg = f"👤 *Your Profile*\n\nName: {user['name']}\nAge: {user['age']}\nGender: {user['gender']}\nPremium: {'Yes 🌟' if user.get('is_premium', 0) else 'No'}"
        bot.send_photo(message.chat.id, user['photo'], caption=msg, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Welcome! What is your Name?")
        bot.register_next_step_handler(message, get_name)

def get_name(message):
    name = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add("Male", "Female")
    bot.send_message(message.chat.id, "Select Gender:", reply_markup=markup)
    bot.register_next_step_handler(message, get_gender, name)

def get_gender(message, name):
    gender = message.text
    bot.send_message(message.chat.id, "How old are you?")
    bot.register_next_step_handler(message, get_age, name, gender)

def get_age(message, name, gender):
    age = message.text
    bot.send_message(message.chat.id, "Which city/location are you in?")
    bot.register_next_step_handler(message, get_photo, name, gender, age)

def get_photo(message, name, gender, age):
    location = message.text
    bot.send_message(message.chat.id, "📸 Send your PHOTO (No Videos/GIFs/Stickers allowed):")
    bot.register_next_step_handler(message, save_profile, name, gender, age, location)

def save_profile(message, name, gender, age, location):
    if message.content_type == 'photo':
        photo_id = message.photo[-1].file_id
        users_col.update_one(
            {"id": message.chat.id}, 
            {"$set": {"id": message.chat.id, "name": name, "gender": gender, "age": age, "location": location, "photo": photo_id, "is_premium": 0}}, 
            upsert=True
        )
        bot.send_message(message.chat.id, "✅ Profile successfully created!")
        show_menu(message)
    else:
        bot.send_message(message.chat.id, "🚫 ERROR: Only photos are allowed. Please send a photo:")
        bot.register_next_step_handler(message, save_profile, name, gender, age, location)

# --- Find Matches with Reactions & 10 Search Limit ---
@bot.message_handler(func=lambda m: m.text == "🔍 Find Matches")
def find_matches(message):
    uid = message.chat.id
    user = users_col.find_one({"id": uid})
    if not user:
        bot.send_message(uid, "Please create a profile first!", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Create Profile"))
        return

    is_premium = user.get('is_premium', 0)
    if not is_premium:
        user_search_data[uid] = user_search_data.get(uid, 0) + 1
        if user_search_data[uid] > 10:
            bot.send_message(uid, "🚫 Free Limit Reached! Upgrade to 🌟 Premium for unlimited searches.", 
                             reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🌟 Buy Premium"))
            return

    target = "Female" if user.get('gender') == "Male" else "Male"
    matches = list(users_col.find({"id": {"$ne": uid}, "gender": target}))
    if matches:
        match = random.choice(matches)
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("❤️", callback_data="rx"),
            types.InlineKeyboardButton("👍", callback_data="rx"),
            types.InlineKeyboardButton("😍", callback_data="rx")
        )
        markup.add(types.InlineKeyboardButton("💬 Send Message", url=f"tg://user?id={match['id']}"))
        
        caption = f"Name: {match['name']}\nAge: {match['age']}\nLoc: {match['location']}"
        if not is_premium:
            caption += f"\n\n(Free matches left: {10 - user_search_data[uid]})"
            
        bot.send_photo(uid, match['photo'], caption=caption, reply_markup=markup)
    else:
        bot.send_message(uid, "No matches found right now. Try again later!")

@bot.callback_query_handler(func=lambda c: c.data == "rx")
def react_callback(call):
    bot.answer_callback_query(call.id, "Reaction Sent! ✨")

# --- Menu & Premium ---
def show_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🔍 Find Matches", "👤 My Profile").add("🌟 Buy Premium", "📊 Stats")
    bot.send_message(message.chat.id, "Main Menu:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 Stats")
def stats(message):
    count = users_col.count_documents({})
    bot.reply_to(message, f"📊 Total Active Users: {count}")

@bot.message_handler(func=lambda m: m.text == "🌟 Buy Premium")
def buy_prem(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Weekly - $2", callback_data="pay_2"))
    markup.add(types.InlineKeyboardButton("Monthly - $7", callback_data="pay_7"))
    markup.add(types.InlineKeyboardButton("Yearly - $200", callback_data="pay_200")) # FIXED: $200
    bot.send_message(message.chat.id, "💎 UNLOCK UNLIMITED ACCESS:\n\n✅ Unlimited Matches\n✅ Yearly Exclusive Access\n✅ Ad-free Experience", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def process_payment(call):
    amount = call.data.split("_")[1]
    invoice = create_invoice(amount, call.message.chat.id)
    if invoice:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Pay via CryptoBot", url=invoice['pay_url']))
        bot.send_message(call.message.chat.id, f"✅ To upgrade, pay ${amount} USDT using the button below:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    show_menu(message)

# --- Start Bot ---
print("Bot is starting...")
threading.Thread(target=check_payments, daemon=True).start()
bot.infinity_polling()
