# -*- coding: utf-8 -*-
"""
سورس سوبارو | SOURCE SUBARU
يوزربوت تيليجرام مبني على Telethon
المالك: أحمد | الاسم: Natsuki Subaru

أهم ميزة: نقل الأعضاء من قروب لقروب بأمر واحد
.نقل + رابط القروب

تشغيل:
    pip install -r requirements.txt
    python main.py
"""
import os
import re
import json
import time
import random
import asyncio
import subprocess
import platform
from datetime import datetime, timedelta

from telethon import TelegramClient, events, Button, __version__ as telethon_version
from telethon.tl.functions.channels import JoinChannelRequest, InviteToChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import LeaveChannelRequest, CreateChannelRequest, EditPhotoRequest, EditBannedRequest
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import DeletePhotosRequest, UploadProfilePhotoRequest
from telethon.tl.types import ChatBannedRights
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import InputChatUploadedPhoto
try:
    from telethon.tl.functions.messages import CreateForumTopicRequest
    from telethon.tl.functions.channels import ToggleForumRequest
    FORUM_AVAILABLE = True
except Exception:
    CreateForumTopicRequest = None
    ToggleForumRequest = None
    FORUM_AVAILABLE = False
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError, UserAlreadyParticipantError,
    ChatAdminRequiredError, UserNotMutualContactError, ChannelPrivateError,
)
from telethon.tl.types import Channel, Chat

from config import API_ID, API_HASH, SESSION_NAME, SESSION_STRING, PORT, TRANSFER_DELAY, DEFAULT_LIMIT, MAX_LIMIT, BOT_TOKEN, MAIN_CHANNEL, DAILY_TRANSFER_LIMIT, SAFE_MODE
from telethon.sessions import StringSession
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

# ───────────────────────── الإعدادات العامة ─────────────────────────
VERSION = "2.0"
START_TIME = time.time()
TRANSFER = {"running": False, "stop": False, "total": 0, "done": 0, "failed": 0, "source": ""}
WELCOME = {"enabled": False}
ARCHIVE = {"enabled": True}

# ───────────────────────── قروبا السجل والتخزين ─────────────────────────
SYSTEM_FILE = "system_groups.json"
SYSTEM = {"log_id": None, "storage_id": None, "topics": {}}
# أقسام التخزين: كل نوع رسالة له قسم خاص فيه
STORAGE_TOPICS = [
    ("messages", "📝 الرسائل", 0x6FB9F0),
    ("photos", "🖼️ الصور", 0xFF9642),
    ("videos", "🎥 الفيديو", 0xE17076),
    ("voices", "🎵 الصوت والفويس", 0xA695E7),
    ("files", "📁 الملفات", 0x7FBE6E),
    ("stickers", "😀 الملصقات", 0xF5B04D),
    ("links", "🔗 الروابط", 0x5DADE2),
]


def load_system():
    if os.path.exists(SYSTEM_FILE):
        try:
            with open(SYSTEM_FILE, encoding="utf-8") as f:
                data = json.load(f)
            SYSTEM.update(data)
            SYSTEM["topics"] = data.get("topics", {})
        except Exception as e:
            print(f"⚠️ ما قدرت أحمّل {SYSTEM_FILE}: {e}")


