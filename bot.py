import telebot
from telebot import types
import sqlite3
import random
import time
import os
import requests

# --- Configuration (Railway Variables) ---
API_TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_PAY_TOKEN = os.getenv('CRYPTO_PAY_TOKEN')
CHANNEL_ID = '@Globalhotgirls_Advertisements'
CHANNEL_LINK = 'https://t.me/Globalhotgirls_Advertisements'
SUPPORT_USER = "@Eva_x33"
ADMIN_ID = 8590099043 

bot = telebot.TeleBot(API_TOKEN)
user_search_data = {} 

# --- Database Initialization ---
def init_db():
    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, name TEXT, gender TEXT, age TEXT, 
                       location TEXT, photo TEXT, verified INTEGER DEFAULT 0, 
                       is_premium INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS likes 
                      (from_id INTEGER, to_id INTEGER, type TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- CryptoPay Integration ---
def create_invoice(amount, user_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    payload = {'asset': 'USDT', 'amount': str(amount), 'payload': str(user_id)}
    try:
        response = requests.post("https://pay.crypt.bot/api/createInvoice", json=payload, headers=headers)
        return response.json()['result']
    except Exception as e:
        print(f"Error creating invoice: {e}")
        return None

# --- Subscription Check ---
def is_subscribed(chat_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, chat_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# --- Profile Creation ---
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
    bot.send_message(message.chat.id, "Send your Profile Photo (Videos/GIFs not allowed):")
    bot.register_next_step_handler(message, process_photo_final, name, gender, age, location)

def process_photo_final(message, name, gender, age, location):
    if message.content_type == 'photo':
        photo_id = message.photo[-1].file_id
        conn = sqlite3.connect('dating_bot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (id, name, gender, age, location, photo) VALUES (?, ?, ?, ?, ?, ?)", 
                       (message.chat.id, name, gender, age, location, photo_id))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Profile Created Successfully!")
        show_main_menu(message)
    else:
        bot.send_message(message.chat.id, "🚫 Only photos allowed! Please upload a photo:")
        bot.register_next_step_handler(message, process_photo_final, name, gender, age, location)

# --- Matching Logic ---
@bot.message_handler(func=lambda m: m.text in ["🔍 Find Matches", "🎲 Random Match"])
def handle_matching(message):
    user_id = message.chat.id
    if not is_subscribed(user_id):
        start(message)
        return

    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_premium, gender FROM users WHERE id = ?", (user_id,))
    res = cursor.fetchone()
    
    if not res:
        bot.send_message(user_id, "Please create a profile first!", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("Create Profile"))
        return

    is_premium, me_gender = res
    
    if not is_premium:
        now = time.time()
        if user_id not in user_search_data:
            user_search_data[user_id] = {'count': 0, 'last_reset': now}
        if user_search_data[user_id]['count'] >= 10:
            bot.send_message(user_id, "🚫 Free limit reached! Upgrade to 🌟 Premium for unlimited matches.")
            return
        user_search_data[user_id]['count'] += 1

    target = "Female" if me_gender == "Male" else "Male"
    cursor.execute("SELECT * FROM users WHERE id != ? AND gender = ?", (user_id, target))
    rows = cursor.fetchall()
    conn.close()
    
    if rows:
        row = random.choice(rows)
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("❤️", callback_data=f"react_like_{row[0]}"),
            types.InlineKeyboardButton("👍", callback_data=f"react_thumb_{row[0]}"),
            types.InlineKeyboardButton("😍", callback_data=f"react_fire_{row[0]}")
        )
        markup.add(types.InlineKeyboardButton("💬 Send Message", url=f"tg://user?id={row[0]}"))
        bot.send_photo(user_id, row[5], caption=f"Name: {row[1]}\nAge: {row[3]}\nLoc: {row[4]}", reply_markup=markup)
    else:
        bot.send_message(user_id, "No users found. Try again later!")

# --- Premium & Support Handlers (አዲስ የተጨመሩ) ---
@bot.message_handler(func=lambda m: m.text == "🌟 Buy Premium")
def premium_plans(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Weekly - $2", callback_data="buy_2"))
    markup.add(types.InlineKeyboardButton("Monthly - $7", callback_data="buy_7"))
    markup.add(types.InlineKeyboardButton("Yearly - $200", callback_data="buy_200"))
    bot.send_message(message.chat.id, "💎 Upgrade for Unlimited Matches!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🛠 Support")
def support_info(message):
    bot.send_message(message.chat.id, f"Need help? Contact Admin: {SUPPORT_USER}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def process_buy(call):
    amount = call.data.split("_")[1]
    invoice = create_invoice(amount, call.message.chat.id)
    if invoice:
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Pay via CryptoBot", url=invoice['pay_url']))
        bot.send_message(call.message.chat.id, f"✅ Pay ${amount} to unlock Unlimited Access:", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "❌ Error creating invoice. Check API Token.")

# --- General Handlers ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("react_"))
def handle_reactions(call):
    data = call.data.split("_")
    react_type, target_id = data[1], int(data[2])
    bot.answer_callback_query(call.id, "Reaction sent! ✨")
    try:
        emoji = "❤️" if react_type == "like" else "👍" if react_type == "thumb" else "😍"
        bot.send_message(target_id, f"🌟 Someone sent you a {emoji}!")
    except: pass

@bot.message_handler(func=lambda m: m.text == "👤 My Profile")
def view_profile(message):
    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (message.chat.id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        bot.send_photo(message.chat.id, row[5], caption=f"👤 **Your Profile**\n\nName: {row[1]}\nAge: {row[3]}\nLoc: {row[4]}\nPremium: {'Yes' if row[7] else 'No'}", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "No profile found.")

@bot.message_handler(func=lambda m: m.text == "📊 Stats")
def show_stats(message):
    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    bot.reply_to(message, f"📊 Total Users: {count}")

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

print("Dating Bot is LIVE...")
bot.infinity_polling()
