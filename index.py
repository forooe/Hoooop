import os, time, asyncio, aiohttp
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# --- البيانات الأساسية ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 932821457))

# تشغيل الحساب المميز والبوت
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

# --- استقبال الملف المكتمل من الحساب وتوزيعه ---
@bot_client.on(events.NewMessage(incoming=True))
async def forwarder(event):
    if event.document and event.is_private and event.sender_id != ADMIN_ID:
        try:
            parts = event.message.message.split("|")
            uid, u_name = int(parts[0]), parts[1]
            await bot_client.send_file(uid, event.document, caption="✅ تم إنجاز ملفك بنجاح!")
            await bot_client.send_file(ADMIN_ID, event.document, caption=f"✅ اكتمل لـ {u_name}\n🆔 `{uid}`")
            processing_users[uid] = "cooldown"
            asyncio.create_task(cooldown_timer(uid))
        except: pass

async def cooldown_timer(uid):
    await asyncio.sleep(300) # عداد 5 دقائق
    if uid in processing_users: del processing_users[uid]
    await bot_client.send_message(uid, "✅ يمكنك الآن البدء بعملية جديدة!")

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    if chat_id in processing_users: return await event.reply("⚠️ يرجى الانتظار.")
    sender = await event.get_sender()
    u_name = f"@{sender.username}" if sender.username else "لا يوجد"
    await bot_client.send_message(ADMIN_ID, f"👤 دخول: {sender.first_name}\nيوزر: {u_name}")
    
    msg = (f"أهلاً بك يا {sender.first_name} في بوت الرفع المطور 🚀\n\n"
           f"أصبح بإمكاني الآن:\n"
           f"1- تغيير اسم وصورة الملفات (4GB) 🖼️\n"
           f"2- تحويل الروابط المباشرة لملفات تليجرام 🔗\n\n"
           f"ماذا تريد أن تفعل الآن؟")
    
    buttons = [[Button.inline("تغيير اسم ملف 📝", data="mode_name")],
               [Button.inline("تغيير صورة ملف 🖼️", data="mode_thumb")],
               [Button.inline("تغيير الاثنين معاً 🔄", data="mode_both")],
               [Button.inline("تحويل رابط مباشر 🔗", data="mode_url")]]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()
    if data == "cancel_proc":
        processing_users[chat_id] = "cancelled"
        return await event.answer("✅ سيتم الإلغاء..", alert=True)
    if data.startswith("mode_"):
        user_data[chat_id] = {'mode': data.replace('mode_', '')}
        txt = "أرسل الرابط 🔗" if "url" in data else "أرسل الصورة أولاً 🖼️" if "thumb" in data or "both" in data else "أرسل الملف 📁"
        await event.edit(txt)
    elif data == "keep_name": await run_logic(event, chat_id, "url")
    elif data == "change_name_url":
        user_data[chat_id]['waiting_name'] = True
        await event.edit("أرسل الاسم الجديد للملف الآن 📝")

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data or chat_id in processing_users: return
    mode = user_data[chat_id]['mode']

    if mode == 'url' and event.text and event.text.startswith("http"):
        user_data[chat_id]['url'] = event.text
        name = event.text.split("/")[-1].split("?")[0] or "file"
        user_data[chat_id]['file_name'] = name
        buttons = [[Button.inline("لا، ابدأ ⬇️", data="keep_name")], [Button.inline("نعم، تغيير 📝", data="change_name_url")]]
        await event.reply(f"اسم الملف: `{name}`\nتغيير الاسم؟", buttons=buttons)
        return

    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        user_data[chat_id]['waiting_name'] = (mode == 'both')
        await event.reply("✅ تم حفظ الصورة، أرسل " + ("الاسم الجديد" if mode == 'both' else "الملف"))
        return

    if event.text and not event.text.startswith('/') and user_data[chat_id].get('waiting_name'):
        user_data[chat_id]['new_name'] = event.text
        user_data[chat_id]['waiting_name'] = False
        if mode == 'url': await run_logic(event, chat_id, "url")
        elif 'file' in user_data[chat_id]: await run_logic(event, chat_id, "file")
        else: await event.reply("✅ تم حفظ الاسم، أرسل الملف.")
        return

    if event.document:
        user_data[chat_id].update({'file': event.document, 'file_name': event.file.name, 'ext': os.path.splitext(event.file.name)[1]})
        if mode == 'name' and 'new_name' not in user_data[chat_id]:
            user_data[chat_id]['waiting_name'] = True
            await event.reply("✅ أرسل الاسم الجديد الآن.")
        else: await run_logic(event, chat_id, "file")

async def run_logic(event, chat_id, source_type):
    processing_users[chat_id] = "active"
    data = user_data[chat_id]
    u_name = f"@{event.sender.username}" if event.sender.username else "لا يوجد"
    status = await event.respond("📡 جاري البدء...", buttons=[Button.inline("إلغاء المعالجة ❌", data="cancel_proc")])
    
    try:
        async def prog_cb(c, t, action, eid, arrow):
            if processing_users.get(chat_id) == "cancelled": raise Exception("user_cancelled")
            now = time.time()
            if chat_id not in prog_cb_last or (now - prog_cb_last[chat_id]) > 8:
                perc = (c * 100 / t) if t > 0 else 0
                txt = f"{arrow} {action} {get_em(eid)} 🚀\n【{'▰'*int(perc/10)}{'▱'*(10-int(perc/10))}】 {round(perc,2)}%\n{format_size(c)} / {format_size(t)}"
                await status.edit(txt, parse_mode='html')
                prog_cb_last[chat_id] = now

        if source_type == "url":
            path = data['file_name']
            async with aiohttp.ClientSession() as sess:
                async with sess.get(data['url']) as res:
                    total = int(res.headers.get('content-length', 0))
                    curr = 0
                    with open(path, 'wb') as f:
                        async for chunk in res.content.iter_chunked(1024*1024*8):
                            f.write(chunk)
                            curr += len(chunk)
                            await prog_cb(curr, total, "جاري التحميل", "5406745015365943482", "⬇️")
        else:
            path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t,"تحميل ملفك","5406745015365943482","⬇️"))

        ext = data.get('ext', os.path.splitext(path)[1])
        final_name = f"{data.get('new_name', os.path.splitext(path)[0])}_By_pdfingebot{ext}"
        
        async with user_client:
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t,"رفع لتليجرام","5415655814079723871","⬆️"))
            bot_me = await bot_client.get_me()
            await user_client.send_file(bot_me.id, uploaded, thumb=data.get('thumb'), caption=f"{chat_id}|{u_name}", attributes=[DocumentAttributeFilename(final_name)], force_document=True)
            
        await status.delete()
        if os.path.exists(path): os.remove(path)
    except Exception as e:
        await event.respond(f"❌ {'تم الإلغاء' if 'cancelled' in str(e) else f'خطأ: {e}'}")
        if chat_id in processing_users: del processing_users[chat_id]
    finally: user_data.pop(chat_id, None)

bot_client.run_until_disconnected()