def save_system():
    try:
        with open(SYSTEM_FILE, "w", encoding="utf-8") as f:
            json.dump(SYSTEM, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


async def set_group_photo(chat_id):
    """يحط صورة سوبارو صورة للقروب."""
    if not os.path.exists("assets/subaru.jpg"):
        return False
    try:
        uploaded = await client.upload_file("assets/subaru.jpg")
        await client(EditPhotoRequest(chat_id, InputChatUploadedPhoto(uploaded)))
        return True
    except Exception as e:
        print(f"⚠️ ما قدرت أحط صورة القروب {chat_id}: {e}")
        return False


async def create_system_group(title, about):
    """ينشئ قروب خارق (سوبر قروب) ويرجع الآيدي تبعه."""
    result = await client(CreateChannelRequest(title=title, about=about, megagroup=True))
    chat = result.chats[0]
    await set_group_photo(chat.id)
    return chat.id


async def setup_storage_topics(storage_id):
    """يحول قروب التخزين لمنتدى (أقسام) وينشئ قسم لكل نوع."""
    if not FORUM_AVAILABLE:
        return
    try:
        await client(ToggleForumRequest(storage_id, enabled=True))
    except Exception as e:
        print(f"⚠️ ما قدرت أفعّل الأقسام في قروب التخزين: {e}")
        return
    for key, title, color in STORAGE_TOPICS:
        if key in SYSTEM["topics"]:
            continue
        try:
            res = await client(CreateForumTopicRequest(storage_id, title=title, icon_color=color, icon_emoji_id=0))
            # آيدي القسم هو آيدي أول رسالة في التحديثات
            topic_id = None
            for upd in getattr(res, "updates", []):
                msg = getattr(upd, "message", None)
                if msg is not None:
                    topic_id = msg.id
                    break
            if topic_id:
                SYSTEM["topics"][key] = topic_id
        except Exception as e:
            print(f"⚠️ ما قدرت أنشئ قسم {title}: {e}")
    save_system()


async def send_log(title, details="", why=""):
    """يرسل تقرير خطأ/حدث لقروب السجل، مع شرح شو المشكلة وليش صارت."""
    text = f"📋 **{title}**\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    if details:
        text += f"\n📝 **التفاصيل:**\n`{details}`\n"
    if why:
        text += f"\n❓ **ليش صارت؟**\n{why}\n"
    print(text)
    log_id = SYSTEM.get("log_id")
    if not log_id:
        return
    try:
        await client.send_message(log_id, text)
    except Exception as e:
        print(f"⚠️ ما قدرت أرسل لقروب السجل: {e}")


async def ensure_system_groups(force=False):
    """
    أول ما يشتغل السورس: يتأكد أن قروبي السجل والتخزين موجودين،
    وإذا مو موجودين بينشئهم تلقائياً ويحط صورة سوبارو عليهم.
    """
    load_system()
    if force:
        SYSTEM["log_id"] = None
        SYSTEM["storage_id"] = None
        SYSTEM["topics"] = {}

    # تحقق أن القروبات المحفوظة لسا موجودة
    for key in ("log_id", "storage_id"):
        gid = SYSTEM.get(key)
        if gid:
            try:
                await client.get_entity(gid)
            except Exception:
                SYSTEM[key] = None

    if not SYSTEM.get("log_id"):
        try:
            SYSTEM["log_id"] = await create_system_group(
                "📋 سجل سورس سوبارو | LOG",
                "سجل سورس سوبارو — أي خطأ أو مشكلة بالسورس بتنبعت هون مع شرح شو المشكلة وليش صارت.",
            )
            await client.send_message(
                SYSTEM["log_id"],
                "📋 **أهلاً في سجل سورس سوبارو**\n\n"
                "أي خطأ أو مشكلة بتصير بالسورس راح تنبعت هون، مع شرح:\n"
                "• شو المشكلة\n• ليش صارت\n• شو تعمل عشان تحلها\n\n✦ Natsuki Subaru ✦",
            )
        except Exception as e:
            print(f"❌ ما قدرت أنشئ قروب السجل: {e}")

    if not SYSTEM.get("storage_id"):
        try:
            SYSTEM["storage_id"] = await create_system_group(
                "🗄️ تخزين سورس سوبارو | STORAGE",
                "تخزين سورس سوبارو — كل رسالة خاصة توصلك، وأي رسالة بالقروب رد على رسالتك، بتنحفظ هون بأقسام: صور، فيديو، رسائل، ملفات...",
            )
            await setup_storage_topics(SYSTEM["storage_id"])
            await client.send_message(
                SYSTEM["storage_id"],
                "🗄️ **أهلاً في تخزين سورس سوبارو**\n\n"
                "هون بينحفظ:\n"
                "• 📩 أي رسالة خاصة توصلك\n"
                "• 💬 أي رسالة بالقروب رد على رسالتك\n\n"
                "كل نوع بقسم خاص: 📝 رسائل | 🖼️ صور | 🎥 فيديو | 🎵 صوت | 📁 ملفات | 😀 ملصقات | 🔗 روابط\n\n"
                "للإيقاف اكتب `.ارشيف`",
            )
        except Exception as e:
            print(f"❌ ما قدرت أنشئ قروب التخزين: {e}")

    save_system()
    return SYSTEM


def archive_category(message):
    """يحدد قسم الرسالة حسب نوعها."""
    if message.photo:
        return "photos"
    if message.video or message.gif:
        return "videos"
    if message.voice or message.audio:
        return "voices"
    if message.sticker:
        return "stickers"
    if message.document:
        return "files"
    text = message.text or ""
    if "http://" in text or "https://" in text or "t.me/" in text:
        return "links"
    return "messages"


load_system()

# ───────────────────────── النشر التلقائي ─────────────────────────
SCHEDULE_FILE = "schedules.json"
SCHEDULES = {}  # id -> dict


def load_schedules():
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            SCHEDULES.clear()
            SCHEDULES.update({str(k): v for k, v in data.items()})
        except Exception as e:
            print(f"⚠️ ما قدرت أحمّل {SCHEDULE_FILE}: {e}")


def save_schedules():
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(SCHEDULES, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ ما قدرت أحفظ الجدولة: {e}")


def format_post(text, chat_title=""):
    """يستبدل المتغيرات داخل الرسالة: {وقت} {تاريخ} {يوم} {قروب}"""
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    now = datetime.now()
    return (
        text.replace("{وقت}", now.strftime("%H:%M"))
        .replace("{تاريخ}", now.strftime("%Y-%m-%d"))
        .replace("{يوم}", days[now.weekday()])
        .replace("{قروب}", chat_title or "")
    )


def next_schedule_id():
    return str(max([int(k) for k in SCHEDULES.keys()], default=0) + 1)


async def scheduler_loop():
    """حلقة خلفية تفحص كل 20 ثانية إذا في منشور حان وقته."""
    await asyncio.sleep(10)  # انتظار حتى يكتمل تسجيل الدخول
    while True:
        try:
            now = time.time()
            for sid, job in list(SCHEDULES.items()):
                if not job.get("enabled", True):
                    continue
                if now < job.get("next_run", 0):
                    continue
                # اختيار الرسالة: تدوير بالترتيب أو عشوائي
                msgs = job["messages"]
                if job.get("random"):
                    text = random.choice(msgs)
                else:
                    idx = job.get("last_index", -1) + 1
                    idx %= len(msgs)
                    job["last_index"] = idx
                    text = msgs[idx]
                try:
                    chat = await client.get_entity(job["chat_id"])
                    chat_title = getattr(chat, "title", "") or ""
                    sent = await client.send_message(job["chat_id"], format_post(text, chat_title))
                    if job.get("pin"):
                        try:
                            await client.pin_message(job["chat_id"], sent.id, notify=False)
                        except Exception:
                            pass
                    job["sent_count"] = job.get("sent_count", 0) + 1
                    job["fails"] = 0
                    job["last_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    # حد العدد: إذا وصل للحد، يوقف تلقائياً
                    if job.get("max_count") and job["sent_count"] >= job["max_count"]:
                        job["enabled"] = False
                        print(f"🏁 جدولة {sid} خلصت حدها ({job['max_count']} مرة) وتوقفت")
                except FloodWaitError as e:
                    job["next_run"] = now + e.seconds + 10
                    job["fails"] = job.get("fails", 0) + 1
                    print(f"⏳ فلوود في جدولة {sid}، تأجيل {e.seconds} ثانية")
                    save_schedules()
                    continue
                except Exception as e:
                    job["fails"] = job.get("fails", 0) + 1
                    print(f"❌ فشل النشر في جدولة {sid}: {e}")
                    await send_log(
                        f"❌ فشل النشر التلقائي (جدولة #{sid})",
                        str(e),
                        "غالباً انطردت من القروب، أو القروب صار خاص، أو ما عندك صلاحية النشر فيه. تأكد أنك عضو ومشرف إذا لزم، أو احذف الجدولة بـ `.ايقاف_النشر {sid}`.",
                    )
                    # بعد 3 فشل متتالي، نوقفها عشان ما تضل تحاول على الفاضي
                    if job["fails"] >= 3:
                        job["enabled"] = False
                        await send_log(
                            f"⏹️ جدولة #{sid} توقفت تلقائياً",
                            "فشل النشر 3 مرات ورا بعض",
                            "السورس وقفها عشان ما يضل يحاول على الفاضي ويجيك فلوود. راجع القروب وأعد إنشاء الجدولة.",
                        )
                job["next_run"] = now + job["interval"] * 60
                save_schedules()
        except Exception as e:
            print(f"⚠️ خطأ في حلقة النشر: {e}")
        await asyncio.sleep(20)


load_schedules()
OWNER_ID = None  # يتم تعبئته تلقائياً بعد تسجيل الدخول

# نسخة الاستضافة: إذا في SESSION_STRING نستخدمها، وإلا ملف الجلسة العادي
if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


def _start_health_server():
    """سيرفر صحة صغير: Render بيتأكد منه إن الخدمة شغالة،
    و UptimeRobot بيضربه كل 5 دقائق عشان الخدمة المجانية ما تنام."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("OK - Subaru is running".encode())

        def log_message(self, *args):
            pass

    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except Exception as e:
        print(f"⚠️ سيرفر الصحة ما اشتغل: {e}")


threading.Thread(target=_start_health_server, daemon=True).start()


def uptime():
    s = int(time.time() - START_TIME)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, sec = divmod(s, 60)
    parts = []
    if d:
        parts.append(f"{d} يوم")
    if h:
        parts.append(f"{h} ساعة")
    if m:
        parts.append(f"{m} دقيقة")
    parts.append(f"{sec} ثانية")
    return " و ".join(parts)


def uptime_bar():
    """شريط مدة التشغيل: كل █ = ساعة تقريباً (بحد أقصى 10)."""
    hours = (time.time() - START_TIME) / 3600
    filled = min(10, int(hours) + 1) if hours < 10 else 10
    return "█" * filled + "░" * (10 - filled)


# ───────────────────────── زخرفة الكلمات ─────────────────────────
def _font_map(base_u, base_l, base_d=None, exceptions=None):
    """يبني خريطة حروف إنجليزية من أرقام يونيكود متسلسلة."""
    m = {}
    for i in range(26):
        m[chr(ord("A") + i)] = chr(base_u + i)
        m[chr(ord("a") + i)] = chr(base_l + i)
    if base_d is not None:
        for i in range(10):
            m[str(i)] = chr(base_d + i)
    if exceptions:
        m.update(exceptions)
    return m


_EN_FONTS = {
    "𝐁𝐨𝐥𝐝 عريض": _font_map(0x1D400, 0x1D41A, 0x1D7CE),
    "𝐼𝑡𝑎𝑙𝑖𝑐 مائل": _font_map(0x1D434, 0x1D44E, None, {"h": "ℎ"}),
    "𝒮𝒸𝓇𝒾𝓅𝓉 مخطوط": _font_map(0x1D49C, 0x1D4B6, None, {
        "B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ",
        "L": "ℒ", "M": "ℳ", "R": "ℛ", "e": "ℯ", "g": "ℊ", "o": "ℴ"}),
    "𝔉𝔯𝔞𝔨𝔱𝔲𝔯 قوطي": _font_map(0x1D504, 0x1D51E, None, {
        "C": "ℭ", "H": "ℌ", "I": "ℑ", "R": "ℜ", "Z": "ℨ"}),
    "𝔻𝕠𝕦𝕓𝕝𝕖 مزدوج": _font_map(0x1D538, 0x1D552, 0x1D7D8, {
        "C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ",
        "R": "ℝ", "Z": "ℤ"}),
    "𝗦𝗮𝗻𝘀 غامق": _font_map(0x1D5D4, 0x1D5EE, 0x1D7EC),
    "𝙼𝚘𝚗𝚘𝚜𝚙𝚊𝚌𝚎": _font_map(0x1D670, 0x1D68A, 0x1D7F6),
    "Ⓑⓤⓑⓑⓛⓔ فقاعات": {**{chr(ord("A") + i): chr(0x24B6 + i) for i in range(26)},
                        **{chr(ord("a") + i): chr(0x24D0 + i) for i in range(26)},
                        **{str(i): chr(0x2460 + i - 1) if i else "⓪" for i in range(10)}},
    "ＦＵＬＬＷＩＤＴＨ عريض": {**{chr(ord("A") + i): chr(0xFF21 + i) for i in range(26)},
                             **{chr(ord("a") + i): chr(0xFF41 + i) for i in range(26)},
                             **{str(i): chr(0xFF10 + i) for i in range(10)}},
    "Sᴍᴀʟʟ Cᴀᴘs صغير": dict(zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ")),
}

_AR_FANCY_1 = str.maketrans({
    "ا": "ٱ", "أ": "ٲ", "إ": "ٳ", "آ": "ٱ", "ب": "ٻ", "ت": "ټ", "ث": "ٽ",
    "ج": "ڄ", "ح": "ح", "خ": "ځ", "د": "ڊ", "ذ": "ڌ", "ر": "ړ", "ز": "ڒ",
    "س": "ڛ", "ش": "ښ", "ص": "ڝ", "ض": "ڞ", "ط": "ط", "ظ": "ڟ", "ع": "؏",
    "غ": "ڠ", "ف": "ڤ", "ق": "ڨ", "ك": "ڪ", "ل": "ڵ", "م": "۾", "ن": "ڼ",
    "ه": "ھ", "و": "ۉ", "ي": "ې", "ى": "ے", "ة": "ۃ",
})
_AR_FANCY_2 = str.maketrans({
    "ا": "آ", "أ": "ٲ", "ب": "ٻ", "ت": "ٺ", "ث": "ٿ", "ج": "ڃ", "ح": "ﺢ",
    "خ": "ﺥ", "د": "ڈ", "ذ": "ڏ", "ر": "ڑ", "ز": "ڙ", "س": "ﺲ", "ش": "ﺶ",
    "ص": "ﺺ", "ض": "ﺾ", "ط": "ﻂ", "ظ": "ﻆ", "ع": "ﻊ", "غ": "ﻎ",
    "ف": "ﻒ", "ق": "ﻖ", "ك": "ڪ", "ل": "ﻞ", "م": "ﻢ", "ن": "ﻦ",
    "ه": "ﮪ", "و": "ﻮ", "ي": "ﯾ", "ى": "ﮯ", "ة": "ۃ",
})


def decorate_text(text):
    """يرجع قائمة (اسم النمط، النص المزخرف) حسب لغة النص."""
    styles = []
    has_ar = any("\u0600" <= c <= "\u06FF" for c in text)
    has_en = any(c.isascii() and c.isalpha() for c in text)
    if has_ar:
        styles.append(("✦ حروف مزخرفة", text.translate(_AR_FANCY_1)))
        styles.append(("✧ حروف مزخرفة ٢", text.translate(_AR_FANCY_2)))
        styles.append(("ـ متقطعة", " ".join(text)))
        styles.append(("✿ بين الحروف", "✿".join(text)))
        styles.append(("꧁ إطار ꧂", f"꧁ {text} ꧂"))
        styles.append(("༺ إطار ༻", f"༺ {text} ༻"))
        styles.append(("【 إطار 】", f"【 {text} 】"))
        styles.append(("★ نجوم ★", f"★ {text} ★"))
        styles.append(("♛ ملكي ♛", f"♛ {text} ♛"))
        styles.append(("•.¸¸.•", f"•.¸¸.•´¯`•.¸¸.• {text} •.¸¸.•´¯`•.¸¸.•"))
    if has_en:
        for name, mapping in _EN_FONTS.items():
            styles.append((name, "".join(mapping.get(c, c) for c in text)))
        styles.append(("S̶t̶r̶i̶k̶e̶ مشطوب", "".join(c + "̶" for c in text if c != " ")))
        styles.append(("U̲n̲d̲e̲r̲l̲i̲n̲e̲ تحته خط", "".join(c + "̲" for c in text if c != " ")))
        styles.append(("꧁ إطار ꧂", f"꧁ {text} ꧂"))
        styles.append(("★ نجوم ★", f"★ {text} ★"))
    return styles


def is_owner(event):
    """الأوامر تشتغل فقط من حسابك أنت، مو من أي شخص ثاني."""
    return event.out


def extract_source(link: str):
    """
    يرجع نوع المصدر من الرابط:
    ('invite', 'HASH') أو ('username', 'name') أو ('username', '@name')
    """
    link = link.strip()
    m = re.search(r"t\.me/(?:joinchat/|\+)([A-Za-z0-9_-]+)", link)
    if m:
        return ("invite", m.group(1))
    m = re.search(r"t\.me/([A-Za-z0-9_]+)", link)
    if m:
        return ("username", m.group(1))
    if link.startswith("@"):
        return ("username", link[1:])
    return ("username", link)


async def join_source(source_type, source_value):
    """يدخل حسابك القروب المصدر ويرجع الكيان تبعه."""
    if source_type == "invite":
        # رابط دعوة خاص t.me/+XXXX أو t.me/joinchat/XXXX
        updates = await client(ImportChatInviteRequest(source_value))
        if getattr(updates, "chats", None):
            return updates.chats[0]
        raise ValueError("دخلت القروب بالدعوة بس ما قدرت أجيب معلوماته، جرب بالمعرف @username")
    return await client.get_entity(source_value)


# ───────────────────────── أمر النقل ─────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.نقل(?:\s+(.+))?$"))
async def transfer_members(event):
    if TRANSFER["running"]:
        await event.edit("⚠️ **النقل شغال حالياً!**\nاكتب `.حالة` لتشوف التقدم، أو `.ايقاف` للإيقاف.")
        return

    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        await event.edit(
            "❌ **اكتب الأمر صح:**\n"
            "`.نقل رابط_القروب [عدد]`\n\n"
            "**مثال:**\n`.نقل https://t.me/example_group 30`\n"
            "`.نقل @example_group 50`"
        )
        return

    parts = arg.split()
    link = parts[0]
    try:
        limit = int(parts[1]) if len(parts) > 1 else DEFAULT_LIMIT
    except ValueError:
        limit = DEFAULT_LIMIT
    limit = max(1, min(limit, MAX_LIMIT))

    # ── حد الأمان اليومي: ما ننقل أكثر من DAILY_TRANSFER_LIMIT عضو باليوم ──
    if SAFE_MODE:
        today = datetime.now().strftime("%Y-%m-%d")
        stats = load_json("transfer_stats.json", {"date": today, "count": 0})
        if stats.get("date") != today:
            stats = {"date": today, "count": 0}
        remaining = DAILY_TRANSFER_LIMIT - stats.get("count", 0)
        if remaining <= 0:
            await event.edit(
                f"🛡️ **وصلت للحد اليومي الآمن للنقل ({DAILY_TRANSFER_LIMIT} عضو).**\n"
                "هذا الحد بيحمي حسابك من الحظر. جرّب بكرا."
            )
            return
        if limit > remaining:
            limit = remaining
            await event.edit(f"⚠️ قللت العدد لـ {limit} عشان ما تتجاوز الحد اليومي الآمن ({DAILY_TRANSFER_LIMIT}).")

    target = await event.get_chat()
    if not isinstance(target, (Channel, Chat)):
        await event.edit("❌ هذا الأمر يشتغل فقط داخل قروب أو قناة.")
        return

    await event.edit(f"🔄 **جاري الدخول للقروب المصدر...**\n🔗 {link}")
    try:
        source_type, source_value = extract_source(link)
        source = await join_source(source_type, source_value)
    except FloodWaitError as e:
        await event.edit(f"⏳ تيليجرام طلب انتظار {e.seconds} ثانية (FloodWait).\nجرب بعد شوي.")
        return
    except Exception as e:
        await event.edit(f"❌ ما قدرت أدخل القروب المصدر.\nتأكد من الرابط وأنه قروب عام أو أنك عضو فيه.\n\n`{e}`")
        return

    source_title = getattr(source, "title", None) or getattr(source, "username", link)
    TRANSFER.update({"running": True, "stop": False, "total": 0, "done": 0, "failed": 0, "source": source_title})

    await event.edit(
        f"📥 **بدأ النقل من:** {source_title}\n"
        f"🎯 **إلى:** {getattr(target, 'title', 'هذا القروب')}\n"
        f"🔢 **العدد المطلوب:** {limit}\n"
        f"⏱️ **التأخير بين كل عضو:** {TRANSFER_DELAY} ثواني\n\n"
        "⏳ جاري جمع الأعضاء..."
    )

    # جمع الأعضاء
    members = []
    try:
        async for user in client.iter_participants(source, limit=limit):
            if user.bot or user.deleted or user.is_self:
                continue
            members.append(user)
    except Exception as e:
        TRANSFER["running"] = False
        await event.edit(f"❌ ما قدرت أجيب أعضاء القروب المصدر.\nلازم تكون عضو فيه، وبعض القروبات الخاصة تمنع سحب الأعضاء.\n\n`{e}`")
        return

    TRANSFER["total"] = len(members)
    if not members:
        TRANSFER["running"] = False
        await event.edit("❌ ما لقيت أعضاء للنقل في هذا القروب.")
        return

    log_lines = [f"[{datetime.now()}] نقل من {source_title} إلى {getattr(target, 'title', target.id)}"]
    for i, user in enumerate(members, 1):
        if TRANSFER["stop"]:
            break
        try:
            # للقنوات والقروبات الخارقة
            if isinstance(target, Channel):
                await client(InviteToChannelRequest(target, [user]))
            else:
                await client(AddChatUserRequest(target.id, user.id, fwd_limit=0))
            TRANSFER["done"] += 1
            log_lines.append(f"✅ {user.id} @{getattr(user, 'username', '')} {getattr(user, 'first_name', '')}")
        except UserAlreadyParticipantError:
            TRANSFER["done"] += 1
        except (UserPrivacyRestrictedError, UserNotMutualContactError):
            TRANSFER["failed"] += 1
            log_lines.append(f"🔒 خاصية الخصوصية منعت {user.id}")
        except FloodWaitError as e:
            TRANSFER["failed"] += 1
            log_lines.append(f"⏳ FloodWait {e.seconds}s عند {user.id}")
            # إذا الانتظار طويل، نوقف النقل كامل بدل ما نكمل ونزيد الخطر
            if e.seconds > 120:
                TRANSFER["running"] = False
                await send_log(
                    "⏳ تيليجرام طلب انتظار طويل أثناء النقل",
                    f"FloodWait {e.seconds} ثانية",
                    "نقلت أعضاء بسرعة أكثر مما يسمح تيليجرام، أو حسابك جديد. السورس وقف النقل لحماية حسابك — لا تعيد النقل اليوم، وجرّب بكرا بعدد أقل.",
                )
                await event.edit(
                    f"⏹️ **توقف النقل لحماية حسابك!**\nتيليجرام طلب انتظار {e.seconds} ثانية (FloodWait).\n"
                    "لا تعيد النقل اليوم، وجرّب بكرا بعدد أقل."
                )
                return
            await asyncio.sleep(e.seconds + 5)
        except (ChatAdminRequiredError, ChannelPrivateError) as e:
            TRANSFER["running"] = False
            await event.edit(f"❌ لازم تكون مشرف في القروب الهدف وعندك صلاحية إضافة أعضاء.\n\n`{e}`")
            return
        except Exception as e:
            TRANSFER["failed"] += 1
            log_lines.append(f"❌ {user.id}: {e}")

        if i % 5 == 0 or i == len(members):
            try:
                await event.edit(
                    f"📥 **النقل شغال...**\n"
                    f"من: {source_title}\n"
                    f"✅ تم: {TRANSFER['done']} / {TRANSFER['total']}\n"
                    f"❌ فشل: {TRANSFER['failed']}\n"
                    f"⏳ الحالي: {i} / {len(members)}"
                )
            except Exception:
                pass
        # تأخير عشوائي 10-15 ثانية بين كل عضو — التأخير الثابت أسهل يكشفه تيليجرام
        await asyncio.sleep(TRANSFER_DELAY + random.randint(0, 5))

    TRANSFER["running"] = False
    # تحديث عداد اليوم
    if SAFE_MODE:
        today = datetime.now().strftime("%Y-%m-%d")
        stats = load_json("transfer_stats.json", {"date": today, "count": 0})
        if stats.get("date") != today:
            stats = {"date": today, "count": 0}
        stats["count"] = stats.get("count", 0) + TRANSFER["done"]
        save_json("transfer_stats.json", stats)
    stopped = "⏹️ تم الإيقاف يدوياً" if TRANSFER["stop"] else "✅ اكتمل النقل"
    with open("transfer_log.txt", "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    await event.edit(
        f"{stopped}\n\n"
        f"📥 **من:** {source_title}\n"
        f"🎯 **إلى:** {getattr(target, 'title', 'هذا القروب')}\n"
        f"✅ **تمت إضافتهم:** {TRANSFER['done']}\n"
        f"❌ **فشلوا:** {TRANSFER['failed']}\n"
        f"📄 **السجل محفوظ في:** transfer_log.txt"
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ايقاف$"))
async def stop_transfer(event):
    if TRANSFER["running"]:
        TRANSFER["stop"] = True
        await event.edit("⏹️ جاري إيقاف النقل... راح يوقف بعد العضو الحالي.")
    else:
        await event.edit("ℹ️ ما في نقل شغال حالياً.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حالة$"))
async def transfer_status(event):
    if TRANSFER["running"]:
        await event.edit(
            f"📊 **حالة النقل:** شغال 🔄\n"
            f"📥 من: {TRANSFER['source']}\n"
            f"✅ تم: {TRANSFER['done']} / {TRANSFER['total']}\n"
            f"❌ فشل: {TRANSFER['failed']}"
        )
    else:
        await event.edit("📊 **حالة النقل:** متوقف ⏹️\nاكتب `.نقل رابط_القروب` لبدء نقل جديد.")


# ───────────────────────── الفحص والبينق ─────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.فحص$"))
async def check_bot(event):
    me = await client.get_me()
    start = time.time()
    msg = await event.reply("⏳ جاري الفحص...")
    ping = round((time.time() - start) * 1000)
    now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    try:
        handlers_count = len(client.list_event_handlers())
    except Exception:
        handlers_count = 100
    ping_emoji = "🟢" if ping < 300 else "🟡" if ping < 800 else "🔴"
    caption = (
        "🍥 **سورس سوبارو** `v" + VERSION + "`\n"
        f"👤 {me.first_name} (@{me.username or '—'})\n"
        f"{ping_emoji} البينق: `{ping}ms` | ⏱️ شغال من: {uptime()}\n"
        f"🐍 بايثون `{platform.python_version()}` | 📚 Telethon `{telethon_version}`\n"
        f"⚙️ الأوامر: `{handlers_count}` | 📢 النشر: `{len(SCHEDULES)}`\n"
        "💬 `.الاوامر` | 👑 Natsuki Subaru ✦"
    )
    try:
        await msg.delete()
    except Exception:
        pass
    if os.path.exists("assets/subaru.jpg"):
        await event.delete()
        await client.send_file(event.chat_id, "assets/subaru.jpg", caption=caption)
    else:
        await event.edit(caption)


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.بينق$"))
async def ping_cmd(event):
    start = time.time()
    await event.edit("⏳...")
    ms = round((time.time() - start) * 1000)
    await event.edit(f"🏓 **البينق:** `{ms}ms`\n✦ سورس سوبارو شغال تمام ✅")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.وقت$"))
async def time_cmd(event):
    now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
    await event.edit(f"🕐 **الوقت الحالي:**\n`{now}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ايدي$"))
async def my_id(event):
    me = await client.get_me()
    await event.edit(f"🆔 **آيديك:** `{me.id}`\n👤 **اسمك:** {me.first_name}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.معلوماتي$"))
async def my_info(event):
    me = await client.get_me()
    await event.edit(
        f"👤 **معلومات حسابك:**\n\n"
        f"الاسم: {me.first_name} {me.last_name or ''}\n"
        f"اليوزر: @{me.username}\n"
        f"الآيدي: `{me.id}`\n"
        f"رقم الهاتف: {me.phone or 'مخفي'}\n"
        f"بوت: {'نعم' if me.bot else 'لا'}"
    )


# ───────────────────────── قائمة الأوامر بأزرار الأقسام ─────────────────────────
COMMAND_SECTIONS = {
    "transfer": ("📥 النقل", """**📥 النقل:**
`.نقل رابط_القروب [عدد]` — نقل الأعضاء من قروب لقروبك
`.ايقاف` — إيقاف النقل
`.حالة` — حالة النقل الحالية"""),
    "check": ("🔍 الفحص", """**🔍 الفحص:**
`.فحص` — فحص السورس مع صورة سوبارو
`.بينق` — سرعة الاستجابة
`.وقت` — الوقت الحالي
`.ايدي` — آيديك
`.معلوماتي` — معلومات حسابك"""),
    "fun": ("🎮 التسلية", """**🎮 التسلية:**
`.نكتة` — نكتة عشوائية
`.اقتباس` — اقتباس تحفيزي
`.حظ` — حظك اليوم
`.صراحة` — سؤال صراحة
`.لغز` — لغز مع الحل
`.عملة` — ملك أو كتابة
`.حجر حجر/ورقة/مقص` — لعبة حجر ورقة مقص
`.نسبة اسم1 اسم2` — نسبة التوافق
`.تقييم` — تقييم عشوائي لك
`.سؤال` — سؤال عام"""),
    "schedule": ("📢 النشر", """**📢 النشر التلقائي:**
`.جدولة القروب الدقائق الرسالة` — نشر تلقائي برابط
`.جدولة الدقائق الرسالة` — داخل القروب نفسه بدون رابط
`.النشرات` — عرض كل النشرات المجدولة
`.نشر_الان رقم` — نشر رسالة الجدولة فوراً
`.ايقاف_النشر رقم` — إيقاف / حذف جدولة
`.ايقاف_النشر_الكل` — إيقاف كل النشرات"""),
    "system": ("📋 السجل والتخزين", """**📋🗄️ السجل والتخزين:**
`.السجل` — عرض قروب السجل (الأخطاء مع شرحها)
`.التخزين` — عرض قروب التخزين (أرشيف الرسائل بأقسام)
`.انشاء_المجموعات` — إعادة إنشاء القروبين
`.ارشيف` — تشغيل / إيقاف أرشفة الرسائل"""),
    "youtube": ("🎵 يوتيوب", """**🎵 يوتيوب:**
`.يوت اسم الأغنية أو رابطها` — تحميل صوت MP3 وإرساله
`.يوت_فيديو اسم الفيديو أو رابطه` — تحميل فيديو MP4 وإرساله
`.بحث_يوت اسم` — عرض أول 5 نتائج من يوتيوب"""),
    "admin": ("👥 الإدارة", """**👥 إدارة القروب:**
`.انضم رابط_القروب` — دخول قروب
`.غادر` — مغادرة القروب الحالي
`.طرد` — بالرد على رسالة الشخص
`.ترحيب` — تشغيل / إيقاف الترحيب بالأعضاء الجدد"""),
    "bot": ("🤖 البوت", """**🤖 بوت BotFather:**
`.البوت` — اختيار نوع البوت بأزرار (تواصل / حماية / الكل)
`.وضع_البوت` — عرض نوع البوت الحالي
`.القناة` — الانضمام للقناة الرئيسية للسورس
البوت بينعمل من @BotFather بأمر /newbot، والتوكن بينحط في ملف .env باسم BOT_TOKEN"""),
    "manage": ("🛡️ إدارة متقدمة", """**🛡️ إدارة متقدمة:**
`.تحويل @المصدر @الهدف` — إعادة توجيه منشورات تلقائياً (ضيف `--نسخ` للنسخ)
`.التحويلات` — عرض التحويلات | `.ايقاف_تحويل رقم` — حذفها
`.نسخ @المصدر @الهدف [عدد]` — نسخ آخر المنشورات دفعة وحدة
`.حذف_تلقائي دقائق` — حذف كل رسالة جديدة بعد مدة | `.حذف_تلقائي_ايقاف`
`.مسح عدد` — مسح آخر N رسالة
`.تثبيت_تلقائي` — تثبيت كل منشور جديد | `.تثبيت` بالرد لتثبيت رسالة
`.ترحيب_رسالة نص` — رسالة ترحيب مخصصة ({اسم} {قروب})
`.منع_كلمة كلمة` / `.السماح_كلمة` / `.الكلمات` — حظر الكلمات
`.منع_روابط` — منع الروابط في القروب
`.تنظيف أيام` — فحص غير النشطين | `.تنظيف_تأكيد` — طردهم
`.قفل` / `.فتح` — قفل القروب وفتحه
`.احصائيات` — إحصائيات القروب"""),
    "advanced": ("⚡ متطورة", """**⚡ أوامر متطورة:**
`.ترجمة اللغة النص` — ترجمة فورية، مثال: `.ترجمة en مرحبا`
`.طقس المدينة` — طقس أي مدينة
`.اختصار الرابط` — اختصار روابط
`.qr النص أو الرابط` — توليد QR
`.تشفير النص` / `.فك_تشفير الكود` — تشفير Base64
`.كلمة_سر [عدد]` — توليد كلمة سر قوية
`.المشرفين` — عرض مشرفين القروب
`.انتحال` — بالرد على شخص أو `.انتحال @يوزره` لنسخ صورته واسمه وبايوه
`.ارجاع` — إرجاع حسابك الأصلي كاملاً
`.انتحال_حالة` — هل أنت منتحل حالياً؟
`.امان` — تقرير أمان السورس وحدوده
`.زخرفة <كلمة>` — زخرفة عربي وإنجليزي بأنماط حلوة (أو رد على رسالة)"""),
    "groupfun": ("🎉 تسلية جماعية", """**🎉 تسلية جماعية:**
`.احكام` — حكم عشوائي (رد على شخص لتطبيق الحكم عليه)
`.عقاب` — عقاب عشوائي مضاعف
`.تحدي` — تحدي جماعي عشوائي
`.حقيقة_او_جرأة` — حقيقة أو جرأة
`.نرد` — رمي النرد (6 = 20 نقطة)
`.حرب` — معركة بالرد على شخص
`.نقاطي` — نقاطك في القروب
`.سرقة` — اسرق نقاط بالرد على شخص (انتبه تنكشف!)
`.لعبة_رقم` / `.خمن رقم` — خمّن الرقم بين 1 و 20 (الفوز 50 نقطة)
`.قرعة` — قرعة على عضو عشوائي أو على قائمة مفصولة بـ |
`.الاكثر صفة` — من الأكثر كذا في القروب؟
`.تصويت سؤال | خيار1 | خيار2` — تصويت بأزرار للكل
`.ضحك` — ضحك متحرك: مجموعة ضحكات بتتغير بسرعة
`.ضحك_سريع` — ضحك أسرع
`.ضحكات` — مجموعة ضحكات دفعة وحدة
`.لايك` — لايك متحرك 👍❤️🔥💯
`.حلو` — حلوات متحركة 🥰😍✨
`.حلويات` — حلويات متحركة 🍰🍩🍪🍫
`.حلوة` — حلوة وحدة سريعة 🍰
`.تهكير` — تهكير وهمي بالرد على شخص (شريط تحميل)
`.هكر` — تهكير وهمي بتصميم ترمينال أخضر
`.اختراق` — تهكير وهمي بتصميم ماتريكس
`.فيروس` — فيروس وهمي (مزح فقط!)"""),
}
COMMANDS_TEXT = "✦ ━━━━━━━━━━━ ✦\n   📜 **أوامر سورس سوبارو** 📜\n✦ ━━━━━━━━━━━ ✦\n\nاختر قسم من الأزرار تحت 👇"


def section_buttons():
    """أزرار شفافة (إنلاين) لأقسام الأوامر — زرين بكل سطر."""
    keys = list(COMMAND_SECTIONS.keys())
    rows = []
    for i in range(0, len(keys), 2):
        row = [Button.inline(COMMAND_SECTIONS[k][0], data=f"sec:{k}".encode()) for k in keys[i:i + 2]]
        rows.append(row)
    rows.append([Button.inline("📜 عرض الكل", data=b"sec:all")])
    return rows


def section_text(key):
    if key == "all":
        parts = [COMMANDS_TEXT] + [v[1] for v in COMMAND_SECTIONS.values()]
        return "\n\n".join(parts) + "\n\n✦ سورس سوبارو | Natsuki Subaru ✦"
    label, body = COMMAND_SECTIONS[key]
    return f"✦ ━━━━━━━━━━━ ✦\n   📜 **أوامر سورس سوبارو — {label}**\n✦ ━━━━━━━━━━━ ✦\n\n{body}\n\n👇 اختر قسم ثاني من الأزرار تحت"


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.(الاوامر|مساعدة)$"))
async def commands_list(event):
    try:
        await event.delete()
    except Exception:
        pass
    await client.send_message(event.chat_id, COMMANDS_TEXT, buttons=section_buttons())


@client.on(events.CallbackQuery)
async def commands_callback(event):
    """الضغط على أزرار أقسام الأوامر أو أزرار اختيار نوع البوت."""
    _d = event.data.decode(errors="ignore")
    if _d.startswith("vote:"):
        return  # أزرار التصويت لها معالج خاص بها، والكل يقدر يصوت
    if not event.is_private and event.sender_id != OWNER_ID and event.sender_id is not None:
        # أزرار الأوامر لك أنت فقط
        try:
            me = await client.get_me()
            if event.sender_id != me.id:
                await event.answer("هذه الأزرار لصاحب السورس فقط 🙂", alert=True)
                return
        except Exception:
            pass
    data = event.data.decode(errors="ignore")
    if data.startswith("sec:"):
        key = data[4:]
        if key not in COMMAND_SECTIONS and key != "all":
            return
        await event.edit(section_text(key), buttons=section_buttons())
        await event.answer()
    elif data.startswith("mode:"):
        mode = data[5:]
        await set_bot_mode(mode, event)
        await event.answer()


# ───────────────────────── بوت BotFather ─────────────────────────
BOT_MODE_FILE = "bot_mode.json"
BOT_MODE = {"mode": "all"}  # contact | protection | all
PROTECTION_FILE = "protection.json"
PROTECTION = {}  # chat_id -> settings
FLOOD_TRACK = {}  # (chat_id, user_id) -> [timestamps]
CONTACT_MAP = {}  # bot forwarded msg id -> user id
bot_client = None


def load_bot_mode():
    if os.path.exists(BOT_MODE_FILE):
        try:
            with open(BOT_MODE_FILE, encoding="utf-8") as f:
                BOT_MODE.update(json.load(f))
        except Exception:
            pass
    if os.path.exists(PROTECTION_FILE):
        try:
            with open(PROTECTION_FILE, encoding="utf-8") as f:
                PROTECTION.update({str(k): v for k, v in json.load(f).items()})
        except Exception:
            pass


def save_bot_mode():
    try:
        with open(BOT_MODE_FILE, "w", encoding="utf-8") as f:
            json.dump(BOT_MODE, f, ensure_ascii=False, indent=2)
        with open(PROTECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(PROTECTION, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def bot_mode_label(mode=None):
    mode = mode or BOT_MODE.get("mode", "all")
    return {
        "contact": "📩 بوت تواصل",
        "protection": "🛡️ بوت حماية قروبات",
        "all": "✅ الكل مع بعض (تواصل + حماية)",
    }.get(mode, mode)


def mode_buttons():
    return [
        [Button.inline("📩 بوت تواصل", data=b"mode:contact")],
        [Button.inline("🛡️ بوت حماية قروبات", data=b"mode:protection")],
        [Button.inline("✅ الكل مع بعض", data=b"mode:all")],
    ]


async def set_bot_mode(mode, event=None):
    BOT_MODE["mode"] = mode
    save_bot_mode()
    text = (
        f"🤖 **تم اختيار نوع البوت:** {bot_mode_label(mode)}\n\n"
        + {
            "contact": "📩 **بوت تواصل:** أي شخص يرسل للبوت رسالة خاصة، بتنبعت لك، وردك عليها بيرجع له.\nجرب: افتح البوت واكتب /start",
            "protection": "🛡️ **بوت حماية قروبات:** ضيف البوت لقروبك واجعله مشرف، وهو بيحذف الروابط، وبيمنع الفلوود والتحويل، وبيرحب بالأعضاء الجدد.\nأوامر الحماية في القروب: /ban /kick /warn /mute /lock_links",
            "all": "✅ **الكل مع بعض:** البوت بيشتغل تواصل في الخاص، وحماية في القروبات بنفس الوقت.",
        }[mode]
    )
    if event is not None:
        await event.edit(text, buttons=mode_buttons())
    return text


async def send_mode_selection():
    """رسالة اختيار نوع البوت — بتنبعت لك (الرسائل المحفوظة) أول ما يشتغل السورس."""
    if not BOT_TOKEN:
        return
    try:
        await client.send_message(
            "me",
            "🤖 **أهلاً في سورس سوبارو!**\n\n"
            "اختار نوع البوت اللي بدك ياه من الأزرار تحت 👇\n\n"
            "📩 **تواصل** — الناس تراسلك عن طريق البوت\n"
            "🛡️ **حماية قروبات** — البوت يحمي قروبك من الروابط والسبام\n"
            "✅ **الكل** — الاثنين مع بعض\n\n"
            f"النوع الحالي: {bot_mode_label()}",
            buttons=mode_buttons(),
        )
    except Exception as e:
        print(f"⚠️ ما قدرت أبعت رسالة اختيار البوت: {e}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.البوت$"))
async def bot_mode_cmd(event):
    if not BOT_TOKEN:
        await event.edit(
            "❌ **ما في توكن بوت بعد!**\n\n"
            "اعمل بوت من @BotFather:\n"
            "1. افتح @BotFather واكتب /newbot\n"
            "2. اختار اسم ويوزر للبوت\n"
            "3. انسخ التوكن وحطه في ملف .env باسم `BOT_TOKEN=`\n"
            "4. أعد تشغيل السورس، وراح تطلع لك رسالة اختيار النوع بأزرار"
        )
        return
    try:
        await event.delete()
    except Exception:
        pass
    await client.send_message(
        event.chat_id,
        f"🤖 **اختار نوع البوت:**\n\nالنوع الحالي: {bot_mode_label()}\n\n📩 تواصل | 🛡️ حماية قروبات | ✅ الكل",
        buttons=mode_buttons(),
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.وضع_البوت$"))
async def bot_mode_show(event):
    if not BOT_TOKEN:
        await event.edit("❌ ما في بوت مربوط بعد. اعمل بوت من @BotFather وحط توكنه في .env")
        return
    await event.edit(f"🤖 **نوع البوت الحالي:** {bot_mode_label()}\n\nغيّره بـ `.البوت`")


load_bot_mode()


# ───────────────────────── أوامر التسلية ─────────────────────────
JOKES = [
    "مرة واحد محشش سألوه: شو اسمك؟ قال: اسمي مكتوب على بطاقتي، بس نسيت وين حطيتها 😂",
    "مرة مدرس سأل طالب: شو يعني كلمة مستحيل؟ قال: يعني أبوي يوافق أطلع مع أصحابي 😅",
    "واحد راح للدكتور قاله: دكتور كل ما أشرب قهوة توجعني عيني، قاله: شيل الملعقة من الكوب ☕😂",
    "مرة واحد نذل راح على البحر، شاف واحد يغرق، قاله: ساعدني! قاله: آسف أنا ما بعرف أسبح، بس بقدر أصورك 📸😂",
    "ليش الكمبيوتر ما بيحب الشتاء؟ لأنه بيخاف من الفيروسات 🖥️❄️",
    "مرة سمكة سألت سمكة ثانية: شو رأيك بالبحر؟ قالت: مالح زيادة، بدنا سكر 🐟😂",
    "واحد سأل صاحبه: شو بتشتغل؟ قاله: بشتغل على نفسي، ولسا ما خلصت 😅",
    "مرة قلم رصاص قال للقلم الجاف: أنت دايماً غلطان وما بتنمسح، قاله: وأنت دايماً بتنكسر 😂",
    "ليش الطالب نام بالامتحان؟ لأنه كان يحلم بالنجاح 💤",
    "مرة واحد بخيل سألوه: شو بتعمل إذا فزت بمليون؟ قال: بحطهم بالبنك وبعيش على فوائدهم، يعني بصير غني وما بصرف شي 😂",
    "واحد راح يشتري خبز، قاله للخباز: عندك خبز بايت؟ قاله: لا، كله طازج، قاله: طيب بكرا بجي آخذه بايت 🍞😂",
    "مرة تلفون سأل الشاحن: ليش دايماً معصب؟ قاله: لأني دايماً مشحون 🔋😂",
]

QUOTES = [
    "«النجاح ليس نهائياً، والفشل ليس قاتلاً، الشجاعة للاستمرار هي ما يهم.» — ونستون تشرشل",
    "«لا تنتظر الفرصة، اصنعها.» — جورج برنارد شو",
    "«أفضل وقت لزراعة شجرة كان قبل عشرين سنة، وثاني أفضل وقت هو الآن.» — مثل صيني",
    "«العقل مثل العضلة، كلما دربته صار أقوى.»",
    "«من جدّ وجد، ومن زرع حصد.»",
    "«لا تخف من البدء من جديد، فهذه المرة أنت لا تبدأ من الصفر، بل من الخبرة.»",
    "«الحلم بلا خطة هو مجرد أمنية.»",
    "«كن أنت التغيير الذي تريد أن تراه في العالم.» — غاندي",
]

SARAHAA = [
    "ما هو أكبر سر تخفيه عن أصدقائك؟ 🤔",
    "لو تقدر ترجع بالزمن، شو أول شي بتغيره؟ ⏳",
    "من هو الشخص اللي ما تقدر تعيش بدونه؟ ❤️",
    "شو أكثر موقف محرج صار معك بحياتك؟ 😳",
    "لو عندك مليون دولار، شو أول شي بتعمله؟ 💰",
    "ما هو الشيء اللي بتخاف منه أكثر شي؟ 😨",
    "من هو قدوتك بالحياة وليش؟ 🌟",
    "شو أكثر شي بتندم عليه؟ 😔",
    "لو تقدر تكون أي شخصية أنمي، مين بتختار؟ 🎌",
    "شو هو حلمك اللي لسا ما حققته؟ ✨",
]

RIDDLES = [
    ("شي كل ما أخذت منه يكبر، ما هو؟", "الحفرة 🕳️"),
    ("ما هو الشيء الذي يصعد ولا ينزل أبداً؟", "العمر ⏳"),
    ("شي له أسنان وما يعض، ما هو؟", "المشط 🪮"),
    ("ما هو الشيء الذي أمامك دائماً ولا تراه؟", "المستقبل 🔮"),
    ("شي يمشي بلا رجلين ويدخل الأذن، ما هو؟", "الصوت 🔊"),
    ("ما هو الشيء الذي كلما زاد نقص؟", "العمر ⏳"),
    ("بيت بلا أبواب ولا نوافذ، ما هو؟", "البيضة 🥚"),
    ("ما هو الشيء الذي له عين واحدة ولا يرى؟", "الإبرة 🪡"),
]

LUCK = [
    "🍀 حظك اليوم ممتاز! في مفاجأة حلوة بانتظارك.",
    "🌟 يومك مليان طاقة إيجابية، استغلها صح.",
    "💰 في فلوس جاية بطريقك، بس انتبه من المصاريف الزايدة.",
    "❤️ في شخص بيفكر فيك هلا، يمكن يرسل لك رسالة اليوم.",
    "🎯 ركز على هدفك اليوم، النجاح قريب أكثر مما تتخيل.",
    "😌 يوم هادئ ومناسب للراحة وإعادة ترتيب أفكارك.",
    "🚀 فرصة جديدة راح تظهر قدامك، لا تتردد تمسك فيها.",
    "🤝 لقاء مع صديق قديم راح يفرح قلبك اليوم.",
]


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.نكتة$"))
async def joke_cmd(event):
    await event.edit(f"😂 **نكتة:**\n\n{random.choice(JOKES)}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.اقتباس$"))
async def quote_cmd(event):
    await event.edit(f"💡 **اقتباس:**\n\n{random.choice(QUOTES)}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حظ$"))
async def luck_cmd(event):
    await event.edit(f"🔮 **حظك اليوم:**\n\n{random.choice(LUCK)}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.صراحة$"))
async def saraha_cmd(event):
    await event.edit(f"🎤 **سؤال صراحة:**\n\n{random.choice(SARAHAA)}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.لغز$"))
async def riddle_cmd(event):
    q, a = random.choice(RIDDLES)
    await event.edit(f"🧩 **لغز:**\n\n{q}\n\n||الحل: {a}||")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.عملة$"))
async def coin_cmd(event):
    result = random.choice(["👑 ملك", "🔢 كتابة"])
    await event.edit(f"🪙 **العملة طلعت:** {result}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حجر(?:\s+(.+))?$"))
async def rps_cmd(event):
    choice = (event.pattern_match.group(1) or "").strip()
    options = {"حجر": "🪨 حجر", "ورقة": "📄 ورقة", "مقص": "✂️ مقص"}
    if choice not in options:
        await event.edit("✊ **اكتب:** `.حجر حجر` أو `.حجر ورقة` أو `.حجر مقص`")
        return
    bot = random.choice(list(options.values()))
    you = options[choice]
    wins = {("🪨 حجر", "✂️ مقص"), ("📄 ورقة", "🪨 حجر"), ("✂️ مقص", "📄 ورقة")}
    if you == bot:
        res = "🤝 تعادل!"
    elif (you, bot) in wins:
        res = "🎉 فزت عليّ!"
    else:
        res = "😎 فزت عليك!"
    await event.edit(f"✊✋✌️ **حجر ورقة مقص:**\n\nأنت: {you}\nأنا: {bot}\n\n{res}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.نسبة(?:\s+(.+))?$"))
async def percent_cmd(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        await event.edit("💞 **اكتب:** `.نسبة اسم1 اسم2`\nمثال: `.نسبة أحمد سارة`")
        return
    names = arg.split()
    if len(names) < 2:
        names = names + ["؟"]
    # نسبة ثابتة لنفس الاسمين (عشان ما تتغير كل مرة)
    seed = sum(ord(c) for c in arg)
    pct = (seed * 37) % 101
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    await event.edit(f"💞 **نسبة التوافق بين {names[0]} و {names[1]}:**\n\n{pct}% \n{bar}\n\n{'❤️❤️❤️ حب قوي!' if pct >= 80 else '💛 حب متوسط' if pct >= 50 else '🤍 لسه بدري عليهم'}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تقييم$"))
async def rate_cmd(event):
    pct = random.randint(1, 100)
    await event.edit(f"⭐ **تقييمك اليوم:** {pct}/100\n{'🔥 أسطوري!' if pct >= 90 else '👍 ممتاز' if pct >= 70 else '🙂 جيد' if pct >= 50 else '😅 بدك شغل على حالك'}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.سؤال$"))
async def question_cmd(event):
    qs = [
        "شو أكثر أنمي بتحبه وليش؟ 🎌",
        "لو تقدر تسافر لأي مكان بالعالم، وين بتروح؟ ✈️",
        "شو أكتر أكلة بتحبها؟ 🍔",
        "بتفضل الليل ولا النهار؟ 🌙☀️",
        "شو آخر فيلم شفته وعجبك؟ 🎬",
        "لو عندك قوة خارقة، شو بتختار؟ 🦸",
    ]
    await event.edit(f"❓ **سؤال:**\n\n{random.choice(qs)}")


# ───────────────────────── إدارة القروب ─────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.انضم(?:\s+(.+))?$"))
async def join_cmd(event):
    link = (event.pattern_match.group(1) or "").strip()
    if not link:
        await event.edit("❌ اكتب: `.انضم رابط_القروب`")
        return
    try:
        st, val = extract_source(link)
        await join_source(st, val)
        await event.edit(f"✅ دخلت القروب: {link}")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أدخل.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.غادر$"))
async def leave_cmd(event):
    try:
        await client(LeaveChannelRequest(event.chat_id))
        await event.edit("👋 غادرت القروب.")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أغادر.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.طرد$"))
async def kick_cmd(event):
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("❌ رد على رسالة الشخص اللي بدك تطرده ثم اكتب `.طرد`")
        return
    try:
        await client.kick_participant(event.chat_id, reply.sender_id)
        await event.edit(f"👢 تم طرد {reply.sender.first_name} من القروب.")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أطرده، لازم تكون مشرف.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ترحيب$"))
async def welcome_toggle(event):
    WELCOME["enabled"] = not WELCOME["enabled"]
    status = "مفعّل ✅" if WELCOME["enabled"] else "متوقف ⏹️"
    await event.edit(f"👋 **الترحيب بالأعضاء الجدد:** {status}")


@client.on(events.ChatAction)
async def welcome_new(event):
    if not WELCOME["enabled"]:
        return
    if event.user_joined or event.user_added:
        try:
            user = await event.get_user()
            chat = await event.get_chat()
            template = WELCOME_MSG.get(str(event.chat_id), "👋 أهلاً وسهلاً {اسم} نورت القروب! 🎉\n✦ سورس سوبارو ✦")
            text = template.replace("{اسم}", user.first_name or "").replace("{قروب}", getattr(chat, "title", "") or "")
            await event.reply(text)
        except Exception:
            pass


# ───────────────────────── النشر التلقائي: الأوامر ─────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.جدولة(?:\s+(.+))?$"))
async def schedule_add(event):
    """
    طريقتين لاستخدام الأمر:
    1) برابط/معرف: .جدولة @القروب 60 صباح الخير
    2) داخل القروب نفسه (حتى لو ما له رابط): .جدولة 60 صباح الخير
       — القروب هو القروب اللي انكتب فيه الأمر
    .جدولة https://t.me/group 120 رسالة1 | رسالة2 | رسالة3 --عشوائي --تثبيت --عدد=10
    """
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        await event.edit(
            "❌ **اكتب الأمر صح:**\n\n"
            "**برابط:** `.جدولة @القروب 60 رسالتك`\n"
            "**داخل القروب نفسه (بدون رابط):** `.جدولة 60 رسالتك`\n\n"
            "**مثال:**\n`.جدولة @mygroup 60 صباح الخير ☀️`\n"
            "`.جدولة 120 رسالة1 | رسالة2 | رسالة3`\n\n"
            "**خيارات (في آخر الأمر):**\n"
            "`--عشوائي` — رسالة عشوائية كل مرة\n"
            "`--تثبيت` — تثبيت كل رسالة\n"
            "`--عدد=10` — يوقف بعد 10 مرات\n\n"
            "**متغيرات تقدر تحطها بالرسالة:**\n`{وقت}` `{تاريخ}` `{يوم}` `{قروب}`"
        )
        return

    # استخراج الخيارات من آخر الأمر
    pin = "--تثبيت" in arg
    random_mode = "--عشوائي" in arg
    max_count = None
    m = re.search(r"--عدد=(\d+)", arg)
    if m:
        max_count = int(m.group(1))
    arg = re.sub(r"--(تثبيت|عشوائي|عدد=\d+)", "", arg).strip()

    # تحديد القروب: إذا أول كلمة رقم → القروب الحالي، وإلا أول كلمة هي القروب
    parts = arg.split(None, 2)
    chat_ref = None
    if parts and parts[0].isdigit():
        # .جدولة 60 رسالتك — داخل القروب نفسه
        if len(parts) < 2:
            await event.edit("❌ ناقص شي! الصيغة داخل القروب: `.جدولة 60 رسالتك`")
            return
        minutes_str, text = parts[0], parts[1]
    elif len(parts) >= 3:
        chat_ref, minutes_str, text = parts
    else:
        await event.edit("❌ ناقص شي! الصيغة: `.جدولة القروب الدقائق الرسالة` أو داخل القروب: `.جدولة الدقائق الرسالة`")
        return
    try:
        minutes = int(minutes_str)
    except ValueError:
        await event.edit("❌ الدقائق لازم تكون رقم، مثال: `60` يعني كل ساعة.")
        return
    if minutes < 5:
        await event.edit("⚠️ أقل فترة مسموحة 5 دقائق، عشان ما يجيك حظر فلوود.\nجرب 5 أو أكثر.")
        return
    if minutes > 10080:
        await event.edit("⚠️ أقصى فترة 10080 دقيقة (أسبوع).")
        return

    messages = [t.strip() for t in text.split("|") if t.strip()]
    if not messages:
        await event.edit("❌ اكتب رسالة للنشر.")
        return

    try:
        if chat_ref is None:
            # القروب الحالي اللي انكتب فيه الأمر — يشتغل حتى لو القروب ما له رابط
            target = await event.get_chat()
            chat_id = target.id
            chat_title = getattr(target, "title", None) or "هذا القروب"
        else:
            st, val = extract_source(chat_ref)
            target = await client.get_entity(val) if st == "username" else await join_source(st, val)
            chat_id = target.id
            chat_title = getattr(target, "title", None) or getattr(target, "username", chat_ref)
    except Exception as e:
        await event.edit(f"❌ ما قدرت أوصل للقروب: `{chat_ref or 'الحالي'}`\nتأكد من المعرف/الرابط وأنك عضو فيه.\n\n`{e}`")
        await send_log("❌ فشل إنشاء جدولة نشر", str(e), "الرابط/المعرف غلط، أو القروب خاص وما عندك صلاحية، أو ما انضممت له بعد.")
        return

    sid = next_schedule_id()
    SCHEDULES[sid] = {
        "chat_id": chat_id,
        "chat_title": chat_title,
        "messages": messages,
        "interval": minutes,
        "next_run": time.time() + minutes * 60,
        "sent_count": 0,
        "fails": 0,
        "last_index": -1,
        "pin": pin,
        "random": random_mode,
        "max_count": max_count,
        "enabled": True,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_schedules()
    await event.edit(
        f"✅ **تمت إضافة النشر التلقائي (رقم {sid})**\n\n"
        f"📢 **القروب:** {chat_title}\n"
        f"⏱️ **كل:** {minutes} دقيقة\n"
        f"💬 **عدد الرسائل:** {len(messages)} {'(عشوائي 🎲)' if random_mode else '(تدوير بالترتيب 🔄)'}\n"
        f"📌 **تثبيت:** {'نعم' if pin else 'لا'}\n"
        f"🔢 **الحد:** {max_count if max_count else 'بدون حد ∞'}\n"
        f"🕐 **أول نشر:** بعد {minutes} دقيقة\n\n"
        f"اكتب `.النشرات` لتشوف كل الجدولات، و `.نشر_الان {sid}` للنشر فوراً."
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.النشرات$"))
async def schedule_list(event):
    if not SCHEDULES:
        await event.edit("📭 ما في أي نشرة مجدولة حالياً.\nأضف وحدة بـ: `.جدولة @القروب 60 رسالتك`")
        return
    lines = ["📢 **النشرات المجدولة:**\n"]
    for sid, job in SCHEDULES.items():
        mins_left = max(0, int((job["next_run"] - time.time()) // 60))
        status = "✅ شغالة" if job.get("enabled") else "⏹️ متوقفة"
        lines.append(
            f"**#{sid}** — {job.get('chat_title', job['chat_id'])} — {status}\n"
            f"⏱️ كل {job['interval']} دقيقة | ⏳ المتبقي ~{mins_left} دقيقة\n"
            f"💬 {len(job['messages'])} رسالة | 📤 تم النشر {job.get('sent_count', 0)} مرة\n"
            f"📝 أول رسالة: {job['messages'][0][:60]}\n"
        )
    lines.append("`.نشر_الان رقم` للنشر فوراً | `.ايقاف_النشر رقم` للحذف")
    await event.edit("\n".join(lines))


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.نشر_الان(?:\s+(\d+))?$"))
async def schedule_send_now(event):
    sid = event.pattern_match.group(1)
    if not sid or sid not in SCHEDULES:
        await event.edit("❌ اكتب رقم الجدولة، مثال: `.نشر_الان 1`\nاكتب `.النشرات` لتشوف الأرقام.")
        return
    job = SCHEDULES[sid]
    msgs = job["messages"]
    text = random.choice(msgs) if job.get("random") else msgs[(job.get("last_index", -1) + 1) % len(msgs)]
    try:
        chat = await client.get_entity(job["chat_id"])
        sent = await client.send_message(job["chat_id"], format_post(text, getattr(chat, "title", "")))
        if job.get("pin"):
            try:
                await client.pin_message(job["chat_id"], sent.id, notify=False)
            except Exception:
                pass
        job["sent_count"] = job.get("sent_count", 0) + 1
        job["next_run"] = time.time() + job["interval"] * 60
        save_schedules()
        await event.edit(f"✅ تم النشر فوراً في {job.get('chat_title', '')} (جدولة #{sid})")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أنشر.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ايقاف_النشر(?:\s+(\d+))?$"))
async def schedule_stop(event):
    sid = event.pattern_match.group(1)
    if not sid or sid not in SCHEDULES:
        await event.edit("❌ اكتب رقم الجدولة، مثال: `.ايقاف_النشر 1`\nاكتب `.النشرات` لتشوف الأرقام.")
        return
    title = SCHEDULES[sid].get("chat_title", "")
    del SCHEDULES[sid]
    save_schedules()
    await event.edit(f"⏹️ تم إيقاف وحذف النشر التلقائي #{sid} ({title})")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ايقاف_النشر_الكل$"))
async def schedule_stop_all(event):
    count = len(SCHEDULES)
    SCHEDULES.clear()
    save_schedules()
    await event.edit(f"⏹️ تم إيقاف وحذف كل النشرات ({count}).")


# ───────────────────────── السجل والتخزين: الأوامر والأرشفة ─────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.السجل$"))
async def show_log_group(event):
    gid = SYSTEM.get("log_id")
    if not gid:
        await event.edit("❌ قروب السجل مو موجود. اكتب `.انشاء_المجموعات` لإنشائه.")
        return
    await event.edit(f"📋 **قروب السجل:**\n`{gid}`\n\nأي خطأ أو مشكلة بتنبعت هناك مع شرح شو المشكلة وليش صارت.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.التخزين$"))
async def show_storage_group(event):
    gid = SYSTEM.get("storage_id")
    if not gid:
        await event.edit("❌ قروب التخزين مو موجود. اكتب `.انشاء_المجموعات` لإنشائه.")
        return
    topics = ", ".join(SYSTEM.get("topics", {}).keys()) or "بدون أقسام (منتدى غير مفعّل)"
    await event.edit(f"🗄️ **قروب التخزين:**\n`{gid}`\n\n**الأقسام:** {topics}\n\nالأرشفة: {'مفعّلة ✅' if ARCHIVE['enabled'] else 'متوقفة ⏹️'} — اكتب `.ارشيف` للتبديل.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.انشاء_المجموعات$"))
async def recreate_system_groups(event):
    await event.edit("🔄 جاري إنشاء / تحديث قروبي السجل والتخزين...")
    await ensure_system_groups(force=True)
    await event.edit(
        f"✅ **تم إنشاء القروبين:**\n\n"
        f"📋 السجل: `{SYSTEM.get('log_id')}`\n"
        f"🗄️ التخزين: `{SYSTEM.get('storage_id')}`\n\n"
        "صورة القروبين صورة سوبارو."
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ارشيف$"))
async def archive_toggle(event):
    ARCHIVE["enabled"] = not ARCHIVE["enabled"]
    status = "مفعّلة ✅" if ARCHIVE["enabled"] else "متوقفة ⏹️"
    await event.edit(f"🗄️ **أرشفة الرسائل في قروب التخزين:** {status}")


@client.on(events.NewMessage(incoming=True))
async def archive_incoming(event):
    """أرشفة: أي رسالة خاصة توصلك، أو أي رسالة بالقروب رد على رسالتك، بتروح لقروب التخزين بقسمها الخاص."""
    if not ARCHIVE["enabled"]:
        return
    storage_id = SYSTEM.get("storage_id")
    if not storage_id:
        return
    # لا تأرشف رسائل قروبي السجل والتخزين نفسهم (عشان ما يصير لوب)
    if event.chat_id in (SYSTEM.get("log_id"), storage_id):
        return
    # لا تأرشف رسائلك أنت الصادرة
    if event.out:
        return

    should_archive = False
    source_label = ""
    if event.is_private:
        should_archive = True
        sender = await event.get_sender()
        name = getattr(sender, "first_name", "شخص") or "شخص"
        source_label = f"📩 خاص من {name} (@{getattr(sender, 'username', '') or 'بدون يوزر'})"
    elif event.is_group or event.is_channel:
        # رد على رسالتك أنت فقط
        reply = await event.get_reply_message()
        if reply and reply.out:
            should_archive = True
            sender = await event.get_sender()
            chat = await event.get_chat()
            source_label = f"💬 رد من {getattr(sender, 'first_name', '')} في {getattr(chat, 'title', '')}"

    if not should_archive:
        return

    category = archive_category(event.message)
    topic_id = SYSTEM.get("topics", {}).get(category)
    caption = f"{source_label}\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n#{category}"
    try:
        # نحاول نرسلها داخل قسمها (توبيك)؛ إذا ما ضبط، بتنبعت عادي في القروب
        kwargs = {}
        if topic_id:
            kwargs["reply_to"] = topic_id
        if event.message.media:
            await client.send_file(storage_id, event.message.media, caption=caption + (f"\n\n{event.message.text or ''}" if event.message.text else ""), **kwargs)
        else:
            await client.send_message(storage_id, caption + f"\n\n{event.message.text or ''}", **kwargs)
    except Exception:
        try:
            if event.message.media:
                await client.send_file(storage_id, event.message.media, caption=caption)
            else:
                await client.send_message(storage_id, caption + f"\n\n{event.message.text or ''}")
        except Exception as e:
            await send_log("❌ فشل الأرشفة في قروب التخزين", str(e), "غالباً مشكلة بالوسائط أو انحذف قروب التخزين. اكتب `.انشاء_المجموعات` لإعادة إنشائه.")


# ───────────────────────── يوتيوب: تحميل صوت وفيديو ─────────────────────────
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def is_youtube_link(text):
    return "youtube.com" in text or "youtu.be" in text or "music.youtube.com" in text


def yt_query(user_input):
    """إذا كان رابط يرجعه كما هو، وإذا كان اسم يبحث عنه في يوتيوب."""
    user_input = user_input.strip()
    if is_youtube_link(user_input):
        return user_input
    return f"ytsearch1:{user_input}"


async def run_ytdlp(args, timeout=600):
    """يشغل yt-dlp بدون ما يعلق البوت، ويرجع (كود الخروج، الخرج، الخطأ)."""
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 1, "", "انتهى الوقت أثناء التحميل"
    return proc.returncode, out.decode(errors="ignore"), err.decode(errors="ignore")


async def yt_info(query):
    """يجيب معلومات أول نتيجة: العنوان، المدة، الرابط، الصورة."""
    code, out, err = await run_ytdlp(["--dump-json", "--no-playlist", query], timeout=120)
    if code != 0 or not out.strip():
        return None, err.strip()[-500:]
    try:
        info = json.loads(out.strip().splitlines()[0])
    except Exception:
        return None, "ما قدرت أقرأ معلومات الفيديو"
    return info, ""


def format_duration(seconds):
    if not seconds:
        return "؟"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.يوت(?:\s+(.+))?$"))
async def yt_audio(event):
    """تحميل صوت MP3: .يوت اسم الأغنية  أو  .يوت رابط يوتيوب"""
    query_text = (event.pattern_match.group(1) or "").strip()
    if not query_text:
        await event.edit("❌ **اكتب:** `.يوت اسم الأغنية` أو `.يوت رابط يوتيوب`\nمثال: `.يوت Alan Walker Faded`")
        return
    await event.edit(f"🔍 **جاري البحث عن:** {query_text} ...")
    info, err = await yt_info(yt_query(query_text))
    if not info:
        await event.edit(f"❌ ما لقيت شي على يوتيوب.\n`{err}`")
        await send_log("❌ فشل تحميل يوتيوب (صوت)", err or query_text, "الاسم/الرابط غلط، أو الفيديو محذوف/خاص، أو يوتيوب حظر الطلب مؤقتاً. جرب رابط مباشر.")
        return
    duration = info.get("duration") or 0
    if duration > 900:
        await event.edit(f"❌ الفيديو طويل ({format_duration(duration)}) — الأقصى للصوت 15 دقيقة.")
        return
    title = info.get("title", "audio")
    url = info.get("webpage_url") or info.get("id", "")
    await event.edit(f"⬇️ **جاري تحميل الصوت...**\n🎵 {title}\n⏱️ {format_duration(duration)}")
    safe = re.sub(r'[\\/*?:"<>|]', "", title)[:80] or "audio"
    out_template = os.path.join(DOWNLOAD_DIR, f"{safe}.%(ext)s")
    code, out, err = await run_ytdlp([
        "-f", "bestaudio/best", "--extract-audio", "--audio-format", "mp3",
        "--audio-quality", "192K", "--no-playlist",
        "-o", out_template, url,
    ])
    mp3_path = os.path.join(DOWNLOAD_DIR, f"{safe}.mp3")
    if code != 0 or not os.path.exists(mp3_path):
        await event.edit(f"❌ فشل التحميل.\n`{err.strip()[-400:]}`")
        await send_log("❌ فشل تحميل يوتيوب (صوت)", err.strip()[-400:], "غالباً الفيديو محمي أو فيه قيود عمر/منطقة، أو مشكلة مؤقتة من يوتيوب.")
        return
    size_mb = os.path.getsize(mp3_path) / 1024 / 1024
    try:
        await event.delete()
        await client.send_file(
            event.chat_id, mp3_path,
            caption=f"🎵 **{title}**\n⏱️ {format_duration(duration)} | 💾 {size_mb:.1f} MB\n🔗 {url}\n✦ سورس سوبارو ✦",
            attributes=[],
        )
    finally:
        try:
            os.remove(mp3_path)
        except Exception:
            pass


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.يوت_فيديو(?:\s+(.+))?$"))
async def yt_video(event):
    """تحميل فيديو MP4: .يوت_فيديو اسم الفيديو  أو  .يوت_فيديو رابط يوتيوب"""
    query_text = (event.pattern_match.group(1) or "").strip()
    if not query_text:
        await event.edit("❌ **اكتب:** `.يوت_فيديو اسم الفيديو` أو `.يوت_فيديو رابط يوتيوب`")
        return
    await event.edit(f"🔍 **جاري البحث عن:** {query_text} ...")
    info, err = await yt_info(yt_query(query_text))
    if not info:
        await event.edit(f"❌ ما لقيت شي على يوتيوب.\n`{err}`")
        return
    duration = info.get("duration") or 0
    if duration > 1200:
        await event.edit(f"❌ الفيديو طويل ({format_duration(duration)}) — الأقصى للفيديو 20 دقيقة.")
        return
    title = info.get("title", "video")
    url = info.get("webpage_url") or info.get("id", "")
    await event.edit(f"⬇️ **جاري تحميل الفيديو (720p)...**\n🎬 {title}\n⏱️ {format_duration(duration)}")
    safe = re.sub(r'[\\/*?:"<>|]', "", title)[:80] or "video"
    out_template = os.path.join(DOWNLOAD_DIR, f"{safe}.%(ext)s")
    code, out, err = await run_ytdlp([
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]/best",
        "--merge-output-format", "mp4", "--no-playlist",
        "-o", out_template, url,
    ])
    video_path = None
    for ext in ("mp4", "mkv", "webm"):
        p = os.path.join(DOWNLOAD_DIR, f"{safe}.{ext}")
        if os.path.exists(p):
            video_path = p
            break
    if code != 0 or not video_path:
        await event.edit(f"❌ فشل تحميل الفيديو.\n`{err.strip()[-400:]}`")
        await send_log("❌ فشل تحميل يوتيوب (فيديو)", err.strip()[-400:], "غالباً الفيديو محمي أو فيه قيود، أو حجمه كبير. جرب فيديو أقصر.")
        return
    size_mb = os.path.getsize(video_path) / 1024 / 1024
    if size_mb > 1900:
        await event.edit("❌ حجم الفيديو أكبر من حد تيليجرام.")
        os.remove(video_path)
        return
    try:
        await event.delete()
        await client.send_file(
            event.chat_id, video_path,
            caption=f"🎬 **{title}**\n⏱️ {format_duration(duration)} | 💾 {size_mb:.1f} MB\n🔗 {url}\n✦ سورس سوبارو ✦",
            supports_streaming=True,
        )
    finally:
        try:
            os.remove(video_path)
        except Exception:
            pass


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.بحث_يوت(?:\s+(.+))?$"))
async def yt_search(event):
    """يعرض أول 5 نتائج من يوتيوب عشان تختار منها."""
    query_text = (event.pattern_match.group(1) or "").strip()
    if not query_text:
        await event.edit("❌ اكتب: `.بحث_يوت اسم الأغنية`")
        return
    await event.edit(f"🔍 جاري البحث عن: {query_text} ...")
    code, out, err = await run_ytdlp([
        "--dump-json", "--no-playlist", "--flat-playlist",
        f"ytsearch5:{query_text}",
    ], timeout=120)
    if code != 0 or not out.strip():
        await event.edit(f"❌ ما لقيت نتائج.\n`{err.strip()[-300:]}`")
        return
    lines = [f"🔍 **نتائج يوتيوب لـ: {query_text}**\n"]
    for line in out.strip().splitlines()[:5]:
        try:
            info = json.loads(line)
            lines.append(
                f"🎵 **{info.get('title', '؟')}**\n"
                f"⏱️ {format_duration(info.get('duration'))} | 👤 {info.get('uploader', '')}\n"
                f"🔗 https://youtu.be/{info.get('id', '')}\n"
            )
        except Exception:
            continue
    lines.append("للتحميل اكتب: `.يوت رابط الفيديو`")
    await event.edit("\n".join(lines))


# ───────────────────────── بوت BotFather: التواصل والحماية ─────────────────────────
def bot_enabled(kind):
    mode = BOT_MODE.get("mode", "all")
    return mode == "all" or mode == kind


def protection_settings(chat_id):
    return PROTECTION.setdefault(str(chat_id), {
        "lock_links": True, "lock_forward": True, "anti_flood": True,
        "welcome": True, "warns": {},
    })


async def bot_is_admin(chat_id, user_id):
    try:
        perms = await bot_client.get_permissions(chat_id, user_id)
        return perms.is_admin or perms.is_creator
    except Exception:
        return False


async def setup_bot_client():
    """يشغل بوت BotFather إذا في توكن، ويربط أوامره."""
    global bot_client
    if not BOT_TOKEN:
        print("🤖 ما في BOT_TOKEN — البوت مطفي، اليوزربوت شغال عادي")
        return None
    bot_client = TelegramClient("subaru_bot", API_ID, API_HASH)
    await bot_client.start(bot_token=BOT_TOKEN)
    me = await bot_client.get_me()
    print(f"🤖 بوت BotFather شغال: @{me.username} — الوضع: {bot_mode_label()}")

    @bot_client.on(events.NewMessage(pattern=r"^/start"))
    async def bot_start(event):
        if event.is_private:
            await event.reply(
                "👋 **أهلاً فيك في بوت سوبارو!**\n\n"
                "📩 ارسل رسالتك هون، وراح توصل لصاحب البوت ويرد عليك.\n"
                "✦ Natsuki Subaru ✦"
            )
        else:
            await event.reply("👋 أهلاً! أنا بوت سوبارو — للحماية اكتب /help")

    @bot_client.on(events.NewMessage(pattern=r"^/help"))
    async def bot_help(event):
        if event.is_private:
            await event.reply("📩 ارسل أي رسالة وسيتم توصيلها لصاحب البوت.\n/start للبداية")
        else:
            await event.reply(
                "🛡️ **أوامر الحماية (للمشرفين فقط):**\n"
                "/ban — بالرد على الشخص لحظره\n/kick — بالرد لطرده\n/warn — بالرد لإنذاره (3 إنذارات = حظر)\n/mute — بالرد لكتمه\n/unmute — بالرد لفك الكتم\n/lock_links — تشغيل/إيقاف منع الروابط\n/welcome — تشغيل/إيقاف الترحيب"
            )

    @bot_client.on(events.NewMessage(pattern=r"^/(ban|kick|warn|mute|unmute|lock_links|welcome)"))
    async def bot_admin_cmds(event):
        if event.is_private or not bot_enabled("protection"):
            return
        if not await bot_is_admin(event.chat_id, event.sender_id):
            await event.reply("❌ هذا الأمر للمشرفين فقط.")
            return
        cmd = event.pattern_match.group(1)
        reply = await event.get_reply_message()
        settings = protection_settings(event.chat_id)
        if cmd == "lock_links":
            settings["lock_links"] = not settings["lock_links"]
            save_bot_mode()
            await event.reply(f"🔗 منع الروابط: {'مفعّل ✅' if settings['lock_links'] else 'متوقف ⏹️'}")
            return
        if cmd == "welcome":
            settings["welcome"] = not settings["welcome"]
            save_bot_mode()
            await event.reply(f"👋 الترحيب: {'مفعّل ✅' if settings['welcome'] else 'متوقف ⏹️'}")
            return
        if not reply:
            await event.reply("❌ رد على رسالة الشخص أولاً.")
            return
        target = reply.sender_id
        try:
            if cmd == "ban":
                await bot_client(EditBannedRequest(event.chat_id, target, ChatBannedRights(until_date=None, view_messages=True)))
                await event.reply("🔨 تم حظر الشخص.")
            elif cmd == "kick":
                await bot_client.kick_participant(event.chat_id, target)
                await event.reply("👢 تم طرد الشخص.")
            elif cmd == "mute":
                await bot_client(EditBannedRequest(event.chat_id, target, ChatBannedRights(until_date=None, send_messages=True)))
                await event.reply("🔇 تم كتم الشخص.")
            elif cmd == "unmute":
                await bot_client(EditBannedRequest(event.chat_id, target, ChatBannedRights(until_date=None, send_messages=False)))
                await event.reply("🔊 تم فك الكتم.")
            elif cmd == "warn":
                warns = settings.setdefault("warns", {})
                warns[str(target)] = warns.get(str(target), 0) + 1
                save_bot_mode()
                if warns[str(target)] >= 3:
                    await bot_client(EditBannedRequest(event.chat_id, target, ChatBannedRights(until_date=None, view_messages=True)))
                    warns[str(target)] = 0
                    await event.reply("⚠️ 3 إنذارات — تم حظر الشخص.")
                else:
                    await event.reply(f"⚠️ إنذار {warns[str(target)]}/3 للشخص.")
        except Exception as e:
            await event.reply(f"❌ ما قدرت أنفذ الأمر — لازم البوت يكون مشرف.\n`{e}`")

    @bot_client.on(events.NewMessage)
    async def bot_messages(event):
        # ── التواصل في الخاص ──
        if event.is_private and bot_enabled("contact"):
            if not OWNER_ID:
                return
            if event.sender_id == OWNER_ID:
                # رد صاحب البوت على رسالة محولة = يرجع للمستخدم الأصلي
                reply = await event.get_reply_message()
                if reply and reply.id in CONTACT_MAP:
                    user_id = CONTACT_MAP[reply.id]
                    try:
                        await bot_client.send_message(user_id, event.text)
                        await event.reply("✅ وصل ردك للمستخدم.")
                    except Exception as e:
                        await event.reply(f"❌ ما قدرت أوصل الرد.\n`{e}`")
                return
            if event.text and event.text.startswith("/"):
                return
            sender = await event.get_sender()
            fwd = await bot_client.send_message(
                OWNER_ID,
                f"📩 **رسالة جديدة للتواصل:**\n"
                f"👤 {sender.first_name} (@{getattr(sender, 'username', '') or 'بدون يوزر'})\n"
                f"🆔 `{sender.id}`\n\n{event.text or ''}",
            )
            CONTACT_MAP[fwd.id] = sender.id
            await event.reply("✅ وصلت رسالتك لصاحب البوت، راح يرد عليك قريباً 🙏")
            return

        # ── الحماية في القروبات ──
        if (event.is_group or event.is_channel) and bot_enabled("protection"):
            if await bot_is_admin(event.chat_id, event.sender_id):
                return
            settings = protection_settings(event.chat_id)
            text = event.text or ""
            # منع الروابط
            if settings.get("lock_links") and re.search(r"(https?://|t\.me/|www\.)", text):
                try:
                    await event.delete()
                    await event.reply("🔗 الروابط ممنوعة في هذا القروب.")
                except Exception:
                    pass
                return
            # منع التحويل (الفوروارد)
            if settings.get("lock_forward") and event.message.forward:
                try:
                    await event.delete()
                except Exception:
                    pass
                return
            # منع الفلوود: أكثر من 6 رسائل بـ 10 ثواني
            if settings.get("anti_flood"):
                key = (event.chat_id, event.sender_id)
                now = time.time()
                times = [t for t in FLOOD_TRACK.get(key, []) if now - t < 10]
                times.append(now)
                FLOOD_TRACK[key] = times
                if len(times) > 6:
                    try:
                        await event.delete()
                        await bot_client(EditBannedRequest(
                            event.chat_id, event.sender_id,
                            ChatBannedRights(until_date=int(now) + 600, send_messages=True),
                        ))
                        await event.reply("🚫 فلوود! تم كتمك 10 دقائق.")
                    except Exception:
                        pass
                    FLOOD_TRACK[key] = []

    @bot_client.on(events.ChatAction)
    async def bot_welcome(event):
        if not bot_enabled("protection"):
            return
        if event.user_joined or event.user_added:
            settings = protection_settings(event.chat_id)
            if not settings.get("welcome"):
                return
            try:
                user = await event.get_user()
                await event.reply(f"👋 أهلاً وسهلاً {user.first_name} نورت القروب! 🎉")
            except Exception:
                pass

    return bot_client


# ───────────────────────── إدارة متقدمة: تحويل، نسخ، حذف، تثبيت، حظر، تنظيف ─────────────────────────
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ ما قدرت أحفظ {path}: {e}")


FORWARDS = load_json("forwards.json", {})      # id -> {source_id, target_id, source, target, mode}
AUTODELETE = load_json("autodelete.json", {})  # chat_id -> minutes
AUTOPIN = load_json("autopin.json", [])        # [chat_id]
BANNED = load_json("banned.json", {})          # chat_id -> {"words": [], "links": bool}
WELCOME_MSG = load_json("welcome.json", {})    # chat_id -> custom text
CLEAN_PENDING = {}  # chat_id -> [user_ids]


def resolve_chat_ref(ref):
    """يرجع (chat_id, title) من رابط/معرف، أو None إذا فشل."""
    return ref


async def get_chat_by_ref(ref):
    st, val = extract_source(ref)
    if st == "invite":
        return await join_source(st, val)
    return await client.get_entity(val)


# ── 1) إعادة توجيه / نسخ المنشورات تلقائياً ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تحويل(?:\s+(.+))?$"))
async def forward_add(event):
    """
    .تحويل @المصدر @الهدف
    .تحويل @المصدر @الهدف --نسخ
    بدون --نسخ: إعادة توجيه (يظهر "محوّل من") | مع --نسخ: نسخ كمنشور جديد بدون علامة تحويل
    """
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        await event.edit(
            "❌ **اكتب:** `.تحويل @المصدر @الهدف`\n"
            "للنسخ بدل التوجيه ضيف `--نسخ` في الآخر.\n\n"
            "مثال: `.تحويل @channel1 @channel2`\n"
            "مثال نسخ: `.تحويل @channel1 @channel2 --نسخ`\n\n"
            "`.التحويلات` للعرض | `.ايقاف_تحويل رقم` للحذف"
        )
        return
    copy_mode = "--نسخ" in arg
    arg = arg.replace("--نسخ", "").strip()
    parts = arg.split()
    if len(parts) < 2:
        await event.edit("❌ ناقص شي! الصيغة: `.تحويل @المصدر @الهدف`")
        return
    try:
        src = await get_chat_by_ref(parts[0])
        dst = await get_chat_by_ref(parts[1])
    except Exception as e:
        await event.edit(f"❌ ما قدرت أوصل للقناة/القروب.\n`{e}`")
        return
    fid = str(max([int(k) for k in FORWARDS.keys()], default=0) + 1)
    FORWARDS[fid] = {
        "source_id": src.id, "target_id": dst.id,
        "source": getattr(src, "title", None) or getattr(src, "username", parts[0]),
        "target": getattr(dst, "title", None) or getattr(dst, "username", parts[1]),
        "mode": "copy" if copy_mode else "forward",
    }
    save_json("forwards.json", FORWARDS)
    await event.edit(
        f"✅ **تم تفعيل {'النسخ' if copy_mode else 'إعادة التوجيه'} التلقائي (رقم {fid})**\n\n"
        f"📥 من: {FORWARDS[fid]['source']}\n📤 إلى: {FORWARDS[fid]['target']}\n"
        "أي منشور جديد بالمصدر راح يوصل للهدف تلقائياً."
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.التحويلات$"))
async def forward_list(event):
    if not FORWARDS:
        await event.edit("📭 ما في أي تحويل مفعّل.\nأضف واحد بـ: `.تحويل @المصدر @الهدف`")
        return
    lines = ["📤 **التحويلات المفعّلة:**\n"]
    for fid, f in FORWARDS.items():
        lines.append(f"**#{fid}** — {f['source']} ➜ {f['target']} ({'نسخ 📋' if f['mode'] == 'copy' else 'توجيه ↪️'})")
    lines.append("\n`.ايقاف_تحويل رقم` للحذف")
    await event.edit("\n".join(lines))


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ايقاف_تحويل(?:\s+(\d+))?$"))
async def forward_stop(event):
    fid = event.pattern_match.group(1)
    if not fid or fid not in FORWARDS:
        await event.edit("❌ اكتب رقم التحويل، مثال: `.ايقاف_تحويل 1`")
        return
    del FORWARDS[fid]
    save_json("forwards.json", FORWARDS)
    await event.edit(f"⏹️ تم إيقاف التحويل #{fid}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.نسخ(?:\s+(.+))?$"))
async def copy_posts(event):
    """نسخ آخر منشورات قناة لقناة ثانية دفعة وحدة: .نسخ @المصدر @الهدف 10"""
    arg = (event.pattern_match.group(1) or "").strip()
    parts = arg.split()
    if len(parts) < 2:
        await event.edit("❌ **اكتب:** `.نسخ @المصدر @الهدف [عدد]`\nمثال: `.نسخ @channel1 @channel2 10`")
        return
    try:
        count = int(parts[2]) if len(parts) > 2 else 10
    except ValueError:
        count = 10
    count = max(1, min(count, 50))
    try:
        src = await get_chat_by_ref(parts[0])
        dst = await get_chat_by_ref(parts[1])
    except Exception as e:
        await event.edit(f"❌ ما قدرت أوصل للقناة.\n`{e}`")
        return
    await event.edit(f"📋 جاري نسخ آخر {count} منشور...")
    msgs = [m async for m in client.iter_messages(src, limit=count)]
    msgs.reverse()  # من الأقدم للأحدث عشان الترتيب يضل صح
    done = 0
    for m in msgs:
        try:
            if m.media:
                await client.send_file(dst.id, m.media, caption=m.text or "")
            elif m.text:
                await client.send_message(dst.id, m.text)
            done += 1
            await asyncio.sleep(2)
        except Exception:
            continue
    await event.edit(f"✅ تم نسخ {done} منشور من {getattr(src, 'title', '')} إلى {getattr(dst, 'title', '')}.")


@client.on(events.NewMessage(incoming=True))
async def auto_forward_handler(event):
    """أي منشور جديد في قناة مصدر مفعّلة، بيتوجّه أو بيننسخ للهدف تلقائياً."""
    if not FORWARDS or event.out:
        return
    for f in FORWARDS.values():
        if event.chat_id == f["source_id"]:
            try:
                if f["mode"] == "copy":
                    if event.message.media:
                        await client.send_file(f["target_id"], event.message.media, caption=event.message.text or "")
                    elif event.message.text:
                        await client.send_message(f["target_id"], event.message.text)
                else:
                    await client.forward_messages(f["target_id"], event.message)
            except Exception as e:
                await send_log("❌ فشل التحويل التلقائي", str(e), "غالباً ما عندك صلاحية النشر في القناة الهدف، أو انحذفت القناة المصدر.")


# ── 2) حذف الرسائل تلقائياً ──
async def delete_after(chat_id, msg_id, minutes):
    await asyncio.sleep(minutes * 60)
    try:
        await client.delete_messages(chat_id, msg_id)
    except Exception:
        pass


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حذف_تلقائي(?:\s+(\d+))?$"))
async def autodelete_set(event):
    """داخل القروب: .حذف_تلقائي 10 — كل رسالة جديدة بتنحذف بعد 10 دقائق"""
    minutes = event.pattern_match.group(1)
    if not minutes:
        await event.edit("❌ **اكتب:** `.حذف_تلقائي عدد_الدقائق`\nمثال: `.حذف_تلقائي 10`\nللإيقاف: `.حذف_تلقائي_ايقاف`")
        return
    minutes = int(minutes)
    if minutes < 1 or minutes > 10080:
        await event.edit("⚠️ الدقائق بين 1 و 10080.")
        return
    AUTODELETE[str(event.chat_id)] = minutes
    save_json("autodelete.json", AUTODELETE)
    await event.edit(f"🗑️ **الحذف التلقائي مفعّل في هذا القروب:** كل رسالة جديدة بتنحذف بعد {minutes} دقيقة.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حذف_تلقائي_ايقاف$"))
async def autodelete_stop(event):
    AUTODELETE.pop(str(event.chat_id), None)
    save_json("autodelete.json", AUTODELETE)
    await event.edit("⏹️ تم إيقاف الحذف التلقائي في هذا القروب.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.مسح(?:\s+(\d+))?$"))
async def purge_messages(event):
    """يمسح آخر N رسالة في المحادثة الحالية: .مسح 20"""
    count = int(event.pattern_match.group(1) or 20)
    count = max(1, min(count, 100))
    try:
        msgs = [m async for m in client.iter_messages(event.chat_id, limit=count)]
        await client.delete_messages(event.chat_id, [m.id for m in msgs])
        await event.respond(f"🗑️ تم مسح {len(msgs)} رسالة.")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أمسح — لازم تكون مشرف أو الرسائل قديمة.\n`{e}`")


@client.on(events.NewMessage)
async def autodelete_handler(event):
    if str(event.chat_id) in AUTODELETE:
        asyncio.create_task(delete_after(event.chat_id, event.id, AUTODELETE[str(event.chat_id)]))


# ── 3) تثبيت المنشورات تلقائياً ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تثبيت_تلقائي$"))
async def autopin_toggle(event):
    cid = str(event.chat_id)
    if cid in AUTOPIN:
        AUTOPIN.remove(cid)
        msg = "⏹️ تم إيقاف التثبيت التلقائي في هذا القروب/القناة."
    else:
        AUTOPIN.append(cid)
        msg = "📌 **التثبيت التلقائي مفعّل:** كل منشور جديد راح يتثبت تلقائياً."
    save_json("autopin.json", AUTOPIN)
    await event.edit(msg)


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تثبيت$"))
async def pin_reply(event):
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("❌ رد على الرسالة اللي بدك تثبتها ثم اكتب `.تثبيت`")
        return
    try:
        await client.pin_message(event.chat_id, reply.id, notify=False)
        await event.edit("📌 تم تثبيت الرسالة.")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أثبت — لازم تكون مشرف.\n`{e}`")


@client.on(events.NewMessage)
async def autopin_handler(event):
    if str(event.chat_id) in AUTOPIN and not event.out:
        try:
            await client.pin_message(event.chat_id, event.id, notify=False)
        except Exception:
            pass


# ── 4) الترحيب المخصص ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ترحيب_رسالة(?:\s+(.+))?$"))
async def welcome_custom(event):
    """تحديد رسالة ترحيب خاصة بهذا القروب: .ترحيب_رسالة أهلاً {اسم} نورت {قروب} 🎉"""
    text = (event.pattern_match.group(1) or "").strip()
    if not text:
        current = WELCOME_MSG.get(str(event.chat_id), "👋 أهلاً وسهلاً {اسم} نورت القروب! 🎉")
        await event.edit(f"📝 **رسالة الترحيب الحالية:**\n{current}\n\nغيّرها بـ: `.ترحيب_رسالة أهلاً {{اسم}} نورت {{قروب}}`\nالمتغيرات: {{اسم}} {{قروب}}")
        return
    WELCOME_MSG[str(event.chat_id)] = text
    save_json("welcome.json", WELCOME_MSG)
    await event.edit(f"✅ **تم حفظ رسالة الترحيب لهذا القروب:**\n{text}")


# ── 5) حظر الكلمات والروابط ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.منع_كلمة(?:\s+(.+))?$"))
async def ban_word_add(event):
    word = (event.pattern_match.group(1) or "").strip()
    if not word:
        await event.edit("❌ اكتب: `.منع_كلمة الكلمة`")
        return
    entry = BANNED.setdefault(str(event.chat_id), {"words": [], "links": False})
    if word not in entry["words"]:
        entry["words"].append(word)
    save_json("banned.json", BANNED)
    await event.edit(f"🚫 **تم حظر الكلمة في هذا القروب:** {word}\nأي رسالة فيها هالكلمة راح تنحذف تلقائياً.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.السماح_كلمة(?:\s+(.+))?$"))
async def ban_word_remove(event):
    word = (event.pattern_match.group(1) or "").strip()
    entry = BANNED.get(str(event.chat_id), {"words": [], "links": False})
    if word in entry.get("words", []):
        entry["words"].remove(word)
        save_json("banned.json", BANNED)
        await event.edit(f"✅ تم السماح بالكلمة: {word}")
    else:
        await event.edit("❌ هالكلمة مو محظورة أصلاً.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.الكلمات$"))
async def ban_word_list(event):
    entry = BANNED.get(str(event.chat_id), {"words": [], "links": False})
    words = entry.get("words", [])
    await event.edit(
        "🚫 **الكلمات الممنوعة في هذا القروب:**\n"
        + ("\n".join(f"• {w}" for w in words) if words else "ما في كلمات ممنوعة.")
        + f"\n\n🔗 منع الروابط: {'مفعّل ✅' if entry.get('links') else 'متوقف ⏹️'} — بدّلها بـ `.منع_روابط`"
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.منع_روابط$"))
async def ban_links_toggle(event):
    entry = BANNED.setdefault(str(event.chat_id), {"words": [], "links": False})
    entry["links"] = not entry.get("links", False)
    save_json("banned.json", BANNED)
    await event.edit(f"🔗 **منع الروابط في هذا القروب:** {'مفعّل ✅' if entry['links'] else 'متوقف ⏹️'}")


@client.on(events.NewMessage(incoming=True))
async def banned_filter_handler(event):
    """يحذف أي رسالة فيها كلمة ممنوعة أو رابط ممنوع (إذا المرسل مو مشرف)."""
    if event.out:
        return
    entry = BANNED.get(str(event.chat_id))
    if not entry:
        return
    text = (event.text or "").lower()
    try:
        perms = await client.get_permissions(event.chat_id, event.sender_id)
        if perms.is_admin or perms.is_creator:
            return
    except Exception:
        pass
    should_delete = False
    reason = ""
    for w in entry.get("words", []):
        if w.lower() in text:
            should_delete, reason = True, f"كلمة ممنوعة: {w}"
            break
    if not should_delete and entry.get("links") and re.search(r"(https?://|t\.me/|www\.)", text):
        should_delete, reason = True, "رابط ممنوع"
    if should_delete:
        try:
            await event.delete()
            sender = await event.get_sender()
            await client.send_message(event.chat_id, f"🚫 تم حذف رسالة من {getattr(sender, 'first_name', '')} — {reason}.")
            await asyncio.sleep(5)
            # نحذف رسالة التحذير نفسها بعد 5 ثواني عشان ما تزعج
            async for m in client.iter_messages(event.chat_id, limit=1):
                if "تم حذف رسالة" in (m.text or ""):
                    await m.delete()
                    break
        except Exception:
            pass


# ── 6) تنظيف الأعضاء غير النشطين ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تنظيف(?:\s+(\d+))?$"))
async def clean_scan(event):
    """يفحص الأعضاء غير النشطين: .تنظيف 30 — يعني ما أرسلوا شي آخر 30 يوم"""
    days = int(event.pattern_match.group(1) or 30)
    await event.edit(f"🔍 جاري فحص الأعضاء غير النشطين آخر {days} يوم... (ممكن ياخذ شوي)")
    try:
        chat = await event.get_chat()
        # الأعضاء النشطين = اللي أرسلوا رسائل آخر X يوم (نفحص آخر 1000 رسالة)
        active = set()
        cutoff = time.time() - days * 86400
        async for m in client.iter_messages(event.chat_id, limit=1000):
            if m.date and m.date.timestamp() < cutoff:
                break
            if m.sender_id:
                active.add(m.sender_id)
        inactive = []
        async for user in client.iter_participants(event.chat_id):
            if user.bot or user.deleted or user.is_self:
                continue
            if user.id not in active:
                inactive.append(user)
        CLEAN_PENDING[event.chat_id] = [u.id for u in inactive]
        names = "\n".join(f"• {u.first_name} (@{getattr(u, 'username', '') or '—'})" for u in inactive[:20])
        await event.edit(
            f"🧹 **الأعضاء غير النشطين آخر {days} يوم: {len(inactive)}**\n\n"
            f"{names or 'ما في أعضاء غير نشطين 🎉'}\n"
            + (f"\n...و {len(inactive) - 20} غيرهم" if len(inactive) > 20 else "")
            + "\n\n⚠️ **للطرد اكتب:** `.تنظيف_تأكيد`\n"
            "ملاحظة: الفحص مبني على آخر 1000 رسالة، والمشرفين والبوتات ما بينطردوا."
        )
    except Exception as e:
        await event.edit(f"❌ ما قدرت أفحص الأعضاء.\n`{e}`")
        await send_log("❌ فشل فحص تنظيف الأعضاء", str(e), "غالباً ما عندك صلاحية عرض الأعضاء، أو القروب كبير جداً.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تنظيف_تأكيد$"))
async def clean_confirm(event):
    ids = CLEAN_PENDING.get(event.chat_id, [])
    if not ids:
        await event.edit("❌ ما في فحص تنظيف جاهز. اكتب أولاً `.تنظيف 30`")
        return
    if len(ids) > 50:
        ids = ids[:50]
        await event.edit("⚠️ قللت العدد لـ 50 عضو كحد آمن للتنظيف الواحد.")
    await event.edit(f"🧹 جاري طرد {len(ids)} عضو غير نشط... (بتأخير 5 ثواني بين كل واحد)")
    done = failed = 0
    for uid in ids:
        try:
            await client.kick_participant(event.chat_id, uid)
            done += 1
        except FloodWaitError as e:
            await send_log("⏳ فلوود أثناء التنظيف", str(e), "طردت أعضاء بسرعة أكثر مما يسمح تيليجرام — توقف التنظيف لحماية حسابك.")
            break
        except Exception:
            failed += 1
        await asyncio.sleep(5)
    CLEAN_PENDING[event.chat_id] = []
    await event.edit(f"✅ **اكتمل التنظيف:**\n👢 تم طرد: {done}\n❌ فشل: {failed}")
    await send_log("🧹 تنظيف أعضاء غير نشطين", f"القروب: {event.chat_id} — طرد {done}، فشل {failed}", "")


# ── إضافات تزبط معها: قفل/فتح القروب + إحصائيات ──
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.قفل$"))
async def lock_group(event):
    """يقفل القروب: بس المشرفين يقدروا يرسلوا. .فتح للفك."""
    try:
        await client(EditBannedRequest(event.chat_id, 0, ChatBannedRights(until_date=None, send_messages=True)))
        await event.edit("🔒 **تم قفل القروب** — بس المشرفين يقدروا يرسلوا.")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أقفل — لازم تكون مشرف.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.فتح$"))
async def unlock_group(event):
    try:
        await client(EditBannedRequest(event.chat_id, 0, ChatBannedRights(until_date=None, send_messages=False)))
        await event.edit("🔓 **تم فتح القروب** — الكل يقدر يرسل.")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أفتح.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.احصائيات$"))
async def group_stats(event):
    try:
        chat = await event.get_chat()
        count = 0
        async for _ in client.iter_participants(event.chat_id, limit=10000):
            count += 1
        await event.edit(
            f"📊 **إحصائيات {getattr(chat, 'title', '')}:**\n\n"
            f"👥 الأعضاء: {count}\n"
            f"📤 تحويلات مفعّلة: {len(FORWARDS)}\n"
            f"📢 جداول نشر: {len(SCHEDULES)}\n"
            f"🗑️ حذف تلقائي: {AUTODELETE.get(str(event.chat_id), 'متوقف')}\n"
            f"📌 تثبيت تلقائي: {'مفعّل' if str(event.chat_id) in AUTOPIN else 'متوقف'}\n"
            f"🚫 كلمات ممنوعة: {len(BANNED.get(str(event.chat_id), {}).get('words', []))}"
        )
    except Exception as e:
        await event.edit(f"❌ ما قدرت أجيب الإحصائيات.\n`{e}`")


# ───────────────────────── أوامر متطورة ─────────────────────────
def http_get_json(url, timeout=15):
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.json()


def http_get_text(url, timeout=15):
    import requests
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text.strip()


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ترجمة(?:\s+(\w+)\s+(.+))?$"))
async def translate_cmd(event):
    """ترجمة نص: .ترجمة en مرحبا  أو  .ترجمة ar Hello"""
    lang = event.pattern_match.group(1)
    text = (event.pattern_match.group(2) or "").strip()
    if not lang or not text:
        await event.edit("❌ **اكتب:** `.ترجمة اللغة النص`\nمثال: `.ترجمة en مرحبا كيف حالك`\nمثال: `.ترجمة ar Hello how are you`")
        return
    await event.edit("🌐 جاري الترجمة...")
    try:
        import urllib.parse
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=" + lang + "&dt=t&q=" + urllib.parse.quote(text)
        data = await asyncio.to_thread(http_get_json, url)
        translated = "".join(part[0] for part in data[0] if part[0])
        await event.edit(f"🌐 **الترجمة ({lang}):**\n\n{translated}\n\nالأصل: {text}")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أترجم.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.طقس(?:\s+(.+))?$"))
async def weather_cmd(event):
    """طقس مدينة: .طقس لندن"""
    city = (event.pattern_match.group(1) or "").strip() or "London"
    await event.edit(f"🌤️ جاري جلب طقس {city} ...")
    try:
        import urllib.parse
        data = await asyncio.to_thread(http_get_json, "https://wttr.in/" + urllib.parse.quote(city) + "?format=j1")
        cur = data["current_condition"][0]
        area = data["nearest_area"][0]["areaName"][0]["value"]
        await event.edit(
            f"🌤️ **طقس {area}:**\n\n"
            f"🌡️ الحرارة: {cur['temp_C']}°C (يحس بها {cur['FeelsLikeC']}°C)\n"
            f"☁️ الحالة: {cur['weatherDesc'][0]['value']}\n"
            f"💧 الرطوبة: {cur['humidity']}%\n"
            f"💨 الرياح: {cur['windspeedKmph']} كم/س\n"
            f"👁️ الرؤية: {cur['visibility']} كم"
        )
    except Exception as e:
        await event.edit(f"❌ ما قدرت أجيب الطقس.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.اختصار(?:\s+(.+))?$"))
async def shorten_cmd(event):
    """اختصار رابط: .اختصار https://example.com"""
    url = (event.pattern_match.group(1) or "").strip()
    if not url:
        await event.edit("❌ اكتب: `.اختصار الرابط`")
        return
    try:
        import urllib.parse
        short = await asyncio.to_thread(http_get_text, "https://is.gd/create.php?format=simple&url=" + urllib.parse.quote(url))
        await event.edit(f"🔗 **الرابط المختصر:**\n{short}\n\nالأصلي: {url}")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أختصر الرابط.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.qr(?:\s+(.+))?$"))
async def qr_cmd(event):
    """يعمل QR لأي نص أو رابط: .qr https://t.me/subaru_surce"""
    text = (event.pattern_match.group(1) or "").strip()
    if not text:
        await event.edit("❌ اكتب: `.qr النص أو الرابط`")
        return
    try:
        import qrcode
        path = os.path.join(DOWNLOAD_DIR, "qr.png")
        img = qrcode.make(text)
        img.save(path)
        await event.delete()
        await client.send_file(event.chat_id, path, caption=f"🔳 **QR لـ:**\n`{text}`")
        os.remove(path)
    except Exception as e:
        await event.edit(f"❌ ما قدرت أعمل QR — تأكد أن مكتبة qrcode مثبّتة.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تشفير(?:\s+(.+))?$"))
