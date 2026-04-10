import os, time, asyncio
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
last_use_time = {}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid):
    return f'<emoji id="{eid}">📍</emoji>'

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    sender = await event.get_sender()
    name = sender.first_name
    await bot_client.send_message(ADMIN_ID, f"👤 **دخول:** {name} | `{chat_id}`")
    
    msg = (f"اهلا بك {get_em('5418017294473251153')}\n"
           f"تغيير الملفات حتى 4GB مجاناً {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد ان تفعل الآن؟")
    buttons = [[Button.inline("تغيير اسم 📝", data="mode_name")],
               [Button.inline("تغيير صورة 🖼️", data="mode_thumb")],
               [Button.inline("تغيير الاثنين معا 🔄", data="mode_both")]]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    user_data[event.chat_id] = {'mode': event.data.decode().replace('mode_', '')}
    await event.edit(f"أرسل المطلوب الآن {get_em('5807821534051438075')}", parse_mode='html')

# --- الجزء المسؤول عن استقبال الملف من الحساب وإعادة توجيهه للمستخدم ---
@bot_client.on(events.NewMessage(incoming=True))
async def forwarder(event):
    # إذا وصل ملف للبوت من حسابك البريميوم وفيه آيدي في الوصف
    if event.document and event.sender_id != ADMIN_ID: # للتأكد أنه ليس مستخدماً عادياً
        try:
            target_id = int(event.message.message) # نقرأ الآيدي من الوصف
            await bot_client.send_file(target_id, event.document, caption="✅ تم معالجة ملفك بنجاح!")
        except: pass

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data or event.sender_id == (await bot_client.get_me()).id: return
    
    mode = user_data[chat_id]['mode']

    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        if mode == 'both': user_data[chat_id]['waiting_name'] = True
        await event.reply("✅ تم حفظ الصورة!")
        return

    if event.text and not event.text.startswith('/'):
        if user_data[chat_id].get('waiting_name') or (mode == 'name' and 'file' in user_data[chat_id]):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            if 'file' in user_data[chat_id]: await process_file(event, chat_id)
            else: await event.reply("✅ أرسل الملف الآن.")
            return

    if event.document:
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        user_data[chat_id]['ext'] = os.path.splitext(event.file.name)[1]
        if mode == 'name' and 'new_name' not in user_data[chat_id]: await event.reply("✅ أرسل الاسم الجديد.")
        else: await process_file(event, chat_id)

async def process_file(event, chat_id):
    data = user_data[chat_id]
    status = await event.respond("📡 جاري التحميل والرفع...")
    try:
        path = await bot_client.download_media(data['file'])
        final_name = f"{data.get('new_name', 'file')}_By_Fileeeibot{data.get('ext', '.zip')}"

        async with user_client:
            uploaded = await user_client.upload_file(path)
            bot_info = await bot_client.get_me()
            
            # نرسل الملف للبوت ونضع آيدي المستخدم في الـ caption
            await user_client.send_file(
                bot_info.username, 
                uploaded, 
                thumb=data.get('thumb'), 
                caption=str(chat_id), # هنا نمرر آيدي الشخص
                attributes=[DocumentAttributeFilename(final_name)], 
                force_document=True
            )
            
        await status.delete()
        if os.path.exists(path): os.remove(path)
    except Exception as e: await event.respond(f"❌ خطأ: {e}")
    finally: user_data.pop(chat_id, None)

bot_client.run_until_disconnected()
