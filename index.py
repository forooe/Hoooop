import os, time, asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# --- البيانات المستخرجة من ريلوي ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 932821457))

# تشغيل المحركات
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_data = {}
last_use_time = {} # نظام الانتظار

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0

def get_em(eid, alt=""):
    return f'<emoji id="{eid}">{alt}</emoji>'

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    chat_id = event.chat_id
    
    # التحقق من وقت الانتظار
    if chat_id in last_use_time:
        rem_time = int(300 - (time.time() - last_use_time[chat_id]))
        if rem_time > 0:
            return await event.reply(f"⚠️ يرجى الانتظار {rem_time // 60} دقيقة و {rem_time % 60} ثانية قبل المحاولة مجدداً.")

    sender = await event.get_sender()
    admin_msg = f"👤 مستخدم جديد:\n@{sender.username} | `{chat_id}`"
    await bot_client.send_message(ADMIN_ID, admin_msg)

    msg = (f"اهلا بك {get_em('5418017294473251153')}\n"
           f"وضيفة البوت {get_em('5105205613600704262')}\n"
           f"يمكنك من خلال هذا البوت تغيير اسم او صورة ل اي ملف مهما كان حجم الملف حتى لو كان حجمه اكثر من 4GB يمكنك فعل ذالك مجانا {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد ان تفعل الآن {get_em('5104863772858647981')}")
    
    buttons = [
        [Button.inline(f"تغيير اسم ملف فقط {get_em('5332724926216428039')}", data="mode_name")],
        [Button.inline(f"تغيير صورة الملف فقط {get_em('5215638109068220476')}", data="mode_thumb")],
        [Button.inline(f"تغيير الاسم و الصورة معا {get_em('5244672079399248361')}", data="mode_both")]
    ]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()
    if data == "mode_name":
        user_data[chat_id] = {'mode': 'name'}
        await event.edit(f"حسنا عليك الآن إرسال الملف لتغيير اسمه {get_em('5936017305585586269')}", parse_mode='html')
    elif data == "mode_thumb":
        user_data[chat_id] = {'mode': 'thumb'}
        await event.edit(f"حسنا ارسل صورة الملف الذي تود ان تضعه في ملفك {get_em('6269288252151173172')}", parse_mode='html')
    elif data == "mode_both":
        user_data[chat_id] = {'mode': 'both'}
        await event.edit(f"حسنا الآن ارسل اولاً الصوره ليتم حفضه وبعده ارسل الاسم {get_em('5807821534051438075')}", parse_mode='html')

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data: return
    mode = user_data[chat_id].get('mode')

    if event.photo and mode in ['thumb', 'both']:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        res = f"تم حفض الصورة بنجاح الآن ارسل الملف {get_em('5298893026444207528')}" if mode == 'thumb' else f"تم حفض الصورة ارسل اسم جديد للملف الآن {get_em('5069265018030130551')}"
        if mode == 'both': user_data[chat_id]['waiting_name'] = True
        await event.reply(res, parse_mode='html')
        return

    if event.text and not event.text.startswith('/'):
        if user_data[chat_id].get('waiting_name') or (mode == 'name' and 'file' in user_data[chat_id]):
            user_data[chat_id]['new_name'] = event.text
            user_data[chat_id]['waiting_name'] = False
            if 'file' in user_data[chat_id]: await process_file(event, chat_id)
            return

    if event.document:
        await bot_client.send_message(ADMIN_ID, f"📎 ملف من `{chat_id}`", file=event.document)
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        if mode == 'name':
            await event.reply(f"تم حفض الملف بنجاح الآن عليك إرسال اي اسم جديد للملف {get_em('5449816553727998023')}", parse_mode='html')
        elif (mode == 'thumb' and 'thumb' in user_data[chat_id]) or (mode == 'both' and 'thumb' in user_data[chat_id] and 'new_name' in user_data[chat_id]):
            await process_file(event, chat_id)

async def process_file(event, chat_id):
    data = user_data[chat_id]
    status_msg = await event.respond("📡 جاري البدء...")
    try:
        start_t = time.time()
        async def prog_cb(c, t, action, eid):
            if (time.time() - prog_cb.last) > 8:
                speed = c / (time.time() - prog_cb.start) if (time.time() - prog_cb.start) > 0 else 0
                perc = (c * 100 / t) if t > 0 else 0
                bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
                text = (f"{action} {get_em(eid)}\n【{bar}】 {round(perc, 2)}%\n"
                        f"{get_em('5105205613600704262')} {format_size(c)} / {format_size(t)}")
                try: await status_msg.edit(text, parse_mode='html')
                except: pass
                prog_cb.last = time.time()

        prog_cb.last = 0
        prog_cb.start = time.time()
        path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "جار تحميل ملفك", "5406745015365943482"))
        
        # تعديل الاسم لإضافة التوقيع الإجباري
        raw_name = data.get('new_name', data.get('file_name', "file"))
        base, ext = os.path.splitext(raw_name)
        final_name = f"{base}_By_Fileeeibot{ext}"

        async with user_client:
            prog_cb.start = time.time()
            # حل مشكلة الأحجام الكبيرة بإضافة force_document
            sent = await user_client.send_file(
                'me', path, thumb=data.get('thumb'),
                attributes=[DocumentAttributeFilename(final_name)],
                force_document=True,
                progress_callback=lambda c,t: prog_cb(c,t, "جار رفع في تلقرام", "5415655814079723871")
            )
            await bot_client.send_file(chat_id, sent, caption="✅ تم الإنجاز بنجاح!")
        
        await status_msg.delete()
        if os.path.exists(path): os.remove(path)
        
        # تفعيل الـ 5 دقائق انتظار
        last_use_time[chat_id] = time.time()
        asyncio.create_task(cooldown_timer(chat_id))

    except Exception as e: await event.respond(f"❌ خطأ: {e}")
    finally: user_data.pop(chat_id, None)

async def cooldown_timer(chat_id):
    await asyncio.sleep(300)
    await bot_client.send_message(chat_id, "✅ يمكنك الان عمل من الجديد اضغط /start")

print("البوت المجهول يعمل...")
bot_client.run_until_disconnected()
