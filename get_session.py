# -*- coding: utf-8 -*-
"""
يولّد جلسة نصية (SESSION_STRING) لنسخة الاستضافة.
شغّله مرة وحدة على جهازك فقط، وانسخ النص اللي بيطلع وحطه في Render
كمتغير بيئة باسم SESSION_STRING. لا تشارك هالنص مع حدا أبداً.

الاستخدام:
    pip install telethon python-dotenv
    python get_session.py
"""
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")

if API_ID == 0 or not API_HASH:
    print("❌ حط API_ID و API_HASH في ملف .env أولاً (من https://my.telegram.org/apps)")
    raise SystemExit(1)

print("📱 بيوصلك كود على تيليجرام — اكتبه هون.")
with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n✅ انسخ هالنص كامل وحطه في Render كمتغير SESSION_STRING:\n")
    print(client.session.save())
    print("\n⚠️ لا تشاركه مع حدا — هو مفتاح حسابك.")