async def encode_cmd(event):
    import base64
    text = (event.pattern_match.group(1) or "").strip()
    if not text:
        await event.edit("❌ اكتب: `.تشفير النص`")
        return
    enc = base64.b64encode(text.encode()).decode()
    await event.edit(f"🔐 **النص المشفّر:**\n`{enc}`\n\nلفك التشفير: `.فك_تشفير {enc}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.فك_تشفير(?:\s+(.+))?$"))
async def decode_cmd(event):
    import base64
    code = (event.pattern_match.group(1) or "").strip()
    if not code:
        await event.edit("❌ اكتب: `.فك_تشفير الكود`")
        return
    try:
        dec = base64.b64decode(code).decode()
        await event.edit(f"🔓 **النص الأصلي:**\n{dec}")
    except Exception:
        await event.edit("❌ الكود مو صحيح.")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.كلمة_سر(?:\s+(\d+))?$"))
async def password_cmd(event):
    import secrets, string
    length = int(event.pattern_match.group(1) or 12)
    length = max(6, min(length, 32))
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = "".join(secrets.choice(alphabet) for _ in range(length))
    await event.edit(f"🔑 **كلمة سر قوية ({length} حرف):**\n`{pwd}`\n\n⚠️ احذف الرسالة بعد ما تنسخها!")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.المشرفين$"))
