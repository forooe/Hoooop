import os, time, asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# --- البيانات الأساسية (تأكد من وضعها في Railway) ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 932821457))

# تشغيل المحركات
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

# --- استقبال الملف المكتمل من الحساب وتوجيهه للمستخدم صاحب الطلب ---
@bot_client.on(events.NewMessage(incoming=True))
async def forward_to_user(event):
    # إذا كان المرسل هو حسابك البريميوم والرسالة تحتوي على ملف
    if event.document and event.sender_id != ADMIN_ID:
        try:
            # نقرأ آيدي المستخدم من الوصف (Caption)
            target_user_id = int(event.message.message)
            await bot_client.send_file(target_user_id, event.document, caption="✅ تم إنجاز ملفك بنجاح!")
        except:
            pass

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    sender = await event.get_sender()
    name = sender.first_name
    
    # إشعار دخول للأدمن
    await bot_client.send_message(ADMIN_ID, f"👤 **دخول مستخدم جديد:**\nالاسم: {name}\nالآيدي: `{chat_id}`")

    msg = (f"اهلا بك {get_em('5418017294473251153')}\n"
           f"وضيفة البوت {get_em('5105205613600704262')}\n"
           f"يمكنك تغيير اسم او صورة اي ملف حتى 4GB مجاناً {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد ان تفعل الآن {get_em('5104863772858647981')}")
    
    buttons = [
        [Button.inline("تغيير اسم ملف فقط 📝", data="mode_name")],
        [Button.inline("تغيير صورة الملف فقط 🖼️", data="mode_thumb")],
        [Button.inline("تغيير الاسم و الصورة معا 🔄", data="mode_both")]
    ]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    user_data[chat_id] = {'mode': event.data.decode().replace('mode_', '')}
    
    mode_text = "أرسل الملف الآن" if "name" in event.data.decode() else "أرسل الصورة أولاً"
    await event.edit(f"{mode_text} {get_em('5807821534051438075')}", parse_mode='html')

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    # نتجنب معالجة رسائل البوت لنفسه
    bot_obj = await bot_client.get_me()
    if chat_id not in user_data or event.sender_id == bot_obj.id: return
    
    mode = user_data[chat_id]['mode']

    # 1. استقبال الصورة
    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        if mode == 'both':
            user_data[chat_id]['waiting_name'] = True
            await event.reply(f"تم حفظ الصورة، أرسل الاسم الجديد الآن {get_em('5069265018030130551')}", parse_mode='html')
        else:
            await event.reply(f"تم حفظ الصورة، أرسل الملف الآن {get_em('5298893026444207528')}", parse_mode='html')
        return

    # 2. استقبال الاسم الجديد
    if event.text and not event.text.startswith('/'):
        if user_data[chat_id].get('waiting_name') or (mode == 'name' and 'file' in user_data[chat_id]):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            if 'file' in user_data[chat_id]:
                await process_file(event, chat_id)
            else:
                await event.reply(f"تم حفظ الاسم، أرسل الملف المطلوب {get_em('5449816553727998023')}", parse_mode='html')
            return

    # 3. استقبال الملف
    if event.document:
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        user_data[chat_id]['original_ext'] = os.path.splitext(event.file.name)[1]
        
        if mode == 'name' and 'new_name' not in user_data[chat_id]:
            await event.reply(f"أرسل الآن الاسم الجديد للملف {get_em('5449816553727998023')}", parse_mode='html')
        elif (mode == 'thumb' and 'thumb' in user_data[chat_id]) or (mode == 'both' and 'new_name' in user_data[chat_id]):
            await process_file(event, chat_id)

async def process_file(event, chat_id):
    data = user_data[chat_id]
    status = await event.respond("📡 جاري البدء...")
    admin_mon = await bot_client.send_message(ADMIN_ID, f"⚙️ معالجة ملف لـ `{chat_id}`...")

    try:
        async def prog_cb(c, t, action, eid, arrow):
            if (time.time() - prog_cb.last) > 8:
                perc = (c * 100 / t) if t > 0 else 0
                bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
                txt = (f"{arrow} {action} {get_em(eid)} 🚀\n"
                       f"【{bar}】 {round(perc, 2)}%\n"
                       f"{format_size(c)} / {format_size(t)}")
                try:
                    await status.edit(txt, parse_mode='html')
                    await admin_mon.edit(f"📊 مراقبة `{chat_id}`:\n{txt}", parse_mode='html')
                except: pass
                prog_cb.last = time.time()
        
        prog_cb.last = 0
        # تحميل الملف للسيرفر
        path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "جار تحميل ملفك", "5406745015365943482", "⬇️"))
        
        # تجهيز الاسم النهائي مع الحفاظ على الصيغة الأصلية
        ext = data.get('original_ext', os.path.splitext(data['file_name'])[1])
        final_name = f"{data.get('new_name', os.path.splitext(data['file_name'])[0])}_By_Fileeeibot{ext}"

        async with user_client:
            # الرفع عبر الحساب المميز
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t, "جار رفع في تلقرام", "5415655814079723871", "⬆️"))
            
            bot_info = await bot_client.get_me()
            # إرسال الملف من الحساب إلى البوت مع وضع الآيدي في الوصف
            sent_to_bot = await user_client.send_file(
                bot_info.username, 
                uploaded, 
                thumb=data.get('thumb'), 
                caption=str(chat_id), # الرقم السري للتوجيه
                attributes=[DocumentAttributeFilename(final_name)], 
                force_document=True
            )
            
            # نسخة للأدمن للمراقبة النهائية
            await bot_client.send_file(ADMIN_ID, sent_to_bot, caption=f"✅ اكتمل للمستخدم `{chat_id}`")

        await status.delete()
        if os.path.exists(path): os.remove(path)
        
        # نظام الانتظار (اختياري يمكنك تفعيله)
        last_use_time[chat_id] = time.time()

    except Exception as e:
        await event.respond(f"❌ خطأ: {e}")
    finally:
        user_data.pop(chat_id, None)

print("البوت المتكامل يعمل الآن...")
bot_client.run_until_disconnected()
