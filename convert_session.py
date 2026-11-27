# -*- coding: utf-8 -*-
"""
حوّل ملف جلسة عندك (subaru.session) لجلسة نصية SESSION_STRING.

الاستخدام:
    python convert_session.py
    python convert_session.py اسم_الملف.session

بيطبع النص، وبيحفظه بملف session_string.txt.
بعدها انسخ النص وحطه في Render كمتغير SESSION_STRING.
"""
import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")

if API_ID == 0 or not API_HASH:
    print("❌ حط API_ID و API_HASH في ملف .env أولاً (من https://my.telegram.org/apps)")
    raise SystemExit(1)

session_file = sys.argv[1] if len(sys.argv) > 1 else "subaru.session"
if not os.path.exists(session_file):
    print(f"❌ ما لقيت ملف الجلسة: {session_file}")
    print("   شغّل نسخة الجهاز أولاً عشان ينشئ الملف، أو استخدم get_session.py --paste")
    raise SystemExit(1)

# نفتح ملف الجلسة بدون ما نتصل بتيليجرام، ونقرأ نصه
client = TelegramClient(session_file, API_ID, API_HASH)
string = StringSession.save(client.session)
if not string:
    print("❌ ملف الجلسة فاضي أو مو مسجّل دخول — شغّل نسخة الجهاز وسجّل دخول أولاً،")
    print("   أو استخدم get_session.py --paste إذا عندك نص جلسة جاهز.")
    raise SystemExit(1)

with open("session_string.txt", "w", encoding="utf-8") as f:
    f.write(string)

print("✅ تم التحويل! انسخ هالنص وحطه في Render كمتغير SESSION_STRING:\n")
print(string)
print("\n💾 وانحفظ كمان بملف session_string.txt")
print("⚠️ لا تشاركه مع حدا — هو مفتاح حسابك.")
