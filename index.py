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

user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, connection_retries=None)
bot_client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_data = {}
processing_users = set() 
waiting_cooldown = set() # قائمة الانتظار لمنع الـ start المتكرر
cancelled_processes = set()
prog_cb_last = {}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid):
    return f'<emoji id="{eid}">📍</emoji>'

@bot_client.on(events.NewMessage(incoming=True))
async def forward_to_all(event):
    if event.document and event.is_private and event.sender_id != ADMIN_ID:
        try:
            caption_parts = event.message.message.split("|")
            target_user_id = int(caption_parts[0])
            user_username = caption_parts[1] if len(caption_parts) > 1 else "لا يوجد"
            
            await bot_client.send_file(target_user_id, event.document, caption="✅ تم إنجاز ملفك بنجاح!")
            await bot_client.send_file(ADMIN_ID, event.document, caption=f"✅ ملف مكتمل\n👤 اليوزر: {user_username}\n🆔 الآيدي: `{target_user_id}`")
            
            # بدء العداد الحقيقي الذي يمنع المستخدم من العمل
            asyncio.create_task(cooldown_timer(target_user_id))
            
            if target_user_id in processing_users:
                processing_users.remove(target_user_id)
        except: pass

async def cooldown_timer(chat_id):
    """العداد الذي يمنع المستخدم فعلياً من البدء مرة أخرى"""
    waiting_cooldown.add(chat_id)
    msg = await bot_client.send_message(chat_id, "⏳ جاري بدء مؤقت الانتظار...")
    
    for i in range(300, 0, -10):
        if chat_id not in waiting_cooldown: break # لضمان عدم التداخل
        mins, secs = divmod(i, 60)
        try: await msg.edit(f"⏳ يرجى الانتظار {mins:02d}:{secs:02d} لإرسال ملف جديد...")
        except: pass
        await asyncio.sleep(10)
    
    await msg.edit("✅ يمكنك الآن العمل من جديد!")
    if chat_id in waiting_cooldown:
        waiting_cooldown.remove(chat_id)

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    
    # منع المستخدم إذا كان قيد المعالجة أو في وقت العداد (الانتظار)
    if chat_id in processing_users or chat_id in waiting_cooldown:
        return await event.reply(f"⚠️ **عذراً!** لا يمكنك البدء الآن، يرجى الانتظار حتى انتهاء المعالجة أو العداد الزمني {get_em('5413642340789133880')}", parse_mode='html')

    sender = await event.get_sender()
    first_name = sender.first_name
    username = f"@{sender.username}" if sender.username else "لا يوجد يوزر"
    
    await bot_client.send_message(ADMIN_ID, f"👤 **دخول مستخدم جديد:**\nالاسم: {first_name}\nاليوزر: {username}\nالآيدي: `{chat_id}`")

    msg = (f"اهلا بك {first_name} {get_em('5418017294473251153')}\n"
           f"وظيفة البوت تغيير صورة واسم الملفات حتى لو كان 4GB مجاناً {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد انت تفعل الان؟")
    
    buttons = [[Button.inline("تغيير اسم 📝", data="mode_name")],
               [Button.inline("تغيير صورة 🖼️", data="mode_thumb")],
               [Button.inline("تغيير الاثنين معا 🔄", data="mode_both")]]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()

    if data == "cancel_p":
        cancelled_processes.add(chat_id)
        return await event.answer("❌ تم إرسال طلب الإلغاء...", alert=True)

    if chat_id in processing_users or chat_id in waiting_cooldown:
        return await event.answer("⚠️ البوت في حالة انتظار حالياً!", alert=True)
    
    user_data[chat_id] = {'mode': data.replace('mode_', '')}
    
    # تخصيص رسالة الرد حسب نوع الزر
    if data == "mode_name":
        res_msg = "وظيفة الزر: **تغيير اسم الملف 📝**\n\nأرسل الاسم الجديد للملف الآن."
    elif data == "mode_thumb":
        res_msg = "وظيفة الزر: **تغيير صورة الملف 🖼️**\n\nأرسل الصورة الجديدة أولاً."
    elif data == "mode_both":
        res_msg = "وظيفة الزر: **تغيير الاسم والصورة معاً 🔄**\n\nأرسل الصورة المطلوبة أولاً."
    
    await event.edit(f"{res_msg} {get_em('5807821534051438075')}", parse_mode='html')

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    me = await bot_client.get_me()
    if event.sender_id == me.id: return
    if chat_id in processing_users or chat_id in waiting_cooldown: return 

    if chat_id not in user_data: return
    mode = user_data[chat_id]['mode']

    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        res = "✅ تم حفظ الصورة، أرسل الاسم الجديد." if mode == 'both' else "✅ تم حفظ الصورة، أرسل الملف."
        if mode == 'both': user_data[chat_id]['waiting_name'] = True
        await event.reply(res)
        return

    if event.text and not event.text.startswith('/'):
        if user_data[chat_id].get('waiting_name') or (mode == 'name' and 'file' in user_data[chat_id]):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            if 'file' in user_data[chat_id]: await process_file(event, chat_id)
            else: await event.reply("✅ تم حفظ الاسم، أرسل الملف.")
            return

    if event.document:
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        user_data[chat_id]['ext'] = os.path.splitext(event.file.name)[1]
        if mode == 'name' and 'new_name' not in user_data[chat_id]:
            await event.reply("✅ أرسل الاسم الجديد للملف.")
        else:
            await process_file(event, chat_id)

