import os, time, asyncio, aiohttp
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# --- البيانات الأساسية من Railway ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "") # لضمان رفع 4GB
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8162224437)) # آيدي الأدمن الخاص بك

# تشغيل الحساب المميز (للرفع) والبوت (للواجهة)
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_data = {}
processing_users = {} 
prog_cb_last = {}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid):
    return f'<emoji id="{eid}">📍</emoji>'

# استقبال الملف من الحساب وإرساله للمستخدم (لحل مشكلة الـ Entity والـ 4GB)
@bot_client.on(events.NewMessage(incoming=True))
async def forward_to_user(event):
    if event.document and event.is_private and event.sender_id != ADMIN_ID:
        try:
            caption_parts = event.message.message.split("|")
            target_user_id = int(caption_parts[0])
            user_name = caption_parts[1]
            
            await bot_client.send_file(target_user_id, event.document, caption="✅ تم إنجاز ملفك بنجاح!")
            await bot_client.send_message(ADMIN_ID, f"✅ اكتمل الرفع للمستخدم: {user_name}")
            
            if target_user_id in processing_users:
                del processing_users[target_user_id]
        except: pass

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    if chat_id in processing_users:
        return await event.reply("⚠️ يرجى الانتظار حتى اكتمال المعالجة الحالية.")

    sender = await event.get_sender()
    username = f"@{sender.username}" if sender.username else "لا يوجد"
    await bot_client.send_message(ADMIN_ID, f"👤 دخول مستخدم جديد: {sender.first_name}\n🆔: `{chat_id}`\n🔗: {username}")

    msg = (f"أهلاً بك يا {sender.first_name} {get_em('5418017294473251153')}\n"
           f"تغيير وتحويل الملفات حتى 4GB مجاناً {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد أن تفعل الآن؟")
    
    buttons = [
        [Button.inline("تغيير اسم 📝", data="mode_name")],
        [Button.inline("تغيير صورة 🖼️", data="mode_thumb")],
        [Button.inline("تغيير الاثنين معاً 🔄", data="mode_both")],
        [Button.inline("تحويل رابط مباشر 🔗", data="mode_url")]
    ]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()
    
    if data == "cancel_proc":
        processing_users[chat_id] = "cancelled"
        return await event.answer("✅ سيتم إلغاء العملية..", alert=True)
    
    user_data[chat_id] = {'mode': data.replace('mode_', '')}
    txt = "أرسل الرابط المباشر الآن 🔗" if "url" in data else "أرسل الصورة المطلوبة أولاً 🖼️" if ("thumb" in data or "both" in data) else "أرسل الملف المطلوب 📁"
    await event.edit(txt)

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data or chat_id in processing_users or event.text.startswith('/'): return
    
    mode = user_data[chat_id]['mode']

    # منطق الروابط
    if mode == 'url' and event.text.startswith("http"):
        user_data[chat_id]['url'] = event.text
        user_data[chat_id]['file_name'] = event.text.split("/")[-1].split("?")[0] or "file"
        await process_file(event, chat_id, "url")
        return

    # منطق الصور
    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        res = "✅ تم حفظ الصورة، أرسل الاسم الجديد الآن 📝" if mode == 'both' else "✅ تم حفظ الصورة، أرسل الملف الآن 📁"
        if mode == 'both': user_data[chat_id]['waiting_name'] = True
        await event.reply(res)
        return

    # منطق الأسماء
    if event.text and user_data[chat_id].get('waiting_name'):
        user_data[chat_id]['new_name'] = event.text
        user_data[chat_id]['waiting_name'] = False
        if 'file' in user_data[chat_id]: await process_file(event, chat_id, "file")
        else: await event.reply("✅ تم حفظ الاسم، أرسل الملف الآن 📁")
        return

    # منطق الملفات
    if event.document:
        user_data[chat_id].update({'file': event.document, 'file_name': event.file.name})
        if mode == 'name' and 'new_name' not in user_data[chat_id]:
            user_data[chat_id]['waiting_name'] = True
            await event.reply("✅ أرسل الاسم الجديد للملف 📝")
        else: await process_file(event, chat_id, "file")

async def process_file(event, chat_id, s_type):
    processing_users[chat_id] = "active"
    data = user_data[chat_id]
    sender = await event.get_sender()
    u_name = f"@{sender.username}" if sender.username else "لا يوجد"
    
    status = await event.respond("📡 جاري البدء بالمعالجة...", buttons=[Button.inline("إلغاء ❌", data="cancel_proc")])

    try:
        async def prog_cb(c, t, action, eid, arrow):
            if processing_users.get(chat_id) == "cancelled": raise Exception("user_cancelled")
            now = time.time()
            if chat_id not in prog_cb_last or (now - prog_cb_last[chat_id]) > 8:
                perc = (c * 100 / t) if t > 0 else 0
                txt = f"{arrow} {action} {get_em(eid)} 🚀\n【{'▰'*int(perc/10)}{'▱'*(10-int(perc/10))}】 {round(perc, 2)}%\n{format_size(c)} / {format_size(t)}"
                await status.edit(txt, parse_mode='html')
                prog_cb_last[chat_id] = now

        # التحميل
        if s_type == "url":
            path = data['file_name']
            async with aiohttp.ClientSession() as sess:
                async with sess.get(data['url']) as res:
                    total = int(res.headers.get('content-length', 0))
                    with open(path, 'wb') as f:
                        curr = 0
                        async for chunk in res.content.iter_chunked(1024*1024*8):
                            f.write(chunk); curr += len(chunk)
                            await prog_cb(curr, total, "سحب الرابط", "5406745015365943482", "⬇️")
        else:
            path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "تحميل ملفك", "5406745015365943482", "⬇️"))

        # الرفع (4GB عبر الحساب المميز)
        final_name = f"{data.get('new_name', os.path.splitext(path)[0])}_By_pdfingebot{os.path.splitext(path)[1]}"
        async with user_client:
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t, "رفع 4GB", "5415655814079723871", "⬆️"))
            bot_me = await bot_client.get_me()
            await user_client.send_file(bot_me.id, uploaded, thumb=data.get('thumb'), caption=f"{chat_id}|{u_name}", attributes=[DocumentAttributeFilename(final_name)], force_document=True)
            
        await status.delete()
        if os.path.exists(path): os.remove(path)
    except Exception as e:
        await event.respond(f"❌ خطأ: {e}")
        if chat_id in processing_users: del processing_users[chat_id]
    finally: user_data.pop(chat_id, None)

print("🚀 البوت يعمل الآن بكامل الميزات...")
bot_client.run_until_disconnected()
