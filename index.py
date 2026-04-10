import os, time, asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# سحب البيانات من ريلوي
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# تشغيل المحركات
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_data = {}

def GET_PROGRESS_BAR(current, total, start_time, action):
    perc = (current * 100 / total) if total > 0 else 0
    now = time.time()
    diff = now - start_time
    speed = current / diff if diff > 0 else 0
    bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
    return f"🚀 **{action}**\n\n【{bar}】 {round(perc, 2)}%\n⚡ {round(speed / 1024 / 1024, 2)} MB/s"

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply("أهلاً بك يا علي 🌹\nنظام الـ **4GB** المتكامل جاهز.\n\n1. أرسل الصورة.\n2. أرسل الملف.")

@bot_client.on(events.NewMessage)
async def handle_msg(event):
    chat_id = event.chat_id
    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await bot_client.download_media(event.photo, path)
        user_data[chat_id] = {'thumb': path}
        await event.reply("✅ تم حفظ الغلاف! أرسل الملف الآن.")
        return

    if event.document:
        if chat_id not in user_data: return await event.reply("⚠️ أرسل الصورة أولاً.")
        user_data[chat_id].update({'file': event.document, 'file_name': event.file.name})
        
        # حل المشكلة 1: الأزرار الثلاثة + زر الإلغاء
        buttons = [
            [Button.inline("📝 تغيير الاسم فقط", data="name")],
            [Button.inline("🖼️ تغيير الصورة فقط", data="thumb")],
            [Button.inline("🔄 تغيير الاثنين معاً", data="both")],
            [Button.inline("❌ إلغاء العملية", data="cancel")]
        ]
        await event.reply("ماذا تريد أن أفعل بهذا الملف؟", buttons=buttons)

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()
    if data == "cancel":
        user_data.pop(chat_id, None)
        return await event.edit("❌ تم إلغاء العملية.")
    
    if data in ["name", "both"]:
        user_data[chat_id]['action_type'] = data
        user_data[chat_id]['waiting_name'] = True
        return await event.edit("📝 أرسل الاسم الجديد الآن:")
    
    if data == "thumb":
        user_data[chat_id]['action_type'] = "thumb"
        await process_file(event, chat_id)

@bot_client.on(events.NewMessage)
async def get_name(event):
    chat_id = event.chat_id
    if chat_id in user_data and user_data[chat_id].get('waiting_name'):
        user_data[chat_id]['new_name'] = event.text
        user_data[chat_id]['waiting_name'] = False
        await process_file(event, chat_id)

async def process_file(event, chat_id):
    data = user_data[chat_id]
    status_msg = await event.respond("📡 جاري بدء المعالجة...")
    
    try:
        # حل المشكلة 3: شريط تحميل حقيقي 100%
        start_t = time.time()
        async def prog(c, t):
            if (time.time() - prog.last) > 5:
                try: await status_msg.edit(GET_PROGRESS_BAR(c, t, start_t, "جاري المعالجة ⏳"))
                except: pass
                prog.last = time.time()
        prog.last = 0

        file_path = await bot_client.download_media(data['file'], progress_callback=prog)
        
        final_name = data.get('new_name', data['file_name'])
        
        async with user_client:
            up_t = time.time()
            async def up_prog(c, t):
                if (time.time() - up_prog.last) > 5:
                    try: await status_msg.edit(GET_PROGRESS_BAR(c, t, up_t, "جاري الرفع 4GB ⬆️"))
                    except: pass
                    up_prog.last = time.time()
            up_prog.last = 0

            # الرفع عبر الحساب البريميوم
            sent = await user_client.send_file(
                'me', file_path, thumb=data['thumb'],
                attributes=[DocumentAttributeFilename(final_name)],
                progress_callback=up_prog, force_file=True
            )
            await bot_client.send_file(chat_id, sent, caption="✅ تم الإنجاز بواسطة علي!")

        await status_msg.delete()
        if os.path.exists(file_path): os.remove(file_path)
    except Exception as e: await event.respond(f"❌ خطأ: {e}")
    finally: user_data.pop(chat_id, None)

print("البوت يعمل بكامل طاقته...")
bot_client.run_until_disconnected()
