import telebot
from telebot import types
import sqlite3
import random
import time

# --- Configuration ---
API_TOKEN = '8239904642:AAHy0xYu2ogMubj8kuWGtnG8_p5Y9V4eM_w'
CHANNEL_ID = '@Globalhotgirls_Advertisements'
CHANNEL_LINK = 'https://t.me/Globalhotgirls_Advertisements'
SUPPORT_USER = "@Eva_x33"
ADMIN_ID = 8590099043 # Your Telegram ID

bot = telebot.TeleBot(API_TOKEN)
user_search_data = {} 

def init_db():
    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, name TEXT, gender TEXT, age TEXT, location TEXT, photo TEXT, verified INTEGER DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS likes 
                      (from_id INTEGER, to_id INTEGER, type TEXT)''')
    conn.commit()
    conn.close()

init_db()

def is_subscribed(chat_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, chat_id).status
        return status in ['member', 'administrator', 'creator']
    except Exception:
        return False

# --- Admin Statistics ---
@bot.message_handler(commands=['stats'])
def get_stats(message):
    if message.chat.id == ADMIN_ID:
        conn = sqlite3.connect('dating_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        conn.close()
        bot.send_message(message.chat.id, f"📊 Bot Statistics\n\nTotal Registered Users: {total_users}")
    else:
        bot.send_message(message.chat.id, "❌ Access Denied.")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if is_subscribed(user_id):
        show_main_menu(message)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Join Channel", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("I have joined ✅", callback_data="check_sub"))
        bot.send_message(user_id, f"Welcome! Please join our channel to use the bot.\nSupport: {SUPPORT_USER}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub(call):
    if is_subscribed(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Join the channel first!", show_alert=True)

def show_main_menu(message):
    if not is_subscribed(message.chat.id):
        start(message)
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Find Matches", "🎲 Random Match")
    markup.add("👤 My Profile", "📝 Edit Profile")
    markup.add("🛠 Support")
    bot.send_message(message.chat.id, "🌟 Main Menu:", reply_markup=markup)

def check_limit(user_id):
    now = time.time()
    if user_id not in user_search_data:
        user_search_data[user_id] = {'count': 0, 'last_reset': now}
    data = user_search_data[user_id]
    if now - data['last_reset'] > 300: 
        data['count'] = 0
        data['last_reset'] = now
    if data['count'] >= 10:
        remaining_wait = int((300 - (now - data['last_reset'])) / 60)
        return False, max(1, remaining_wait)
    data['count'] += 1
    return True, 0

@bot.message_handler(func=lambda m: m.text in ["🔍 Find Matches", "🎲 Random Match"])
def handle_matching(message):
    if not is_subscribed(message.chat.id):
        start(message)
        return
    
    user_id = message.chat.id
    allowed, wait_time = check_limit(user_id)
    if not allowed:
        bot.send_message(user_id, f"🚫 Limit reached! Please wait {wait_time} minutes.")
        return

    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT gender FROM users WHERE id = ?", (user_id,))
    me = cursor.fetchone()
    if not me:
        bot.send_message(user_id, "Please create a profile first!")
        return
    target = "Female" if me[0] == "Male" else "Male"
    cursor.execute("SELECT * FROM users WHERE id != ? AND gender = ?", (user_id, target))
    rows = cursor.fetchall()
    conn.close()
    if rows:
        row = random.choice(rows)
        verify_badge = " ✅" if row[6] == 1 else ""
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(types.InlineKeyboardButton("❤️", callback_data=f"react_like_{row[0]}"),
                   types.InlineKeyboardButton("👍", callback_data=f"react_thumb_{row[0]}"),
                   types.InlineKeyboardButton("😍", callback_data=f"react_fire_{row[0]}"))
        markup.add(types.InlineKeyboardButton("💬 Send Message", url=f"tg://user?id={row[0]}"))
        bot.send_photo(user_id, row[5], caption=f"Name: {row[1]}{verify_badge}\nAge: {row[3]}\nLoc: {row[4]}", reply_markup=markup)
    else:
        bot.send_message(user_id, "No users found in the opposite gender.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("react_"))
def handle_reactions(call):
    data = call.data.split("_")
    react_type, target_id = data[1], int(data[2])
    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO likes (from_id, to_id, type) VALUES (?, ?, ?)", (call.from_user.id, target_id, react_type))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Reaction sent!")
    try:
        emoji = "❤️" if react_type == "like" else "👍" if react_type == "thumb" else "😍"
        bot.send_message(target_id, f"🌟 Someone sent you a {emoji}!")
    except: pass

@bot.message_handler(func=lambda m: m.text == "👤 My Profile")
def my_profile(message):
    conn = sqlite3.connect('dating_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (message.chat.id,))
    user = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM likes WHERE to_id = ?", (message.chat.id,))
    total_likes = cursor.fetchone()[0]
    conn.close()
    if user:
        info = f"Profile:\nName: {user[1]}\nAge: {user[3]}\nLoc: {user[4]}\nLikes: {total_likes}"
        bot.send_photo(message.chat.id, user[5], caption=info)
    else: bot.send_message(message.chat.id, "Profile not found.")

@bot.message_handler(func=lambda m: m.text in ["📝 Edit Profile", "Create Profile"])
def create_profile(message):
    bot.send_message(message.chat.id, "What is your Name?")
    bot.register_next_step_handler(message, process_name)

def process_name(message):
    name = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Male", "Female")
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
    bot.send_message(message.chat.id, "Send Photo:")
    bot.register_next_step_handler(message, process_photo_final, name, gender, age, location)

def process_photo_final(message, name, gender, age, location):
    if message.content_type == 'photo':
        photo_id = message.photo[-1].file_id
        conn = sqlite3.connect('dating_bot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (id, name, gender, age, location, photo) VALUES (?, ?, ?, ?, ?, ?)", (message.chat.id, name, gender, age, location, photo_id))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Profile Created!")
        show_main_menu(message)
    else: 
        bot.send_message(message.chat.id, "Please upload a photo.")
        bot.register_next_step_handler(message, process_photo_final, name, gender, age, location)

@bot.message_handler(func=lambda m: m.text == "🛠 Support")
def support_info(message):
    bot.send_message(message.chat.id, f"Contact Support: {SUPPORT_USER}")

print("Bot is running...")
bot.infinity_polling()