async def admins_cmd(event):
    try:
        admins = []
        async for user in client.iter_participants(event.chat_id, filter=None):
            try:
                perms = await client.get_permissions(event.chat_id, user.id)
                if perms.is_admin or perms.is_creator:
                    admins.append(f"• {user.first_name} (@{getattr(user, 'username', '') or '—'}) {'👑' if perms.is_creator else '🛡️'}")
            except Exception:
                continue
        await event.edit("👑 **مشرفين القروب:**\n\n" + ("\n".join(admins) if admins else "ما في مشرفين ظاهرين."))
    except Exception as e:
        await event.edit(f"❌ ما قدرت أجيب المشرفين.\n`{e}`")


# ───────────────────────── تسلية جماعية ─────────────────────────
POINTS_FILE = "points.json"
POINTS = load_json(POINTS_FILE, {})
GUESS_GAME = {}  # chat_id -> {"number": int, "tries": int}
POLLS = {}       # poll_id -> {"question": str, "options": [...], "votes": {idx: set(user_id)}, "voters": {}}

PUNISHMENTS = [
    "😂 الحكم: غيّر اسمك في القروب لـ «أنا بطاطا» لمدة ساعة!",
    "🎤 الحكم: غنّي أي أغنية بصوتك وأرسلها فويس!",
    "📸 الحكم: أرسل آخر صورة في معرض صورك!",
    "🤣 الحكم: اضحك ضحكة شريرة بصوت عالي وأرسلها فويس!",
    "✍️ الحكم: اكتب «أنا أحب سوبارو» 10 مرات!",
    "🕺 الحكم: صوّر نفسك وأنت ترقص 10 ثواني!",
    "😜 الحكم: تكلّم بلهجة مختلفة لمدة 5 دقائق!",
    "📱 الحكم: خلّي صورة بروفايلك صورة قط لمدة يوم!",
    "🍕 الحكم: اطلب أكل للشخص اللي فوقك بالتعليقات!",
    "😴 الحكم: اكتب رسالة وأنت نعسان كأنك راح تنام!",
    "🎭 الحكم: قلّد شخصية أنمي تحبها!",
    "💬 الحكم: أرسل رسالة لأول شخص في جهات اتصالك تقول له «أحبك»!",
    "🧠 الحكم: احفظ بيت شعر واكتبه هون!",
    "😎 الحكم: لا تتكلم إلا بالإيموجي لمدة 10 دقائق!",
    "🏃 الحكم: اعمل 20 تمرين ضغط وصوّر نفسك!",
    "🎵 الحكم: اكتب كلمات أغنية تحبها كاملة!",
    "👑 الحكم: أنت خادم القروب اليوم، نفّذ أي طلب من الأعضاء!",
    "🤐 الحكم: اسكت 10 دقائق كاملة بدون ما تكتب شي!",
    "📞 الحكم: اتصل بأول رقم في هاتفك وقل له «صباح الخير»!",
    "🌶️ الحكم: كُل شي حار وصوّر ردة فعلك!",
]

