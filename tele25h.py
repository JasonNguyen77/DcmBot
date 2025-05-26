import json
import random
import string
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import re
import threading
import os
from flask import Flask
import hashlib
import math

# === CẤU HÌNH ===
BOT_TOKEN = "7687184140:AAHA2OTsXjlKdIPuGJh2Ou1BD_9hlYPsGJU"
ADMIN_ID = 6254591457
KEYS_FILE = "keys.json"
user_keys = {}

# === FLASK WEB SERVER GIỮ BOT LUÔN BẬT ===
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return 'Bot is running!'

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# === HÀM SOI CẦU MỚI ===
def calculate_percentage(value: int, max_value: int) -> float:
    normalized_value = value / max_value
    probability = 1 / (1 + math.exp(-12 * (normalized_value - 0.5)))
    return probability * 100

def deterministic_salt(input_str: str) -> str:
    return hashlib.md5(input_str.encode()).hexdigest()

def enhanced_hash_analysis(input_str: str) -> float:
    salt = deterministic_salt(input_str)
    combined_input = input_str + salt

    sha512_hash = hashlib.sha512(combined_input.encode()).hexdigest()
    sha256_hash = hashlib.sha256(combined_input.encode()).hexdigest()
    sha3_512_hash = hashlib.sha3_512(combined_input.encode()).hexdigest()
    blake2b_hash = hashlib.blake2b(combined_input.encode()).hexdigest()
    md5_hash = hashlib.md5(combined_input.encode()).hexdigest()

    value1 = int(sha512_hash[:16], 16)
    value2 = int(sha256_hash[-16:], 16)
    value3 = int(sha3_512_hash[16:32], 16)
    value4 = int(blake2b_hash[:16], 16)
    value5 = int(md5_hash[:8], 16)

    combined_value = ((value1 ^ value2) + (value3 >> 3) - (value4 << 2) + int(math.sqrt(value5))) % (1 << 64)
    return calculate_percentage(combined_value, (1 << 64) - 1)

# === KEY HANDLING ===
def load_keys():
    try:
        with open(KEYS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

def generate_key(length=10):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def parse_duration(duration_str):
    unit = duration_str[-1]
    amount = int(duration_str[:-1])
    if unit == "m":
        return timedelta(minutes=amount)
    elif unit == "h":
        return timedelta(hours=amount)
    elif unit == "d":
        return timedelta(days=amount)
    return None

def is_valid_key(user_key):
    keys = load_keys()
    key_info = keys.get(user_key)
    if not key_info:
        return False
    if datetime.fromisoformat(key_info["expires_at"]) < datetime.now():
        del keys[user_key]
        save_keys(keys)
        return False
    if key_info.get("used", False):
        return False
    return True

def mark_key_used(user_key):
    keys = load_keys()
    if user_key in keys:
        keys[user_key]["used"] = True
        save_keys(keys)

# === ADMIN COMMANDS ===
async def taokey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("❗ Cú pháp: /taokey 30m | 1h | 1d")
        return

    duration = parse_duration(context.args[0])
    if not duration:
        await update.message.reply_text("❗ Đơn vị sai. Dùng m, h hoặc d.")
        return

    key = generate_key()
    expire_time = datetime.now() + duration

    keys = load_keys()
    keys[key] = {"expires_at": expire_time.isoformat(), "used": False}
    save_keys(keys)

    await update.message.reply_text(
        f"✅ Key mới: `{key}`\nHiệu lực: {context.args[0]}",
        parse_mode="Markdown"
    )

async def listkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền.")
        return

    keys = load_keys()
    now = datetime.now()
    text = "🔑 Key còn hiệu lực:\n"
    for k, v in keys.items():
        if not v.get("used", False) and datetime.fromisoformat(v["expires_at"]) > now:
            text += f"- `{k}`: hết hạn {v['expires_at']}\n"
    if text == "🔑 Key còn hiệu lực:\n":
        text = "Không có key còn hiệu lực"
    await update.message.reply_text(text, parse_mode="Markdown")

# === NGƯỜI DÙNG ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.full_name
    keyboard = [["Nhập key", "Nhập mã MD5"], ["Thời gian còn lại", "Liên hệ admin"]]
    await update.message.reply_text(
        f"Chào mừng {name} đến với Bot Dự Đoán Tài Xỉu B52.\nLiên hệ @JasonNguyen77 để mua key.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def nhap_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text("❗ Cú pháp đúng: /nhapkey ABC123456")
        return

    key = context.args[0].strip().upper()
    if is_valid_key(key):
        user_keys[user_id] = key
        mark_key_used(key)
        await update.message.reply_text("✅ Key hợp lệ. Bạn đã được kích hoạt.")
    else:
        await update.message.reply_text("❌ Key không hợp lệ hoặc đã hết hạn.")

# === XỬ LÝ MÃ MD5 VỚI LOGIC MỚI ===
async def handle_md5_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, md5):
    user_id = update.effective_user.id
    if user_id not in user_keys:
        await update.message.reply_text("🔒 Bạn cần nhập key trước. Dùng: /nhapkey KEY")
        return

    await update.message.reply_text("Đang phân tích...")

    percent_xiu = enhanced_hash_analysis(md5)
    percent_tai = 100.0 - percent_xiu

    if abs(percent_xiu - percent_tai) < 5:
        result = "Bỏ tay này (xác suất quá cân bằng)"
    elif percent_xiu > percent_tai:
        result = f"Xỉu mạnh: {percent_xiu:.2f}%\nTài yếu: {percent_tai:.2f}%"
    else:
        result = f"Tài mạnh: {percent_tai:.2f}%\nXỉu yếu: {percent_xiu:.2f}%"

    key = user_keys[user_id]
    keys = load_keys()
    expire_at = datetime.fromisoformat(keys[key]["expires_at"])
    minutes_left = int((expire_at - datetime.now()).total_seconds() // 60)

    await update.message.reply_text(
        f"Kết quả soi cầu:\n{result}\n\nThời gian còn lại: {minutes_left} phút"
    )

# === XỬ LÝ TIN NHẮN ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()

    if text == "nhập key":
        await update.message.reply_text("Vui lòng dùng lệnh: /nhapkey ABC123456")
    elif text == "nhập mã md5":
        await update.message.reply_text("Bạn có thể dán trực tiếp mã MD5 (32 ký tự) vào để bot xử lý.")
    elif text == "liên hệ admin":
        await update.message.reply_text("Liên hệ @JasonNguyen77 để được hỗ trợ.")
    elif text == "thời gian còn lại":
        await update.message.reply_text("Tính năng đang được phát triển.")
    elif re.fullmatch(r"[a-f0-9]{32}", text):
        await handle_md5_direct(update, context, text)
    else:
        await update.message.reply_text("❓ Không hiểu yêu cầu. Hãy dùng các lệnh có sẵn.")

# === KHỞI ĐỘNG BOT + WEB ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taokey", taokey))
    app.add_handler(CommandHandler("listkey", listkey))
    app.add_handler(CommandHandler("nhapkey", nhap_key))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    threading.Thread(target=run_web).start()

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
