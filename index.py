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
processing_users = set() 
cooldown_users = {}   
prog_cb_last = {}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid):
    return f'<emoji id="{eid}">📍</emoji>'

# --- دالة العداد التنازلي للمستخدم ---
async def start_cooldown(chat_id, message_obj):
    cooldown_users[chat_id] = time.time() + 300 
    for i in range(300, 0, -5):
        if chat_id not in cooldown_users: break
        mins, secs = divmod(i, 60)
        try:
            await message_obj.edit(f"✅ تم إنجاز ملفك بنجاح!\n⏳ يرجى الانتظار للمعالجة التالية: {mins:02d}:{secs:02d}")
        except: pass
        await asyncio.sleep(5)
    
    cooldown_users.pop(chat_id, None)
    await bot_client.send_message(chat_id, "✅ حسناً الآن يمكنك العمل من جديد")

@bot_client.on(events.NewMessage(incoming=True))
async def forward_to_all(event):
    if event.document and event.sender_id != ADMIN_ID:
        try:
            caption_parts = event.message.message.split("|")
            target_user_id = int(caption_parts[0])
            user_username = caption_parts[1] if len(caption_parts) > 1 else "لا يوجد"
            
            # إرسال للمستخدم وبدء العداد
            msg = await bot_client.send_file(target_user_id, event.document, caption="✅ تم إنجاز ملفك بنجاح!")
            asyncio.create_task(start_cooldown(target_user_id, msg))
            
            # إرسال نسخة للأدمن (كما في كودك الأصلي)
            await bot_client.send_file(ADMIN_ID, event.document, caption=f"✅ ملف مكتمل\n👤 اليوزر: {user_username}\n🆔 الآيدي: `{target_user_id}`")
            
            if target_user_id in processing_users:
                processing_users.remove(target_user_id)
        except: pass

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    if chat_id in cooldown_users:
        rem = int(cooldown_users[chat_id] - time.time())
        mins, secs = divmod(rem, 60)
        return await event.reply(f"⚠️ يرجى الانتظار حتى ينتهي العداد: {mins:02d}:{secs:02d}")
    
    if chat_id in processing_users:
        return await event.reply(f"⚠️ يرجى الانتظار حتى اكتمال معالجة ملفك الحالي", parse_mode='html')

    sender = await event.get_sender()
    username = f"@{sender.username}" if sender.username else "لا يوجد يوزر"
    
    # إشعار دخول للأدمن
    await bot_client.send_message(ADMIN_ID, f"👤 **دخول مستخدم جديد:**\nالاسم: {sender.first_name}\nاليوزر: {username}\nالآيدي: `{chat_id}`")

    msg = (f"اهلا بك {sender.first_name} {get_em('5418017294473251153')}\n"
           f"وضيفة البوت تغيير صورة الملفات حتى لو كان اكثر من 4GB سيتم تغييره مجانا\n\n"
           f"ماذا تريد ان تعمل الآن؟")
    
    buttons = [[Button.inline("تغيير الاسم فقط 📝", data="mode_name")],
               [Button.inline("تغيير الصوره فقط 🖼️", data="mode_thumb")],
               [Button.inline("تغيير الاسم و صوره معا 🔄", data="mode_both")]]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()

    if data == "cancel_proc":
        if chat_id in processing_users: processing_users.remove(chat_id)
        user_data.pop(chat_id, None)
        return await event.edit("❌ تم إلغاء المعالجة بنجاح.")

    if chat_id in processing_users:
        return await event.answer("⚠️ لديك عملية معالجة قائمة حالياً!", alert=True)
    
    mode = data.replace('mode_', '')
    user_data[chat_id] = {'mode': mode}
    
    if mode == "name":
        await event.edit(f"ارسل الاسم الان {get_em('5807821534051438075')}", parse_mode='html')
    elif mode == "thumb" or mode == "both":
        await event.edit(f"ارسل صوره الان {get_em('5807821534051438075')}", parse_mode='html')

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    me = await bot_client.get_me()
    if event.sender_id == me.id: return
    if chat_id in processing_users or chat_id in cooldown_users: return 
    if chat_id not in user_data: return

    mode = user_data[chat_id]['mode']

    # استقبال الصورة + إرسالها للأدمن للمراقبة
    if event.photo:
        sender = await event.get_sender()
        username = f"@{sender.username}" if sender.username else "لا يوجد يوزر"
        if chat_id != ADMIN_ID:
            await bot_client.send_message(ADMIN_ID, f"🖼️ المستخدم {username} أرسل صورة:", file=event.photo)
        
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        
        if mode == 'both':
            user_data[chat_id]['waiting_name'] = True
            await event.reply("✅ تم حفظ الصورة، ارسل الاسم الان")
        else:
            await event.reply("✅ تم حفظ الصورة، أرسل الملف الآن.")
        return

    # استقبال الاسم
    if event.text and not event.text.startswith('/'):
        if mode == 'name' or (mode == 'both' and user_data[chat_id].get('waiting_name')):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            if mode == 'name':
                await event.reply("✅ تم حفظ الاسم، أرسل الملف الآن.")
            else:
                await event.reply("✅ تم حفظ الاسم، أرسل الملف الآن.")
            return

    # استقبال الملف
    if event.document:
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        user_data[chat_id]['ext'] = os.path.splitext(event.file.name)[1]
        
        # التأكد من اكتمال البيانات قبل المعالجة
        can_process = False
        if mode == 'name' and 'new_name' in user_data[chat_id]: can_process = True
        elif mode == 'thumb' and 'thumb' in user_data[chat_id]: can_process = True
        elif mode == 'both' and 'thumb' in user_data[chat_id] and 'new_name' in user_data[chat_id]: can_process = True
        
        if can_process:
            await process_file(event, chat_id)
        else:
            await event.reply("⚠️ يرجى إرسال (الاسم/الصورة) أولاً حسب اختيارك.")

