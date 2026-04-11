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

user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_data = {}
processing_users = {} # لتخزين حالة الإلغاء والعداد
prog_cb_last = {}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid):
    return f'<emoji id="{eid}">📍</emoji>'

# --- استقبال الملف المكتمل وتوجيهه ---
@bot_client.on(events.NewMessage(incoming=True))
async def forward_to_all(event):
    if event.document and event.sender_id != ADMIN_ID:
        try:
            parts = event.message.message.split("|")
            uid = int(parts[0])
            u_name = parts[1] if len(parts) > 1 else "لا يوجد"
            
            await bot_client.send_file(uid, event.document, caption="✅ تم إنجاز ملفك بنجاح!")
            await bot_client.send_file(ADMIN_ID, event.document, caption=f"✅ ملف مكتمل\n👤 اليوزر: {u_name}\n🆔 الآيدي: `{uid}`")
            
            # بدء عداد الـ 5 دقائق
            asyncio.create_task(cooldown_timer(uid))
        except: pass

async def cooldown_timer(uid):
    processing_users[uid] = "cooldown"
    await asyncio.sleep(300)
    if uid in processing_users and processing_users[uid] == "cooldown":
        del processing_users[uid]
        await bot_client.send_message(uid, f"✅ يمكنك الآن استخدام البوت مرة أخرى {get_em('5413642340789133880')}", parse_mode='html')

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    if chat_id in processing_users:
        return await event.reply("⚠️ يرجى الانتظار حتى اكتمال العملية الحالية أو انتهاء وقت الانتظار.")

    sender = await event.get_sender()
    u_name = f"@{sender.username}" if sender.username else "لا يوجد"
    await bot_client.send_message(ADMIN_ID, f"👤 **دخول:** {sender.first_name}\nاليوزر: {u_name}\nالآيدي: `{chat_id}`")

    msg = (f"اهلا بك {get_em('5418017294473251153')}\n"
           f"وظائف البوت {get_em('5105205613600704262')}:\n"
           f"1- تغيير اسم وصورة الملفات حتى 4GB.\n"
           f"2- تحويل الروابط المباشرة إلى ملفات {get_em('5107633124821436343')}.\n\n"
           f"ماذا تريد ان تفعل الآن؟")
    
    buttons = [
        [Button.inline("تغيير اسم ملف فقط 📝", data="mode_name")],
        [Button.inline("تغيير صورة الملف فقط 🖼️", data="mode_thumb")],
        [Button.inline("تغيير الاسم و الصورة معا 🔄", data="mode_both")],
        [Button.inline("تحويل رابط مباشر إلى ملف 🔗", data="mode_url")]
    ]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()

    if data == "cancel_proc":
        processing_users[chat_id] = "cancelled"
        return await event.answer("✅ تم طلب الإلغاء.. سيتم التوقف فوراً.", alert=True)

    if data.startswith("mode_"):
        mode = data.replace('mode_', '')
        user_data[chat_id] = {'mode': mode}
        
        prompts = {
            'name': "أرسل الملف المطلوب تغيير اسمه 📝",
            'thumb': "أرسل الصورة الجديدة أولاً 🖼️",
            'both': "أرسل الصورة الجديدة أولاً (ثم سنطلب الاسم) 🖼️",
            'url': "أرسل الرابط المباشر الآن 🔗"
        }
        await event.edit(prompts.get(mode, "أرسل المطلوب الآن"), parse_mode='html')

    # أزرار تأكيد اسم الرابط
    elif data == "keep_name":
        await process_url_file(event, chat_id)
    elif data == "change_name_url":
        user_data[chat_id]['waiting_name'] = True
        await event.edit("أرسل الاسم الجديد للملف الآن 📝")

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data or chat_id in processing_users: return
    
    mode = user_data[chat_id]['mode']

    # معالجة الرابط
    if mode == 'url' and event.text.startswith("http"):
        user_data[chat_id]['url'] = event.text
        original_name = event.text.split("/")[-1].split("?")[0] or "file"
        user_data[chat_id]['file_name'] = original_name
        
        msg = f"اسم الملف الحقيقي: `{original_name}`\nهل تود تغيير الاسم؟"
        buttons = [[Button.inline("لا، ابدأ التحميل الآن ⬇️", data="keep_name")],
                   [Button.inline("نعم، أريد تغيير الاسم 📝", data="change_name_url")]]
        await event.reply(msg, buttons=buttons)
        return

    # معالجة الصورة (أولاً في كل الحالات)
    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        if mode == 'both':
            user_data[chat_id]['waiting_name'] = True
            await event.reply("✅ تم حفظ الصورة، أرسل الاسم الجديد للملف الآن.")
        else:
            await event.reply("✅ تم حفظ الصورة، أرسل الملف الآن.")
        return

    # معالجة الاسم
    if event.text and not event.text.startswith('/'):
        if user_data[chat_id].get('waiting_name'):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            if mode == 'url': await process_url_file(event, chat_id)
            elif 'file' in user_data[chat_id]: await process_file(event, chat_id)
            else: await event.reply("✅ تم حفظ الاسم، أرسل الملف الآن.")
            return

    # معالجة الملف
    if event.document:
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        user_data[chat_id]['ext'] = os.path.splitext(event.file.name)[1]
        if mode == 'name' and 'new_name' not in user_data[chat_id]:
            user_data[chat_id]['waiting_name'] = True
            await event.reply("✅ تم حفظ الملف، أرسل الاسم الجديد الآن.")
        else:
            await process_file(event, chat_id)

async def process_file(event, chat_id):
    await run_logic(event, chat_id, "file")

async def process_url_file(event, chat_id):
    await run_logic(event, chat_id, "url")

async def run_logic(event, chat_id, source_type):
    processing_users[chat_id] = "active"
    data = user_data[chat_id]
    sender = await event.get_sender()
    u_name = f"@{sender.username}" if sender.username else "لا يوجد"
    
    status = await event.respond("📡 جاري التحميل...", buttons=[Button.inline("إلغاء المعالجة ❌", data="cancel_proc")])
    
    try:
        async def prog_cb(c, t, action, eid):
            if chat_id in processing_users and processing_users[chat_id] == "cancelled":
                raise Exception("user_cancelled")
            # (نفس منطق العداد السابق مع السرعة)
            ...

        # التحميل (من رابط أو من تليجرام)
        if source_type == "url":
            path = data['file_name'] # منطق تحميل aiohttp
            # ... كود التحميل من الرابط ...
        else:
            path = await bot_client.download_media(data['file'])

        # الرفع عبر الحساب الوسيط للـ 4GB
        async with user_client:
            uploaded = await user_client.upload_file(path)
            # إرسال للبوت مع التوجيه
            ...
            
    except Exception as e:
        if str(e) == "user_cancelled": await event.respond("❌ تم إلغاء العملية بناءً على طلبك.")
        else: await event.respond(f"❌ خطأ: {e}")
    finally:
        if chat_id in processing_users and processing_users[chat_id] != "cooldown":
            del processing_users[chat_id]
        user_data.pop(chat_id, None)

bot_client.run_until_disconnected()