DARES = [
    "🔥 التحدي: اكتب اسم أول حب في حياتك!",
    "😈 التحدي: اعترف بأغرب شي عملته بحياتك!",
    "🎯 التحدي: تحدّى شخص في القروب بلعبة حجر ورقة مقص!",
    "🎤 التحدي: غنّي مقطع من أغنية تحبها!",
    "😂 التحدي: احكي نكتة، وإذا ما حدا ضحك عليك حكم!",
    "📸 التحدي: أرسل صورة سيلفي مضحكة!",
    "🧠 التحدي: حل هاللغز: شي كل ما أخذت منه يكبر، ما هو؟",
    "💪 التحدي: اعمل 10 تمرين ضغط الآن!",
    "🎲 التحدي: ارمي النرد بـ .نرد ، وإذا طلع أقل من 3 عليك حكم!",
    "❤️ التحدي: قول لشخص في القروب أنك تحبه!",
    "👻 التحدي: احكي قصة رعب قصيرة!",
    "🎬 التحدي: مثّل مشهد من فيلم تحبه بالكتابة!",
]

TRUTHS = [
    "🤔 صراحة: ما هو أكبر سر تخفيه عن أصدقائك؟",
    "🤔 صراحة: من هو الشخص اللي ما تقدر تعيش بدونه؟",
    "🤔 صراحة: شو أكثر موقف محرج صار معك؟",
    "🤔 صراحة: لو تقدر ترجع بالزمن، شو بتغير؟",
    "🤔 صراحة: من هو قدوتك وليش؟",
    "🤔 صراحة: شو هو حلمك اللي لسا ما حققته؟",
]


