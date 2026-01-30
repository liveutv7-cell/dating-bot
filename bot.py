import telebot
from telebot import types
from pymongo import MongoClient

# --- CONFIGURATION ---
API_TOKEN = "8239904642:AAHy0xYu2ogMubj8kuWGtnG8_p5Y9V4eM_w"
MONGO_URI = "mongodb+srv://admin:Mrpro123@cluster0.vyqetel.mongodb.net/?appName=Cluster0"
CHANNEL_USERNAME = "@GlobalHotgirls_Advertisements" 
ADMIN_ID = 8593628479 

client = MongoClient(MONGO_URI)
db = client['dating_bot_db']
users_col = db['users']
bot = telebot.TeleBot(API_TOKEN)

# --- JOIN FORCE CHECK ---
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True

# --- BLOCK NON-PHOTO MESSAGES DURING REGISTRATION ---
# This part ensures users only upload photos for their profile
@bot.message_handler(content_types=['video', 'document', 'sticker', 'animation', 'video_note', 'voice'])
def block_others(message):
    bot.reply_to(message, "🚫 Error: Only Photos are allowed! Videos, Stickers, and GIFs are not permitted.")

# --- FIND MATCHES LOGIC ---
@bot.message_handler(func=lambda m: m.text == "🔍 Find Matches")
def find_matches(message):
    if not is_subscribed(message.chat.id):
        return start(message)

    user = users_col.find_one({"id": message.chat.id})
    if not user:
        bot.send_message(message.chat.id, "Please register first by sending /start")
        return

    is_premium = (message.chat.id == ADMIN_ID or user.get('is_premium', 0) == 1)
    search_count = user.get('search_count', 0)

    if not is_premium and search_count >= 10:
        bot.send_message(message.chat.id, "🚫 Daily limit reached (10/10). Upgrade to Premium for unlimited searches!")
        return

    match = list(users_col.aggregate([{"$match": {"id": {"$ne": message.chat.id}}}, {"$sample": {"size": 1}}]))

    if match:
        target = match[0]
        if not is_premium:
            users_col.update_one({"id": message.chat.id}, {"$inc": {"search_count": 1}})

        caption = f"👤 Name: {target['name']}\n🎂 Age: {target['age']}\n📍 Location: {target.get('location', 'N/A')}"
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("😍", callback_data=f"like_{target['id']}"),
            types.InlineKeyboardButton("❤️", callback_data=f"like_{target['id']}"),
            types.InlineKeyboardButton("👍", callback_data=f"like_{target['id']}")
        )
        markup.add(types.InlineKeyboardButton("➡️ Next", callback_data="next_match"))

        bot.send_photo(message.chat.id, target['photo'], caption=caption, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "No more matches found!")

# --- START & MENU ---
@bot.message_handler(commands=['start'])
def start(message):
    if not is_subscribed(message.chat.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Join Channel", url="https://t.me/GlobalHotgirls_Advertisements"))
        bot.send_message(message.chat.id, "❗ Join our channel to use the bot:", reply_markup=markup)
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔍 Find Matches", "👤 My Profile")
    markup.add("🌟 Buy Premium", "📊 Stats", "🎧 Support")
    bot.send_message(message.chat.id, "Welcome to Global Dating! Choose an option:", reply_markup=markup)

# Other handlers (Support, Profile, etc.) remain the same...
@bot.message_handler(func=lambda m: m.text == "🎧 Support")
def support(message):
    bot.send_message(message.chat.id, "📩 Support: @Omar_soner")

bot.infinity_polling()
