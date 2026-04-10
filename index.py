import os, time, asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# سحب البيانات من ريلوي
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# تشغيل حساب البريميوم (المحرك)
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
# تشغيل البوت (الواجهة)
bot_client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_data = {}

def GET_PROGRESS_BAR(current, total, start_time, action):
    now = time.time()
    diff = now - start_time
    if diff <= 0: return "جاري البدء..."
    perc = (current * 100 / total) if total > 0 else 0
    speed = current / diff 
    bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
    return f"🚀 **{action}**\n\n【{bar}】 {round(perc, 2)}%\n⚡ {round(speed / 1024 / 1024, 2)} MB/s"

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("أهلاً بك في بوت التعديل العملاق 4GB ⚡\nأرسل صورة الغلاف أولاً ثم الملف.")

@bot_client.on(events.NewMessage)
async def handle_msg(event):
    chat_id = event.chat_id
    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await bot_client.download_media(event.photo, path)
        user_data[chat_id] = {'thumb': path}
        await event.reply("✅ تم حفظ الغلاف! أرسل الملف الآن (حتى 4GB).")
        return

    if event.document:
        if chat_id not in user_data: return await event.reply("⚠️ أرسل الصورة أولاً.")
        user_data[chat_id].update({'file': event.document, 'file_name': event.file.name})
        buttons = [[Button.inline("📝 تغيير الاسم", data="name")],
                   [Button.inline("❌ إلغاء", data="cancel")]]
        await event.reply("ماذا تريد أن أفعل؟", buttons=buttons)

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    if event.data.decode() == "name":
        user_data[chat_id]['waiting_name'] = True
        await event.edit("📝 أرسل الاسم الجديد مع الصيغة (مثال: ali.mp4):")

@bot_client.on(events.NewMessage)
async def get_name(event):
    chat_id = event.chat_id
    if chat_id in user_data and user_data[chat_id].get('waiting_name'):
        user_data[chat_id]['new_name'] = event.text
        user_data[chat_id]['waiting_name'] = False
        await process_file(event, chat_id)

async def process_file(event, chat_id):
    data = user_data[chat_id]
    status_msg = await event.respond("📡 جاري التحميل والرفع بمميزات الـ 4GB...")
    
    try:
        # التحميل عبر البوت
        file_path = await bot_client.download_media(data['file'])
        
        # الرفع عبر حساب البريميوم (هنا السر)
        async with user_client:
            up_t = time.time()
            async def up_cb(c, t):
                if (time.time() - up_cb.last) > 8:
                    try: await status_msg.edit(GET_PROGRESS_BAR(c, t, up_t, "جاري الرفع السحابي ⬆️"))
                    except: pass
                    up_cb.last = time.time()
            up_cb.last = 0

            # نرسل الملف من حسابك إلى البوت ومن ثم للمستخدم
            sent_file = await user_client.send_file(
                'me', file_path, thumb=data['thumb'],
                attributes=[DocumentAttributeFilename(data['new_name'])],
                progress_callback=up_cb, force_file=True
            )
            # البوت يرسل الملف النهائي للمستخدم
            await bot_client.send_file(chat_id, sent_file, caption="✅ تم الإنجاز بواسطة بوت علي!")
            
        await status_msg.delete()
        if os.path.exists(file_path): os.remove(file_path)
    except Exception as e: await event.respond(f"❌ خطأ: {e}")
    finally: user_data.pop(chat_id, None)

print("النظام الهجين يعمل...")
bot_client.run_until_disconnected()