def get_points(chat_id, user_id):
    return POINTS.get(str(chat_id), {}).get(str(user_id), 100)


def set_points(chat_id, user_id, value):
    POINTS.setdefault(str(chat_id), {})[str(user_id)] = max(0, value)
    save_json(POINTS_FILE, POINTS)


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.احكام$"))
async def punish_cmd(event):
    reply = await event.get_reply_message()
    target = ""
    if reply:
        target = f" {reply.sender.first_name}"
    await event.edit(f"⚖️ **حكم على{target}:**\n\n{random.choice(PUNISHMENTS)}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.عقاب$"))
async def punish2_cmd(event):
    reply = await event.get_reply_message()
    target = ""
    if reply:
        target = f" {reply.sender.first_name}"
    await event.edit(f"😈 **عقاب لـ{target}:**\n\n{random.choice(PUNISHMENTS)}\n\nوإذا ما نفّذه خلال 5 دقائق، الحكم بيصير مضاعف! 😂")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تحدي$"))
async def dare_cmd(event):
    await event.edit(f"🔥 **تحدي جماعي:**\n\n{random.choice(DARES)}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حقيقة_او_جرأة$"))
async def truth_dare_cmd(event):
    if random.random() < 0.5:
        await event.edit(f"🎲 **طلع لك: حقيقة!**\n\n{random.choice(TRUTHS)}")
    else:
        await event.edit(f"🎲 **طلع لك: جرأة!**\n\n{random.choice(DARES)}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.نرد$"))
