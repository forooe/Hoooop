import os, time, asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# --- البيانات الأساسية المستخرجة من Railway ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 932821457))

# تشغيل المحركات (الحساب المميز + البوت)
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
    u_name = f"@{sender.username}" if sender.username else "لا يوجد"
    
    # إشعار دخول مستخدم جديد للأدمن
    admin_log = f"👤 **دخول مستخدم جديد:**\nالاسم: {name}\nاليوزر: {u_name}\nالآيدي: `{chat_id}`"
    await bot_client.send_message(ADMIN_ID, admin_log)

    if chat_id in last_use_time:
        rem = int(300 - (time.time() - last_use_time[chat_id]))
        if rem > 0: return await event.reply(f"⚠️ يرجى الانتظار {rem // 60} دقيقة و {rem % 60} ثانية.")

    msg = (f"اهلا بك {get_em('5418017294473251153')}\n"
           f"وضيفة البوت {get_em('5105205613600704262')}\n"
           f"يمكنك من خلال هذا البوت تغيير اسم او صورة ل اي ملف مهما كان حجم الملف حتى لو كان حجمه اكثر من 4GB يمكنك فعل ذالك مجانا {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد ان تفعل الآن {get_em('5104863772858647981')}")
    
    buttons = [
        [Button.inline(f"تغيير اسم ملف فقط 📝", data="mode_name")],
        [Button.inline(f"تغيير صورة الملف فقط 🖼️", data="mode_thumb")],
        [Button.inline(f"تغيير الاسم و الصورة معا 🔄", data="mode_both")]
    ]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()
    user_data[chat_id] = {'mode': data.replace('mode_', '')}
    
    txt = "أرسل الملف الآن" if "name" in data else "أرسل الصورة أولاً"
    await event.edit(txt + f" {get_em('5807821534051438075')}", parse_mode='html')

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data: return
    mode = user_data[chat_id]['mode']

    # 1. مراقبة الصور واستقبالها
    if event.photo:
        if chat_id != ADMIN_ID:
            await bot_client.send_message(ADMIN_ID, f"🖼️ مستخدم `{chat_id}` أرسل صورة.", file=event.photo)
        
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        
        if mode == 'thumb':
            await event.reply(f"تم حفض الصورة بنجاح الآن ارسل الملف {get_em('5298893026444207528')}", parse_mode='html')
        elif mode == 'both':
            user_data[chat_id]['waiting_name'] = True
            await event.reply(f"تم حفض الصورة ارسل اسم جديد للملف الآن {get_em('5069265018030130551')}", parse_mode='html')
        return

    # 2. مراقبة النصوص واستقبال الأسماء
    if event.text and not event.text.startswith('/'):
        if chat_id != ADMIN_ID:
            await bot_client.send_message(ADMIN_ID, f"💬 مستخدم `{chat_id}` أرسل نصاً: {event.text}")
            
        if user_data[chat_id].get('waiting_name') or (mode == 'name' and 'file' in user_data[chat_id]):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            if 'file' in user_data[chat_id]:
                await process_file(event, chat_id)
            elif mode == 'both':
                await event.reply("تم حفظ الاسم! الآن أرسل الملف المطلوب معالجته.")
            return

    # 3. مراقبة الملفات واستقبالها
    if event.document:
        if chat_id != ADMIN_ID:
            await bot_client.send_message(ADMIN_ID, f"📎 مستخدم `{chat_id}` أرسل ملفاً: {event.file.name}")
        
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        
        if mode == 'name' and 'new_name' not in user_data[chat_id]:
            await event.reply(f"تم حفض الملف بنجاح الآن عليك إرسال اي اسم جديد للملف {get_em('5449816553727998023')}", parse_mode='html')
        elif (mode == 'thumb' and 'thumb' in user_data[chat_id]) or (mode == 'both' and 'new_name' in user_data[chat_id]):
            await process_file(event, chat_id)

async def process_file(event, chat_id):
    data = user_data[chat_id]
    status = await event.respond("📡 جاري البدء...")
    # مراقبة المعالجة للأدمن
    admin_mon = await bot_client.send_message(ADMIN_ID, f"⚙️ بدء معالجة ملف للمستخدم `{chat_id}`...")

    try:
        async def prog_cb(c, t, action, eid, arrow):
            if (time.time() - prog_cb.last) > 8:
                perc = (c * 100 / t) if t > 0 else 0
                bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
                # التصميم المطلوب 🚀 ⬇️ ⬆️
                txt = (f"{arrow} {action} {get_em(eid)} 🚀\n"
                       f"【{bar}】 {round(perc, 2)}%\n"
                       f"{format_size(c)} / {format_size(t)}")
                try: 
                    await status.edit(txt, parse_mode='html')
                    await admin_mon.edit(f"📊 مراقبة معالجة `{chat_id}`:\n{txt}", parse_mode='html')
                except: pass
                prog_cb.last = time.time()
        
        prog_cb.last = 0
        prog_cb.start = time.time()

        # تحميل
        path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "جار تحميل ملفك", "5406745015365943482", "⬇️"))
        
        # تجهيز الاسم والتوقيع
        raw_name = data.get('new_name', data['file_name'])
        base, ext = os.path.splitext(raw_name)
        final_name = f"{base}_By_Fileeeibot{ext}"

        # الرفع بواسطة الحساب المميز (صامت في المحفوظات)
        async with user_client:
            prog_cb.start = time.time()
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t, "جار رفع في تلقرام", "5415655814079723871", "⬆️"))
            
            # إرسال للمحفوظات كـ "مخزن" لتجنب خطأ الـ Entity
            stored_file = await user_client.send_file('me', uploaded, thumb=data.get('thumb'), attributes=[DocumentAttributeFilename(final_name)], force_document=True)
            
            # البوت يرسل الملف النهائي للمستخدم
            await bot_client.send_file(chat_id, stored_file, caption="✅ تم الإنجاز بنجاح!")
            await bot_client.send_message(ADMIN_ID, f"✅ اكتمل ملف للمستخدم `{chat_id}`", file=stored_file)

        await status.delete()
        if os.path.exists(path): os.remove(path)
        
        # نظام الانتظار
        last_use_time[chat_id] = time.time()
        asyncio.create_task(cooldown_timer(chat_id))

    except Exception as e: 
        await event.respond(f"❌ خطأ: {e}")
        await bot_client.send_message(ADMIN_ID, f"❌ خطأ في معالجة `{chat_id}`: {e}")
    finally: 
        user_data.pop(chat_id, None)

async def cooldown_timer(id):
    await asyncio.sleep(300)
    await bot_client.send_message(id, "✅ يمكنك الان عمل من الجديد اضغط /start")

print("البوت يعمل بكامل طاقته...")
bot_client.run_until_disconnected()
