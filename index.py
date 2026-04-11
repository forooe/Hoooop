import os, time, asyncio, aiohttp
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# --- الإعدادات من Railway ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8162224437))

# تشغيل المحركات (البوت للواجهة والحساب للرفع الثقيل)
bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
premium_user = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

user_data = {}
processing_users = {} 
prog_cb_last = {}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid):
    return f'<emoji id="{eid}">📍</emoji>'

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    if chat_id in processing_users:
        return await event.reply("⚠️ **تحذير:** لديك عملية قيد التنفيذ، يرجى الانتظار أو الإلغاء.")
    
    sender = await event.get_sender()
    await bot.send_message(ADMIN_ID, f"👤 دخول: {sender.first_name}\n🆔: `{chat_id}`")

    msg = (f"أهلاً بك يا {sender.first_name} في بوت الرفع الصاروخي 🚀\n\n"
           f"يدعم الرفع حتى **4GB** مع ميزة تحويل الروابط المباشرة مجاناً ✨")
    
    buttons = [[Button.inline("تغيير اسم 📝", data="mode_name")],
               [Button.inline("تغيير صورة 🖼️", data="mode_thumb")],
               [Button.inline("تغيير الاثنين معاً 🔄", data="mode_both")],
               [Button.inline("تحويل رابط مباشر 🔗", data="mode_url")]]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()
    
    if data == "cancel_proc":
        processing_users[chat_id] = "cancelled"
        return await event.answer("✅ سيتم إلغاء العملية فوراً..", alert=True)
    
    user_data[chat_id] = {'mode': data.replace('mode_', '')}
    txt = "أرسل الرابط المباشر 🔗" if "url" in data else "أرسل الصورة أولاً 🖼️"
    await event.edit(txt)

@bot.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data or chat_id in processing_users or event.text.startswith('/'): return
    
    mode = user_data[chat_id]['mode']
    if mode == 'url' and event.text.startswith("http"):
        user_data[chat_id].update({'url': event.text, 'file_name': event.text.split("/")[-1].split("?")[0] or "file"})
        await process_logic(event, chat_id, "url")
    elif event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        await event.reply("✅ تم حفظ الصورة، أرسل الملف الآن 📁")
    elif event.document:
        user_data[chat_id].update({'file': event.document, 'file_name': event.file.name})
        await process_logic(event, chat_id, "file")

async def process_logic(event, chat_id, s_type):
    processing_users[chat_id] = "active"
    data = user_data[chat_id]
    status = await event.respond("📡 جاري فحص البيانات...", buttons=[Button.inline("إلغاء العملية ❌", data="cancel_proc")])
    start_time = time.time()

    try:
        async def prog_cb(current, total, action, eid, arrow):
            if processing_users.get(chat_id) == "cancelled": raise Exception("user_cancelled")
            now = time.time()
            if chat_id not in prog_cb_last or (now - prog_cb_last[chat_id]) > 7:
                diff = now - start_time
                perc = (current * 100 / total) if total > 0 else 0
                speed = current / diff if diff > 0 else 0
                txt = (f"{arrow} **{action}** {get_em(eid)}\n"
                       f"【{'▰'*int(perc/10)}{'▱'*(10-int(perc/10))}】 {round(perc, 2)}%\n"
                       f"📦 الحجم: {format_size(current)} / {format_size(total)}\n"
                       f"⚡ السرعة: {format_size(speed)}/s")
                await status.edit(txt, parse_mode='html')
                prog_cb_last[chat_id] = now

        if s_type == "url":
            path = data['file_name']
            async with aiohttp.ClientSession() as sess:
                async with sess.get(data['url']) as res:
                    total = int(res.headers.get('content-length', 0))
                    with open(path, 'wb') as f:
                        curr = 0
                        async for chunk in res.content.iter_chunked(1024*1024*16): # سرعة 16MB
                            f.write(chunk); curr += len(chunk)
                            await prog_cb(curr, total, "سحب الملف", "5406745015365943482", "⬇️")
        else:
            path = await bot.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t,"تحميل ملفك","5406745015365943482","⬇️"))

        async with premium_user:
            uploaded = await premium_user.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t,"رفع 4GB","5415655814079723871","⬆️"))
            await premium_user.send_file(chat_id, uploaded, thumb=data.get('thumb'), caption=f"✅ تم بنجاح!\n📦 `{path}`", force_document=True)
            
        await status.delete()
        if os.path.exists(path): os.remove(path)
    except Exception as e:
        await event.respond(f"❌ {'تم الإلغاء بنجاح' if 'cancelled' in str(e) else f'خطأ: {e}'}")
    finally:
        processing_users.pop(chat_id, None)
        user_data.pop(chat_id, None)

bot.run_until_disconnected()