async def dice_cmd(event):
    roll = random.randint(1, 6)
    if roll == 6:
        set_points(event.chat_id, event.sender_id, get_points(event.chat_id, event.sender_id) + 20)
        await event.edit(f"🎲 **النرد طلع:** 6 🎉\nربحت 20 نقطة! 💰 (نقاطك: {get_points(event.chat_id, event.sender_id)})")
    else:
        await event.edit(f"🎲 **النرد طلع:** {roll}")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حرب$"))
async def battle_cmd(event):
    reply = await event.get_reply_message()
    me = await client.get_me()
    p1 = me.first_name
    p2 = reply.sender.first_name if reply else "الخصم الوهمي 👻"
    hp1, hp2 = 100, 100
    log = [f"⚔️ **معركة بين {p1} و {p2}!**\n"]
    while hp1 > 0 and hp2 > 0:
        d1, d2 = random.randint(5, 25), random.randint(5, 25)
        hp2 -= d1
        hp1 -= d2
        log.append(f"💥 {p1} ضرب {d1} | {p2} ضرب {d2} — ❤️ {max(hp1,0)} vs {max(hp2,0)}")
    winner = p1 if hp1 > hp2 else p2
    log.append(f"\n🏆 **الفائز: {winner}!**")
    await event.edit("\n".join(log))


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.نقاطي$"))
async def my_points(event):
    pts = get_points(event.chat_id, event.sender_id)
    await event.edit(f"💰 **نقاطك في هذا القروب:** {pts} نقطة\n\nاجمع نقاط بـ .نرد (إذا طلع 6 بتاخذ 20 نقطة) أو اسرق من غيرك بـ .سرقة")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.سرقة$"))
async def steal_cmd(event):
    reply = await event.get_reply_message()
    if not reply:
        await event.edit("❌ رد على رسالة الشخص اللي بدك تسرق منه ثم اكتب `.سرقة`")
        return
    victim = reply.sender_id
    if victim == event.sender_id:
        await event.edit("😂 ما تقدر تسرق من نفسك!")
        return
    stolen = random.randint(10, 50)
    victim_pts = get_points(event.chat_id, victim)
    stolen = min(stolen, victim_pts)
    set_points(event.chat_id, victim, victim_pts - stolen)
    set_points(event.chat_id, event.sender_id, get_points(event.chat_id, event.sender_id) + stolen)
    if random.random() < 0.3:
        fine = 30
        set_points(event.chat_id, event.sender_id, get_points(event.chat_id, event.sender_id) - fine)
        await event.edit(f"🚨 **انكشفت سرقتك!** ودفعت غرامة {fine} نقطة 😂")
    else:
        await event.edit(f"🦹 **سرقة ناجحة!** سرقت {stolen} نقطة من {reply.sender.first_name}! 💰")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.لعبة_رقم$"))
async def guess_start(event):
    GUESS_GAME[event.chat_id] = {"number": random.randint(1, 20), "tries": 0}
    await event.edit("🎯 **لعبة خمّن الرقم بدأت!**\nفكّرت برقم بين 1 و 20...\nخمّن بـ: `.خمن رقم`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.خمن(?:\s+(\d+))?$"))
async def guess_cmd(event):
    game = GUESS_GAME.get(event.chat_id)
    if not game:
        await event.edit("❌ ما في لعبة شغالة. ابدأ وحدة بـ `.لعبة_رقم`")
        return
    guess = event.pattern_match.group(1)
    if not guess:
        await event.edit("❌ اكتب: `.خمن رقم`")
        return
    guess = int(guess)
    game["tries"] += 1
    if guess == game["number"]:
        set_points(event.chat_id, event.sender_id, get_points(event.chat_id, event.sender_id) + 50)
        await event.edit(f"🎉 **صح! الرقم كان {game['number']}!**\nخمّنته بـ {game['tries']} محاولة، وربحت 50 نقطة! 💰")
        del GUESS_GAME[event.chat_id]
    elif guess < game["number"]:
        await event.edit(f"📈 الرقم أكبر من {guess} — جرّب مرة ثانية!")
    else:
        await event.edit(f"📉 الرقم أصغر من {guess} — جرّب مرة ثانية!")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.قرعة(?:\s+(.+))?$"))
async def lottery_cmd(event):
    arg = (event.pattern_match.group(1) or "").strip()
    if arg:
        items = [i.strip() for i in arg.split("|") if i.strip()]
        await event.edit(f"🎰 **القرعة اختارت:** {random.choice(items)}")
        return
    try:
        members = [u async for u in client.iter_participants(event.chat_id, limit=100) if not u.bot and not u.deleted]
        winner = random.choice(members)
        await event.edit(f"🎰 **الفائز بالقرعة:** {winner.first_name} (@{getattr(winner, 'username', '') or '—'}) 🎉")
    except Exception as e:
        await event.edit(f"❌ ما قدرت أعمل قرعة.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.الاكثر(?:\s+(.+))?$"))
async def most_cmd(event):
    trait = (event.pattern_match.group(1) or "").strip() or "ضحكاً"
    try:
        members = [u async for u in client.iter_participants(event.chat_id, limit=100) if not u.bot and not u.deleted]
        winner = random.choice(members)
        await event.edit(f"😂 **من الأكثر {trait} في القروب؟**\n\n👉 {winner.first_name} (@{getattr(winner, 'username', '') or '—'})")
    except Exception as e:
        await event.edit(f"❌ ما قدرت.\n`{e}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تصويت(?:\s+(.+))?$"))
async def poll_cmd(event):
    """تصويت بأزرار: .تصويت سؤال | خيار1 | خيار2 | خيار3"""
    arg = (event.pattern_match.group(1) or "").strip()
    if not arg:
        await event.edit("❌ **اكتب:** `.تصويت سؤال | خيار1 | خيار2`\nمثال: `.تصويت شو أحلى أنمي؟ | ري زيرو | ناروتو | ون بيس`")
        return
    parts = [p.strip() for p in arg.split("|") if p.strip()]
    if len(parts) < 3:
        await event.edit("❌ لازم سؤال وخيارين على الأقل، مفصولين بـ `|`")
        return
    question, options = parts[0], parts[1:5]
    pid = str(random.randint(100000, 999999))
    POLLS[pid] = {"question": question, "options": options, "votes": {i: set() for i in range(len(options))}, "voters": {}}
    buttons = [[Button.inline(f"{opt}", data=f"vote:{pid}:{i}".encode())] for i, opt in enumerate(options)]
    try:
        await event.delete()
    except Exception:
        pass
    await client.send_message(event.chat_id, f"📊 **تصويت:** {question}\n\n" + "\n".join(f"{i+1}. {opt} — 0 صوت" for i, opt in enumerate(options)) + "\n\nاضغط زر للتصويت 👇", buttons=buttons)


@client.on(events.CallbackQuery)
async def poll_vote_callback(event):
    data = event.data.decode(errors="ignore")
    if not data.startswith("vote:"):
        return
    _, pid, idx = data.split(":")
    idx = int(idx)
    poll = POLLS.get(pid)
    if not poll:
        await event.answer("التصويت خلص.", alert=True)
        return
    voter = event.sender_id
    # صوت واحد لكل شخص: نشيل صوته القديم
    for s in poll["votes"].values():
        s.discard(voter)
    poll["votes"][idx].add(voter)
    lines = [f"📊 **تصويت:** {poll['question']}\n"]
    total = sum(len(s) for s in poll["votes"].values())
    for i, opt in enumerate(poll["options"]):
        lines.append(f"{i+1}. {opt} — {len(poll['votes'][i])} صوت")
    lines.append(f"\n🗳️ المجموع: {total} صوت")
    buttons = [[Button.inline(f"{opt}", data=f"vote:{pid}:{i}".encode())] for i, opt in enumerate(poll["options"])]
    await event.edit("\n".join(lines), buttons=buttons)
    await event.answer("✅ تم تسجيل صوتك!")


# ───────────────────────── ضحك ولايك وحلوات متحركة ─────────────────────────
LAUGH_FRAMES = [
    "😂",
    "😂🤣",
    "🤣😂🤣",
    "😹😂🤣😹",
    "🤣😂🤣😂🤣",
    "😂😂😂😂😂",
    "🤣🤣🤣🤣🤣🤣",
    "😹😹😹😹😹😹😹",
    "😂🤣😹😂🤣😹",
    "🤣😂🤣😂🤣😂🤣",
    "😆😂🤣😹😆",
    "😂😂😂😂😂😂😂😂",
    "🤣🤣🤣🤣🤣🤣🤣🤣",
    "😹😂🤣😹😂🤣😹😂",
    "😂🤣😂🤣😂🤣😂🤣😂",
    "🤣😂🤣😂🤣😂🤣😂🤣😂",
]

LIKE_FRAMES = [
    "👍",
    "👍❤️",
    "❤️👍🔥",
    "🔥❤️👍💯",
    "💯🔥❤️👍😍",
    "😍💯🔥❤️👍",
    "👍❤️🔥💯😍✨",
    "✨😍💯🔥❤️👍",
    "❤️❤️❤️❤️❤️",
    "👍👍👍👍👍",
    "🔥🔥🔥🔥🔥",
    "💯💯💯💯💯",
]

CUTE_FRAMES = [
    "🥰",
    "🥰😍",
    "😍🥰✨",
    "✨😍🥰💖",
    "💖✨😍🥰🌸",
    "🌸💖✨😍🥰",
    "🥰😍💖✨🌸💕",
    "💕🌸💖✨😍🥰",
    "😍😍😍😍😍",
    "🥰🥰🥰🥰🥰",
    "💖💖💖💖💖",
    "🌸🌸🌸🌸🌸",
]

SWEETS_FRAMES = [
    "🍰",
    "🍰🍩",
    "🍩🍰🍪",
    "🍪🍩🍰🍫",
    "🍫🍪🍩🍰🍬",
    "🍬🍫🍪🍩🍰🧁",
    "🧁🍬🍫🍪🍩🍰",
    "🍰🍩🍪🍫🍬🧁🍭",
    "🍭🧁🍬🍫🍪🍩🍰",
    "🍰🍰🍰🍰🍰",
    "🍩🍩🍩🍩🍩",
    "🍪🍪🍪🍪🍪",
    "🍫🍫🍫🍫🍫",
    "🍬🍬🍬🍬🍬",
    "🧁🧁🧁🧁🧁",
    "🍰🍩🍪🍫🍬🧁🍭🍮",
]