async def process_file(event, chat_id):
    processing_users.add(chat_id)
    data = user_data[chat_id]
    
    sender = await event.get_sender()
    username = f"@{sender.username}" if sender.username else "لا يوجد يوزر"
    
    # رسالة الحالة للمستخدم مع زر الإلغاء
    status = await event.respond("📡 جاري البدء بالمعالجة...", buttons=[Button.inline("إلغاء المعالجة ❌", data="cancel_proc")])
    # رسالة المراقبة للأدمن
    admin_mon = await bot_client.send_message(ADMIN_ID, f"⚙️ بدء معالجة ملف\n👤 المستخدم: {username}\n🆔 الآيدي: `{chat_id}`")

    try:
        async def prog_cb(c, t, action, eid, arrow):
            if chat_id not in processing_users: raise Exception("CanceledByUser")
            now = time.time()
            if chat_id not in prog_cb_last or (now - prog_cb_last[chat_id]) > 8:
                perc = (c * 100 / t) if t > 0 else 0
                bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
                txt = f"{arrow} {action} {get_em(eid)} 🚀\n【{bar}】 {round(perc, 2)}%\n{format_size(c)} / {format_size(t)}"
                try:
                    await status.edit(txt, buttons=[Button.inline("إلغاء المعالجة ❌", data="cancel_proc")], parse_mode='html')
                    await admin_mon.edit(f"📊 مراقبة {username}:\n{txt}", parse_mode='html')
                except: pass
                prog_cb_last[chat_id] = now
        
        # 1. التحميل
        path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "جار تحميل ملفك", "5406745015365943482", "⬇️"))
        
        ext = data.get('ext', os.path.splitext(data['file_name'])[1])
        final_name = f"{data.get('new_name', os.path.splitext(data['file_name'])[0])}{ext}"

        # 2. الرفع عبر الحساب المميز
        async with user_client:
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t, "جار رفع في تلقرام", "5415655814079723871", "⬆️"))
            bot_info = await bot_client.get_me()
            
            await user_client.send_file(
                bot_info.username, 
                uploaded, 
                thumb=data.get('thumb'), 
                caption=f"{chat_id}|{username}", 
                attributes=[DocumentAttributeFilename(final_name)], 
                force_document=True
            )
            
        await status.delete()
        if os.path.exists(path): os.remove(path)
        if data.get('thumb') and os.path.exists(data['thumb']): os.remove(data['thumb'])
        
    except Exception as e:
        if str(e) == "CanceledByUser":
            await admin_mon.edit(f"🛑 قام المستخدم {username} بإلغاء العملية.")
        else:
            await event.respond(f"❌ خطأ: {e}")
            await bot_client.send_message(ADMIN_ID, f"❌ خطأ مع {username}: {e}")
        if chat_id in processing_users: processing_users.remove(chat_id)
    finally:
        user_data.pop(chat_id, None)

print("البوت يعمل بنظام المراقبة والعداد...")
bot_client.run_until_disconnected()
