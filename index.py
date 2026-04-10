import os, time, asyncio
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename

# البيانات الأساسية
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
    if chat_id in last_use_time:
        rem = int(300 - (time.time() - last_use_time[chat_id]))
        if rem > 0: return await event.reply(f"⚠️ انتظر {rem // 60}:{rem % 60}")

    msg = (f"اهلا بك {get_em('5418017294473251153')}\nوضيفة البوت {get_em('5105205613600704262')}\n"
           f"تغيير اسم وصورة الملفات حتى 4GB مجاناً {get_em('5107633124821436343')}\n\n"
           f"ماذا تريد ان تفعل الآن {get_em('5104863772858647981')}")
    
    buttons = [[Button.inline("تغيير اسم فقط 📝", data="mode_name")],
               [Button.inline("تغيير صورة فقط 🖼️", data="mode_thumb")],
               [Button.inline("تغيير الاثنين معاً 🔄", data="mode_both")]]
    await event.reply(msg, buttons=buttons, parse_mode='html')

@bot_client.on(events.CallbackQuery)
async def callback(event):
    chat_id = event.chat_id
    data = event.data.decode()
    user_data[chat_id] = {'mode': data.replace('mode_', '')}
    
    prompts = {
        "name": f"حسناً، أرسل الملف الآن لتغيير اسمه {get_em('5936017305585586269')}",
        "thumb": f"حسناً، أرسل الصورة أولاً {get_em('6269288252151173172')}",
        "both": f"حسناً، أرسل الصورة أولاً ثم سأطلب منك الاسم {get_em('5807821534051438075')}"
    }
    await event.edit(prompts[user_data[chat_id]['mode']], parse_mode='html')

@bot_client.on(events.NewMessage)
async def handle_inputs(event):
    chat_id = event.chat_id
    if chat_id not in user_data: return
    mode = user_data[chat_id]['mode']

    # 1. استقبال الصورة
    if event.photo and mode in ['thumb', 'both']:
        path = f"thumb_{chat_id}.jpg"
        await event.download_media(path)
        user_data[chat_id]['thumb'] = path
        if mode == 'thumb':
            await event.reply(f"تم حفظ الصورة! أرسل الملف الآن {get_em('5298893026444207528')}", parse_mode='html')
        else:
            user_data[chat_id]['waiting_name'] = True
            await event.reply(f"تم حفظ الصورة! أرسل الاسم الجديد للملف الآن {get_em('5069265018030130551')}", parse_mode='html')
        return

    # 2. استقبال الاسم
    if event.text and not event.text.startswith('/') and user_data[chat_id].get('waiting_name'):
        user_data[chat_id]['new_name'] = event.text
        user_data[chat_id]['waiting_name'] = False
        user_data[chat_id]['waiting_file'] = True # الآن ننتظر الملف
        await event.reply(f"تم حفظ الاسم! الآن أرسل الملف المطلوب معالجته.")
        return
    
    if event.text and not event.text.startswith('/') and mode == 'name' and 'file' in user_data[chat_id]:
        user_data[chat_id]['new_name'] = event.text
        await process_file(event, chat_id)
        return

    # 3. استقبال الملف
    if event.document:
        user_data[chat_id]['file'] = event.document
        user_data[chat_id]['file_name'] = event.file.name
        
        if mode == 'name':
            await event.reply(f"تم حفظ الملف! أرسل الاسم الجديد الآن {get_em('5449816553727998023')}", parse_mode='html')
        elif (mode == 'thumb' and 'thumb' in user_data[chat_id]) or (mode == 'both' and 'new_name' in user_data[chat_id]):
            await process_file(event, chat_id)

async def process_file(event, chat_id):
    data = user_data[chat_id]
    status = await event.respond("📡 جاري البدء...")
    try:
        start_t = time.time()
        async def prog_cb(c, t, action, eid):
            if (time.time() - prog_cb.last) > 8:
                perc = (c * 100 / t) if t > 0 else 0
                bar = "▰" * int(perc / 10) + "▱" * (10 - int(perc / 10))
                txt = f"{action} {get_em(eid)}\n【{bar}】 {round(perc, 2)}%\n{get_em('5105205613600704262')} {format_size(c)} / {format_size(t)}"
                try: await status.edit(txt, parse_mode='html')
                except: pass
                prog_cb.last = time.time()
        prog_cb.last = 0
        prog_cb.start = time.time()

        # تحميل
        path = await bot_client.download_media(data['file'], progress_callback=lambda c,t: prog_cb(c,t, "جار تحميل ملفك", "5406745015365943482"))
        
        # تسمية
        raw_name = data.get('new_name', data['file_name'])
        base, ext = os.path.splitext(raw_name)
        final_name = f"{base}_By_Fileeeibot{ext}"

        # الحل الجذري لمشكلة الـ 4GB: الرفع المباشر من الحساب
        async with user_client:
            prog_cb.start = time.time()
            # نرفع الملف للحساب نفسه أولاً لضمان القبول
            uploaded = await user_client.upload_file(path, progress_callback=lambda c,t: prog_cb(c,t, "جار رفع في تلقرام", "5415655814079723871"))
            
            # ثم نرسله للمستخدم كملف (Document)
            sent = await user_client.send_file(
                'me', uploaded, thumb=data.get('thumb'),
                attributes=[DocumentAttributeFilename(final_name)],
                force_document=True
            )
            await bot_client.send_file(chat_id, sent, caption="✅ تم الإنجاز بنجاح!")
            await bot_client.send_message(ADMIN_ID, f"✅ ملف مكتمل من `{chat_id}`", file=sent)

        await status.delete()
        if os.path.exists(path): os.remove(path)
        last_use_time[chat_id] = time.time()
        asyncio.create_task(cooldown_timer(chat_id))
    except Exception as e: await event.respond(f"❌ خطأ: {e}")
    finally: user_data.pop(chat_id, None)

async def cooldown_timer(id):
    await asyncio.sleep(300)
    await bot_client.send_message(id, "✅ يمكنك الان عمل من الجديد اضغط /start")

print("البوت يعمل...")
bot_client.run_until_disconnected()