async def process_file(event, chat_id):
    processing_users.add(chat_id)
    if chat_id in cancelled_processes: cancelled_processes.remove(chat_id)
    
    data = user_data[chat_id]
    sender = await event.get_sender()
    username = f"@{sender.username}" if sender.username else "لا يوجد يوزر"
    
    cancel_btn = [Button.inline("إلغاء المعالجة ❌", data="cancel_p")]
    status = await event.respond("📡 جاري البدء بالمعالجة...", buttons=cancel_btn)

    try:
        async def prog_cb(c, t, action, eid, arrow):
            if chat_id in cancelled_processes:
                raise Exception("CANCELLED_BY_USER")
            now = time.time()
            if chat_id not in prog_cb_last or (now - prog_cb_last[chat_id]) > 8:
                perc = (c * 100 / t) if t > 0 else 0
                bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
                txt = f"{arrow} {action} {get_em(eid)} 🚀\n【{bar}】 {round(perc, 2)}%\n{format_size(c)} / {format_size(t)}"
                try: await status.edit(txt, parse_mode='html', buttons=cancel_btn)
                except: pass
                prog_cb_last[chat_id] = now
        
        path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "جار تحميل ملفك", "5406745015365943482", "⬇️"))
        
        ext = data.get('ext', os.path.splitext(data['file_name'])[1])
        final_name = f"{data.get('new_name', os.path.splitext(data['file_name'])[0])}_By_Ali{ext}"

        async with user_client:
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t, "جار رفع في تلقرام", "5415655814079723871", "⬆️"))
            bot_info = await bot_client.get_me()
            await user_client.send_file(bot_info.username, uploaded, thumb=data.get('thumb'), caption=f"{chat_id}|{username}", attributes=[DocumentAttributeFilename(final_name)], force_document=True)
            
        await status.delete()
        if os.path.exists(path): os.remove(path)
        
    except Exception as e:
        if str(e) == "CANCELLED_BY_USER":
            await event.respond("❌ تم إلغاء المعالجة بنجاح.")
        else:
            await event.respond(f"❌ خطأ: {e}")
            
        if chat_id in processing_users: processing_users.remove(chat_id)
        if chat_id in cancelled_processes: cancelled_processes.remove(chat_id)
    finally:
        user_data.pop(chat_id, None)

print("تم التحديث: العداد الآن يمنع الـ Start المتكرر والأزرار تعطي الوظيفة فوراً.")
bot_client.run_until_disconnected()
