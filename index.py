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
processing_users = {} # سنخزن فيه وقت انتهاء الانتظار أيضاً
cooldown_users = {}   # لمتابعة وقت الانتظار 5 دقائق

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid):
    return f'<emoji id="{eid}">📍</emoji>'

# --- دالة العداد التنازلي ---
async def start_cooldown(chat_id, message_obj):
    cooldown_users[chat_id] = time.time() + 300 # 5 دقائق
    for i in range(300, 0, -5): # تحديث كل 5 ثوانٍ لتقليل الضغط على التليجرام
        if chat_id not in cooldown_users: break
        mins, secs = divmod(i, 60)
        try:
            await message_obj.edit(f"✅ تم إرسال ملفك! يرجى الانتظار للمعالجة التالية:\n⏳ المتبقي: {mins:02d}:{secs:02d}")
        except: pass
        await asyncio.sleep(5)
    
    cooldown_users.pop(chat_id, None)
    await bot_client.send_message(chat_id, "✅ حسناً، الآن يمكنك العمل من جديد!")

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
            
            await bot_client.send_file(ADMIN_ID, event.document, caption=f"✅ ملف مكتمل\n👤 اليوزر: {user_username}\n🆔 الآيدي: `{target_user_id}`")
            
            if target_user_id in processing_users:
                processing_users.pop(target_user_id)
        except: pass

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    
    # التحقق من العداد
    if chat_id in cooldown_users:
        rem = int(cooldown_users[chat_id] - time.time())
        mins, secs = divmod(rem, 60)
        return await event.reply(f"⚠️ يرجى الانتظار حتى ينتهي العداد: {mins:02d}:{secs:02d}")

    if chat_id in processing_users:
        return await event.reply(f"⚠️ جاري معالجة ملفك بالفعل!")

    sender = await event.get_sender()
    name = sender.first_name
    username = f"@{sender.username}" if sender.username else "لا يوجد يوزر"
    
    await bot_client.send_message(ADMIN_ID, f"👤 **دخول جديد:** {name}\nاليوزر: {username}")

    msg = (f"أهلاً بك {name} {get_em('5418017294473251153')}\n"
           f"وظيفة البوت تغيير صورة الملفات حتى لو كان أكثر من 4GB سيتم تغييره مجاناً {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد ان تعمل الآن؟")
    
    buttons = [
        [Button.inline("تغيير الاسم فقط 📝", data="mode_name")],
        [Button.inline("تغيير الصورة فقط 🖼️", data="mode_thumb")],
        [Button.inline("تغيير الاسم والصورة معاً 🔄", data="mode_both")]
    ]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()

    if data == "cancel":
        processing_users.pop(chat_id, None)
        user_data.pop(chat_id, None)
        return await event.edit("❌ تم إلغاء المعالجة.")

    if chat_id in cooldown_users: return await event.answer("انتظر انتهاء العداد!", alert=True)
    
    mode = data.replace('mode_', '')
    user_data[chat_id] = {'mode': mode}
    
    if mode == "name":
        await event.edit("📝 أرسل الاسم الجديد الآن:")
    elif mode == "thumb" or mode == "both":
        await event.edit("🖼️ أرسل الصورة الجديدة الآن أولاً:")

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if event.sender_id == (await bot_client.get_me()).id: return
    if chat_id in cooldown_users or chat_id in processing_users: return
    if chat_id not in user_data: return

    mode = user_data[chat_id]['mode']

    # استقبال الصورة
    if event.photo:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        
        if mode == 'both':
            user_data[chat_id]['waiting_name'] = True
            await event.reply("✅ تم حفظ الصورة، أرسل الآن الاسم الجديد:")
        else:
            await event.reply("✅ تم حفظ الصورة، أرسل الآن الملف (الفيديو/المستند):")
        return

    # استقبال الاسم
    if event.text and not event.text.startswith('/'):
        if mode == 'name' or (mode == 'both' and user_data[chat_id].get('waiting_name')):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            await event.reply("✅ تم حفظ الاسم، أرسل الآن الملف:")
            return

    # استقبال الملف
    if event.document:
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        # التحقق من اكتمال المتطلبات حسب الوضع
        ready = False
        if mode == 'name' and 'new_name' in user_data[chat_id]: ready = True
        if mode == 'thumb' and 'thumb' in user_data[chat_id]: ready = True
        if mode == 'both' and 'thumb' in user_data[chat_id] and 'new_name' in user_data[chat_id]: ready = True
        
        if ready:
            await process_file(event, chat_id)
        else:
            await event.reply("⚠️ يرجى إرسال المتطلبات (الاسم أو الصورة) قبل إرسال الملف.")

async def process_file(event, chat_id):
    processing_users[chat_id] = True
    data = user_data[chat_id]
    
    status = await event.respond("📡 جاري البدء بالمعالجة...", buttons=[Button.inline("إلغاء المعالجة ❌", data="cancel")])

    try:
        async def prog_cb(c, t, action):
            if chat_id not in processing_users: raise Exception("Canceled")
            # تحديث شريط التحميل (نفس الكود الأصلي لديك)
            perc = (c * 100 / t) if t > 0 else 0
            bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
            txt = f"{action}...\n【{bar}】 {round(perc, 2)}%\n{format_size(c)} / {format_size(t)}"
            try: await status.edit(txt, buttons=[Button.inline("إلغاء المعالجة ❌", data="cancel")])
            except: pass
        
        path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "📥 جاري التحميل"))
        
        ext = os.path.splitext(data['file_name'])[1]
        final_name = f"{data.get('new_name', os.path.splitext(data['file_name'])[0])}{ext}"

        async with user_client:
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t, "📤 جاري الرفع"))
            bot_info = await bot_client.get_me()
            await user_client.send_file(
                bot_info.username, 
                uploaded, 
                thumb=data.get('thumb'), 
                caption=f"{chat_id}|User", 
                attributes=[DocumentAttributeFilename(final_name)], 
                force_document=True
            )
            
        await status.delete()
        if os.path.exists(path): os.remove(path)
        if data.get('thumb') and os.path.exists(data['thumb']): os.remove(data['thumb'])

    except Exception as e:
        if str(e) == "Canceled": pass
        else: await event.respond(f"❌ حدث خطأ: {e}")
    finally:
        user_data.pop(chat_id, None)

print("البوت يعمل الآن...")
bot_client.run_until_disconnected()