async def play_animation(event, frames, final_text, delay=0.4):
    """يشغل أنيميشن: رسالة بتتعدل كل شوي بسرعة، وبالآخر بتثبت على النص النهائي."""
    try:
        await event.edit(frames[0])
    except Exception:
        return
    for frame in frames[1:]:
        await asyncio.sleep(delay)
        try:
            await event.edit(frame)
        except Exception:
            return
    await asyncio.sleep(delay)
    try:
        await event.edit(final_text)
    except Exception:
        pass


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ضحك$"))
async def laugh_anim(event):
    """ضحك متحرك: مجموعة ضحكات بتتغير بسرعة كل 0.4 ثانية."""
    await play_animation(
        event, LAUGH_FRAMES,
        "😂🤣😹 **ههههههههههههههههههه!**\n\nضحكت؟ 😂",
        delay=0.4,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ضحك_سريع$"))
async def laugh_fast(event):
    """ضحك أسرع: بتتغير كل 0.2 ثانية."""
    await play_animation(
        event, LAUGH_FRAMES,
        "😂🤣😹 **ههههههههههههههههههه!**",
        delay=0.2,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.لايك$"))
async def like_anim(event):
    """لايك متحرك: 👍❤️🔥💯 بتتغير بسرعة."""
    await play_animation(
        event, LIKE_FRAMES,
        "👍❤️🔥💯 **لايك!**\n\nأحلى لايك إلك 😍",
        delay=0.4,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حلو$"))
async def cute_anim(event):
    """حلوات متحركة: 🥰😍✨💖 بتتغير بسرعة."""
    await play_animation(
        event, CUTE_FRAMES,
        "🥰😍💖✨ **حلووووو!**\n\nأنت أحلى واحد هون 🌸",
        delay=0.4,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حلويات$"))
async def sweets_anim(event):
    """حلويات متحركة: 🍰🍩🍪🍫🍬🧁 بتتغير بسرعة."""
    await play_animation(
        event, SWEETS_FRAMES,
        "🍰🍩🍪🍫🍬🧁🍭 **حلويات!**\n\nخذ لك حلوة، أنت أحلى من الحلو 😋",
        delay=0.4,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.حلوة$"))
async def sweet_one(event):
    """حلوة وحدة — رسالة حلوة وحدة سريعة."""
    await event.edit("🍰 **خذ هالحلوة إلك!** 😋\nأنت أحلى من الحلو 🥰")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ضحكات$"))
async def laugh_set(event):
    """مجموعة ضحكات دفعة وحدة — بدون أنيميشن، كلها برسالة وحدة."""
    await event.edit(
        "😂🤣😹😆😄😁\n"
        "🤣😂😹😆😄😁\n"
        "😹🤣😂😆😄😁\n\n"
        "هههههههههههههه! 😂"
    )


# ───────────────────────── انتحال / إرجاع ─────────────────────────
CLONE_FILE = "clone_backup.json"
CLONE_PHOTO = os.path.join(DOWNLOAD_DIR, "clone_photo.jpg")
BACKUP_PHOTO = os.path.join(DOWNLOAD_DIR, "backup_photo.jpg")

CLOSE_BIOS = [
    "✨ {name}",
    "🌟 {name} | حياة حلوة",
    "💫 {name} ✨",
    "😎 {name} — عايش حياتي",
    "🌙 {name} | ليل وهدوء",
    "🔥 {name} | طموح بلا حدود",
]


async def save_my_backup():
    """يحفظ اسمك وبايوك ويوزرك وصورتك الحالية قبل الانتحال (مرة وحدة بس)."""
    if os.path.exists(CLONE_FILE):
        return load_json(CLONE_FILE, None)
    me = await client.get_me()
    # نحمّل صورتك الحالية كنسخة احتياطية
    photo_path = None
    try:
        downloaded = await client.download_profile_photo(me, file=BACKUP_PHOTO)
        if downloaded:
            photo_path = BACKUP_PHOTO
    except Exception:
        pass
    backup = {
        "first_name": me.first_name or "",
        "last_name": me.last_name or "",
        "about": "",
        "username": me.username or "",
        "photo": photo_path,
    }
    try:
        full = await client.get_entity(me.id)
        backup["about"] = getattr(full, "about", "") or ""
    except Exception:
        pass
    # البايو الكامل بيجي من GetFullUser
    try:
        from telethon.tl.functions.users import GetFullUserRequest
        full_user = await client(GetFullUserRequest(me.id))
        backup["about"] = getattr(full_user.full_user, "about", "") or ""
    except Exception:
        pass
    save_json(CLONE_FILE, backup)
    return backup


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.انتحال(?:\s+(.+))?$"))
async def clone_cmd(event):
    """
    انتحال شخص: .انتحال بالرد على رسالته، أو .انتحال @يوزره
    بينسخ صورته واسمه والبايو تبعه لحسابك.
    ملاحظة: اليوزر (@username) ما بيتغير إذا كان محجوز من الشخص نفسه — تيليجرام ما بيسمح بيوزر مكرر.
    """
    arg = (event.pattern_match.group(1) or "").strip()
    reply = await event.get_reply_message()
    target = None
    if reply:
        target = await reply.get_sender()
    elif arg:
        try:
            target = await client.get_entity(arg)
        except Exception as e:
            await event.edit(f"❌ ما لقيت هالشخص: `{arg}`\n`{e}`")
            return
    else:
        await event.edit("❌ **اكتب:** `.انتحال` بالرد على رسالة الشخص، أو `.انتحال @يوزره`")
        return

    await event.edit(f"🎭 جاري انتحال {target.first_name} ...")
    backup = await save_my_backup()

    # البايو: بايو الشخص نفسه إذا موجود، وإذا مو موجود نختار بايو قريب منه
    target_about = ""
    try:
        from telethon.tl.functions.users import GetFullUserRequest
        full_target = await client(GetFullUserRequest(target.id))
        target_about = getattr(full_target.full_user, "about", "") or ""
    except Exception:
        target_about = ""
    if not target_about:
        target_about = random.choice(CLOSE_BIOS).format(name=target.first_name or "")

    # الاسم والبايو
    try:
        await client(UpdateProfileRequest(
            first_name=target.first_name or " ",
            last_name=target.last_name or "",
            about=target_about,
        ))
    except Exception as e:
        await event.edit(f"❌ ما قدرت أغيّر الاسم/البايو.\n`{e}`")
        return

    # الصورة: نحمّل صورته ونحطها صورة لحسابك
    # (نحمّلها كـ bytes مباشرة — التحميل لملف كان يفشل بصمت أحياناً
    #  إذا كان الملف قديم أو الصورة من رد بدون بيانات كاملة)
    photo_ok = False
    photo_error = ""
    clone_photo_id = None
    try:
        # نمسح أي صورة انتحال قديمة عشان ما تنرفع بالغلط
        try:
            os.remove(CLONE_PHOTO)
        except Exception:
            pass
        photo_bytes = await client.download_profile_photo(target, file=bytes)
        if not photo_bytes:
            # جرّب نجيب بياناته الكاملة أولاً ثم نحمّل الصورة منها
            try:
                from telethon.tl.functions.users import GetFullUserRequest
                full_again = await client(GetFullUserRequest(target.id))
                photo_bytes = await client.download_profile_photo(
                    full_again.users[0] if getattr(full_again, "users", None) else target,
                    file=bytes,
                )
            except Exception:
                photo_bytes = None
        if photo_bytes:
            # نحفظها كملف كمان (عشان .ارجاع يقدر يحذفها) ونرفعها
            with open(CLONE_PHOTO, "wb") as _f:
                _f.write(photo_bytes)
            uploaded = await client.upload_file(photo_bytes)
            result = await client(UploadProfilePhotoRequest(file=uploaded))
            photo_ok = True
            # نحفظ آيدي الصورة الجديدة عشان نحذفها عند الإرجاع
            try:
                clone_photo_id = result.photo.id
            except Exception:
                pass
            # تأكيد: هل صارت الصورة فعلاً صورة حسابك الحالية؟
            try:
                me_after = await client.get_me()
                if not getattr(me_after, "photo", None):
                    photo_ok = False
                    photo_error = "الرفع تم بس الصورة ما ظهرت كصورة حسابك"
            except Exception:
                pass
        else:
            photo_error = "ما عنده صورة ظاهرة لك (ممكن مخفيها بإعدادات الخصوصية)"
    except Exception as e:
        photo_error = str(e)
        print(f"⚠️ ما قدرت أنسخ الصورة: {e}")

    if clone_photo_id:
        backup["clone_photo_id"] = clone_photo_id
        save_json(CLONE_FILE, backup)

    # اليوزر: نحاول نغيّره ليوزره — غالباً بيفشل لأنه محجوز منه، وهذا طبيعي
    username_note = ""
    target_username = getattr(target, "username", None)
    if target_username:
        try:
            await client(UpdateUsernameRequest(target_username))
            username_note = f"\n🆔 اليوزر صار: @{target_username}"
        except Exception:
            username_note = "\n🆔 اليوزر ما تغيّر (محجوز من الشخص نفسه — تيليجرام ما بيسمح بيوزر مكرر)."

    await event.edit(
        f"🎭 **تم الانتحال!**\n\n"
        f"👤 الاسم صار: {target.first_name} {target.last_name or ''}\n"
        f"📝 البايو صار: {target_about}\n"
        f"🖼️ الصورة: {'تم نسخها ✅' if photo_ok else 'ما اننسخت ⚠️' + (f' — {photo_error}' if photo_error else '')}"
        f"{username_note}\n\n"
        "للإرجاع اكتب: `.ارجاع`"
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.ارجاع$"))
async def restore_cmd(event):
    """يرجع حسابك كما كان: اسمك ويوزرك وبايوك وصورتك الأصلية."""
    backup = load_json(CLONE_FILE, None)
    if not backup:
        await event.edit("❌ ما في انتحال شغال حالياً، وما في نسخة احتياطية للإرجاع.")
        return
    await event.edit("🔄 جاري إرجاع حسابك كما كان...")
    # نحذف صورة الانتحال إذا حفظنا آيديها
    if backup.get("clone_photo_id"):
        try:
            from telethon.tl.types import InputPhoto
            await client(DeletePhotosRequest([InputPhoto(id=backup["clone_photo_id"], access_hash=0, file_reference=b"")]))
        except Exception:
            pass
    # نرجع الاسم والبايو واليوزر
    try:
        await client(UpdateProfileRequest(
            first_name=backup.get("first_name") or " ",
            last_name=backup.get("last_name") or "",
            about=backup.get("about") or "",
        ))
    except Exception as e:
        await event.edit(f"❌ ما قدرت أرجّع الاسم/البايو.\n`{e}`")
        return
    if backup.get("username"):
        try:
            await client(UpdateUsernameRequest(backup["username"]))
        except Exception:
            pass
    # نرجع صورتك الأصلية
    photo_ok = False
    if backup.get("photo") and os.path.exists(backup["photo"]):
        try:
            uploaded = await client.upload_file(backup["photo"])
            await client(UploadProfilePhotoRequest(uploaded))
            photo_ok = True
        except Exception as e:
            print(f"⚠️ ما قدرت أرجّع الصورة: {e}")
    try:
        os.remove(CLONE_FILE)
    except Exception:
        pass
    await event.edit(
        f"✅ **تم الإرجاع! حسابك رجع كما كان:**\n\n"
        f"👤 الاسم: {backup.get('first_name', '')} {backup.get('last_name', '')}\n"
        f"🆔 اليوزر: @{backup.get('username', '')}\n"
        f"📝 البايو: {backup.get('about', '') or 'فاضي'}\n"
        f"🖼️ الصورة: {'رجعت ✅' if photo_ok else 'ما كان عندك صورة محفوظة ⚠️'}"
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.انتحال_حالة$"))
async def clone_status(event):
    backup = load_json(CLONE_FILE, None)
    if backup:
        await event.edit(
            "🎭 **أنت منتحل حالياً!**\n\n"
            f"اسمك الأصلي المحفوظ: {backup.get('first_name', '')}\n"
            f"يوزرك الأصلي: @{backup.get('username', '')}\n\n"
            "للإرجاع اكتب: `.ارجاع`"
        )
    else:
        await event.edit("ℹ️ أنت مو منتحل حدا حالياً.\nانتحل شخص بـ: `.انتحال` بالرد عليه، أو `.انتحال @يوزره`")


# ───────────────────────── تهكير وهمي (مزح فقط — مو حقيقي) ─────────────────────────
def progress_bar(pct):
    filled = pct // 10
    return "█" * filled + "░" * (10 - filled)


async def play_hack(event, target_name, frames, final_text, delay=0.7):
    """يشغل أنيميشن تهكير وهمي: شريط تحميل بيتحرك ومراحل، وبالآخر الرسالة النهائية."""
    for frame in frames:
        try:
            await event.edit(frame)
        except Exception:
            return
        await asyncio.sleep(delay)
    try:
        await event.edit(final_text)
    except Exception:
        pass


def hack_target_name(reply, event):
    if reply:
        return reply.sender.first_name or "الهدف"
    return "الهدف"


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.تهكير$"))
async def fake_hack1(event):
    """تهكير وهمي — تصميم 1: شريط تحميل كلاسيكي. رد على رسالة الشخص أولاً."""
    reply = await event.get_reply_message()
    name = hack_target_name(reply, event)
    frames = []
    stages = [
        (5, "🔌 جاري الاتصال بحساب " + name + "..."),
        (15, "🔍 جاري البحث عن ثغرة..."),
        (30, "🔓 جاري تجاوز كلمة السر..."),
        (45, "📥 جاري تحميل الصور..."),
        (60, "📩 جاري تحميل الرسائل..."),
        (75, "📇 جاري تحميل جهات الاتصال..."),
        (88, "💾 جاري حفظ البيانات..."),
        (97, "⏳ جاري إنهاء التهكير..."),
    ]
    for pct, stage in stages:
        frames.append(f"💻 **جاري تهكير حساب {name}...**\n\n{stage}\n[{progress_bar(pct)}] {pct}%")
    await play_hack(
        event, name, frames,
        f"✅ **تم تهكير حساب {name}!**\n\n"
        f"📸 الصور: تم تحميلها\n📩 الرسائل: تم تحميلها\n📇 جهات الاتصال: تم تحميلها\n\n"
        f"💰 **ادفع لصاحب الحساب لكي لا يتم نشر بياناتك!** 😂\n\n"
        "😂 **مزحة فقط — ما تم تهكير شي، ولا حدا أخذ بياناتك!**",
        delay=0.7,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.هكر$"))
async def fake_hack2(event):
    """تهكير وهمي — تصميم 2: شاشة هاكر خضراء (ترمينال)."""
    reply = await event.get_reply_message()
    name = hack_target_name(reply, event)
    frames = [
        f"```\n[>_] root@subaru:~$ hack {name}\n[>_] Connecting...\n```",
        f"```\n[>_] root@subaru:~$ hack {name}\n[>_] Connecting... OK\n[>_] Bypassing firewall...\n```",
        f"```\n[>_] Bypassing firewall... OK\n[>_] Cracking password...\n[>_] ██████░░░░ 60%\n```",
        f"```\n[>_] Cracking password... OK\n[>_] Downloading data...\n[>_] █████████░ 90%\n```",
        f"```\n[>_] Downloading data... OK\n[>_] Access granted!\n[>_] ██████████ 100%\n```",
    ]
    await play_hack(
        event, name, frames,
        f"💻 **HACKED!**\n\n"
        f"✅ تم اختراق حساب **{name}** بنجاح!\n\n"
        f"💰 ادفع لصاحب الحساب لكي لا يتم نشر بياناتك! 😂\n\n"
        "😂 مزحة فقط — ما صار شي حقيقي!",
        delay=0.8,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.اختراق$"))
async def fake_hack3(event):
    """تهكير وهمي — تصميم 3: ماتريكس وإيموجي."""
    reply = await event.get_reply_message()
    name = hack_target_name(reply, event)
    frames = [
        f"🕶️ **بدء الاختراق...**\n👤 الهدف: {name}\n⏳ 0%",
        f"🕶️ **اختراق جارٍ...**\n🔓 كسر الحماية...\n▓▓░░░░░░░░ 20%",
        f"🕶️ **اختراق جارٍ...**\n📡 سحب البيانات...\n▓▓▓▓▓░░░░░ 50%",
        f"🕶️ **اختراق جارٍ...**\n💾 نسخ الصور والرسائل...\n▓▓▓▓▓▓▓░░░ 75%",
        f"🕶️ **اختراق جارٍ...**\n🔥 تقريباً خلصنا...\n▓▓▓▓▓▓▓▓▓░ 95%",
    ]
    await play_hack(
        event, name, frames,
        f"😎 **تم الاختراق!**\n\n"
        f"🎯 الضحية: **{name}**\n"
        f"📸 صوره ورسائله صارت معنا!\n\n"
        f"💰 ادفع لصاحب الحساب لكي لا يتم نشر بياناتك! 😂\n\n"
        "😂 مزحة فقط — كل شي وهمي!",
        delay=0.7,
    )


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.فيروس$"))
async def fake_virus(event):
    """فيروس وهمي — تصميم 4: تحميل فيروس مزيف."""
    reply = await event.get_reply_message()
    name = hack_target_name(reply, event)
    frames = [
        f"🦠 **إرسال فيروس إلى {name}...**\n[░░░░░░░░░░] 0%",
        f"🦠 **إرسال فيروس إلى {name}...**\n[███░░░░░░░] 30%\n⚠️ الفيروس ينتشر...",
        f"🦠 **إرسال فيروس إلى {name}...**\n[██████░░░░] 60%\n⚠️ تم تعطيل الحماية...",
        f"🦠 **إرسال فيروس إلى {name}...**\n[█████████░] 90%\n⚠️ تم حذف الملفات...",
        f"🦠 **إرسال فيروس إلى {name}...**\n[██████████] 100%",
    ]
    await play_hack(
        event, name, frames,
        f"🦠 **تم إصابة حساب {name} بالفيروس!**\n\n"
        f"📱 جهازه راح ينفجر خلال 10 ثواني! 💥😂\n\n"
        f"💰 ادفع لصاحب الحساب لكي لا يتم نشر بياناتك! 😂\n\n"
        "😂 مزحة فقط — ما في فيروس ولا شي!",
        delay=0.7,
    )


# ───────────────────────── زخرفة ─────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.زخرفة(?:\s+(.+))?$"))
async def decorate_cmd(event):
    text = (event.pattern_match.group(1) or "").strip()
    if not text and event.is_reply:
        reply = await event.get_reply_message()
        text = (reply.text or "").strip() if reply else ""
    if not text:
        await event.edit(
            "✨ **زخرفة الكلمات**\n\n"
            "اكتب: `.زخرفة الكلمة`\n"
            "أو رد على رسالة بـ `.زخرفة`\n\n"
            "مثال: `.زخرفة سوبارو` أو `.زخرفة Subaru`"
        )
        return
    if len(text) > 30:
        await event.edit("❌ الكلمة طويلة — خليها 30 حرف كحد أقصى.")
        return
    styles = decorate_text(text)
    lines = [f"✨ **زخرفة:** `{text}`\n"]
    for i, (name, styled) in enumerate(styles, 1):
        lines.append(f"{i}️⃣ {name}\n`{styled}`")
    lines.append("\n💡 انسخ أي نمط يعجبك من فوق")
    await event.edit("\n".join(lines))


# ───────────────────────── الأمان ─────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.امان$"))
async def safety_cmd(event):
    today = datetime.now().strftime("%Y-%m-%d")
    stats = load_json("transfer_stats.json", {"date": today, "count": 0})
    today_count = stats.get("count", 0) if stats.get("date") == today else 0
    await event.edit(
        "🛡️ **تقرير أمان سورس سوبارو**\n\n"
        f"✅ الوضع الآمن: {'مفعّل' if SAFE_MODE else 'متوقف ⚠️'}\n"
        f"⏱️ تأخير النقل: {TRANSFER_DELAY}–{TRANSFER_DELAY + 5} ثانية (عشوائي)\n"
        f"🔢 حد النقل بأمر واحد: {MAX_LIMIT} | الافتراضي: {DEFAULT_LIMIT}\n"
        f"📅 نقلت اليوم: {today_count} / {DAILY_TRANSFER_LIMIT}\n"
        "🧹 حد التنظيف: 50 عضو | تأخير 5 ثواني\n"
        "📋 حد النسخ: 50 منشور | تأخير 2 ثانية\n"
        "📢 حد النشر: 5 دقائق كأقل فترة\n\n"
        "⚠️ **قواعد ذهبية عشان ما يجيك حظر:**\n"
        "• لا تنقل أكثر من 100 عضو باليوم\n"
        "• لا تشغل النقل أكثر من مرة باليوم\n"
        "• استخدم النقل لقروباتك أو بإذن أصحابها فقط\n"
        "• إذا طلع لك FloodWait، وقف كل شي وريح الحساب يوم\n"
        "• لا تشارك ملف subaru.session مع حدا أبداً\n"
        "• لا تستخدم الانتحال لخداع الناس\n\n"
        "ℹ️ ضمان 100% ما في — أي يوزربوت فيه مخاطرة بسيطة، بس هالحدود بتقللها لأقل حد ممكن."
    )


# ───────────────────────── القناة الرئيسية للسورس ─────────────────────────
async def join_main_channel():
    """أول ما يشتغل السورس: حسابك بينضم تلقائياً للقناة الرئيسية للسورس."""
    if not MAIN_CHANNEL:
        return False
    try:
        st, val = extract_source(MAIN_CHANNEL)
        if st == "invite":
            await join_source(st, val)
        else:
            entity = await client.get_entity(val)
            await client(JoinChannelRequest(entity))
        print(f"📢 انضممت للقناة الرئيسية: {MAIN_CHANNEL}")
        return True
    except UserAlreadyParticipantError:
        print(f"📢 أنت عضو أصلاً في القناة الرئيسية: {MAIN_CHANNEL}")
        return True
    except FloodWaitError as e:
        print(f"⏳ فلوود أثناء الانضمام للقناة الرئيسية، جرب بعد {e.seconds} ثانية")
        await send_log("⏳ فلوود أثناء الانضمام للقناة الرئيسية", str(e), "تيليجرام طلب انتظار مؤقت بسبب كثرة الطلبات — السورس بيكمل عادي وبتنضم للقناة بالتشغيل الجاي.")
        return False
    except Exception as e:
        print(f"❌ ما قدرت أنضم للقناة الرئيسية {MAIN_CHANNEL}: {e}")
        await send_log(
            "❌ ما قدرت أنضم للقناة الرئيسية للسورس",
            f"{MAIN_CHANNEL} — {e}",
            "غالباً القناة خاصة أو الرابط غلط أو انحذفت، أو حسابك محظور من الانضمام. تأكد من الرابط وجرّب تنضم يدوياً، أو غيّر الرابط في config.py باسم MAIN_CHANNEL.",
        )
        return False


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.القناة$"))
async def main_channel_cmd(event):
    await event.edit(f"📢 **القناة الرئيسية لسورس سوبارو:**\n{MAIN_CHANNEL}\n\nجاري الانضمام...")
    ok = await join_main_channel()
    if ok:
        await event.edit(f"✅ **انضممت للقناة الرئيسية:**\n{MAIN_CHANNEL}")
    else:
        await event.edit(f"❌ ما قدرت أنضم للقناة:\n{MAIN_CHANNEL}\n\nتأكد من الرابط، وتفاصيل الخطأ انبعتت لقروب السجل.")


# ───────────────────────── التشغيل ─────────────────────────
async def main():
    global OWNER_ID
    await client.start()
    me = await client.get_me()
    OWNER_ID = me.id
    print("=" * 45)
    print("✦ سورس سوبارو شغال ✦")
    print(f"👤 الحساب: {me.first_name} (@{me.username})")
    print(f"🆔 الآيدي: {me.id}")
    print("💬 اكتب .الاوامر في أي محادثة لتشوف الأوامر")
    print("📥 للنقل اكتب: .نقل رابط_القروب 30")
    print(f"📢 النشر التلقائي: {len(SCHEDULES)} جدولة محملة من schedules.json")
    # أول ما يشتغل السورس: حسابك بينضم تلقائياً للقناة الرئيسية للسورس
    try:
        await join_main_channel()
    except Exception as e:
        print(f"⚠️ مشكلة بالانضمام للقناة الرئيسية: {e}")
    # أول ما يشتغل السورس: ينشئ قروبي السجل والتخزين إذا مو موجودين
    try:
        await ensure_system_groups()
        print(f"📋 قروب السجل: {SYSTEM.get('log_id')}")
        print(f"🗄️ قروب التخزين: {SYSTEM.get('storage_id')}")
        await send_log("✅ سورس سوبارو اشتغل", f"الحساب: {me.first_name} (@{me.username})", "")
    except Exception as e:
        print(f"⚠️ مشكلة بإنشاء قروبي النظام: {e}")
    # بوت BotFather: يشتغل إذا في توكن، وتطلع لك رسالة أزرار تختار نوعه
    try:
        await setup_bot_client()
        if BOT_TOKEN:
            await send_mode_selection()
    except Exception as e:
        print(f"⚠️ مشكلة بتشغيل بوت BotFather: {e}")
        await send_log("❌ فشل تشغيل بوت BotFather", str(e), "التوكن غلط أو منتهي — اعمل بوت جديد من @BotFather بأمر /newbot وحط توكنه في .env باسم BOT_TOKEN.")
    print("=" * 45)
    asyncio.create_task(scheduler_loop())
    # البوت واليوزربوت بيشتغلوا مع بعض بنفس العملية
    if bot_client is not None:
        await asyncio.gather(client.run_until_disconnected(), bot_client.run_until_disconnected())
    else:
        await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
