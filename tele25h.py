import json
import random
import string
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import re

# === SERVER GIẢ CHO RENDER ===
import threading
import http.server
import socketserver
import os

def dummy_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving dummy HTTP on port {port}")
        httpd.serve_forever()

# === CẤU HÌNH ===
BOT_TOKEN = os.environ.get("7687184140:AAHA2OTsXjlKdIPuGJh2Ou1BD_9hlYPsGJU")
ADMIN_ID = 6254591457
KEYS_FILE = "keys.json"
user_keys = {}

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

# === XỬ LÝ MÃ MD5 TỰ ĐỘNG ===
async def handle_md5_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, md5):
    user_id = update.effective_user.id
    if user_id not in user_keys:
        await update.message.reply_text("🔒 Bạn cần nhập key trước. Dùng: /nhapkey KEY")
        return

    await update.message.reply_text("Bot đang chạy...")
    import asyncio
    await asyncio.sleep(3)

    to_hops = [(0, 2, 31), (0, 6, 31), (0, 7, 31), (0, 8, 31),
               (0, 12, 31), (0, 14, 31), (0, 18, 31), (0, 20, 31),
               (0, 24, 31), (0, 26, 31)]
    phieu_tai = 0
    phieu_xiu = 0
    for a, b, c in to_hops:
        hex_str = md5[a] + md5[b] + md5[c]
        dec_value = int(hex_str, 16)
        if dec_value % 10 < 5:
            phieu_xiu += 1
        else:
            phieu_tai += 1

    if phieu_tai > phieu_xiu:
        result = f"Xỉu ({phieu_tai * 10}%)"
    elif phieu_xiu > phieu_tai:
        result = f"Tài ({phieu_xiu * 10}%)"
    else:
        result = "Bỏ tay này (5/5 phiếu)"

    key = user_keys[user_id]
    keys = load_keys()
    expire_at = datetime.fromisoformat(keys[key]["expires_at"])
    minutes_left = int((expire_at - datetime.now()).total_seconds() // 60)

    await update.message.reply_text(
        f"Kết quả: {result}\nThời gian còn lại: {minutes_left} phút"
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

# === KHỞI TẠO ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("taokey", taokey))
    app.add_handler(CommandHandler("listkey", listkey))
    app.add_handler(CommandHandler("nhapkey", nhap_key))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Mở server giả để Render không báo lỗi
    threading.Thread(target=dummy_server, daemon=True).start()

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()