# -*- coding: utf-8 -*-
"""
إعدادات سورس سوبارو
حط بياناتك هنا، أو حطها في ملف .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

# من موقع https://my.telegram.org/apps
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")

SESSION_NAME = os.getenv("SESSION_NAME", "subaru")

# نسخة الاستضافة: جلسة نصية بدل ملف subaru.session
# لأن ملفات الاستضافة المجانية بتنمسح مع كل إعادة تشغيل،
# الجلسة بتنحفظ كنص في متغير SESSION_STRING (بتجيبه من get_session.py)
# إذا كان فاضي، السورس بيرجع لملف الجلسة العادي
SESSION_STRING = os.getenv("SESSION_STRING", "")

# منفذ سيرفر الصحة (Render بيعطيه تلقائياً في متغير PORT)
PORT = int(os.getenv("PORT", "10000") or 10000)

# توكن البوت من @BotFather — اعمل بوت جديد بأمر /newbot وانسخ التوكن هنا
# إذا تركته فاضي، اليوزربوت بيشتغل عادي بدون بوت
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# القناة الرئيسية للسورس — أول ما يشتغل السورس حسابك بينضم لها تلقائياً
MAIN_CHANNEL = os.getenv("MAIN_CHANNEL", "https://t.me/subaru_surce")

# ── الأمان: هالإعدادات بتحمي حسابك من الحظر، لا تنقصها ──
# النقل: التأخير بين كل عضو وعضو بالثواني (10 ثواني + عشوائي حتى 5 ثواني إضافية)
# تيليجرام بيحظر الحسابات اللي بتضيف أعضاء بسرعة، فلا تنقصه عن 10 أبداً
TRANSFER_DELAY = max(10, int(os.getenv("TRANSFER_DELAY", "10") or 10))

# العدد الافتراضي للنقل إذا ما كتبت عدد
DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "20"))

# أقصى عدد مسموح بنقله بأمر واحد
MAX_LIMIT = int(os.getenv("MAX_LIMIT", "50"))

# أقصى عدد أعضاء تنقلهم باليوم كامل (حماية من الحظر)
DAILY_TRANSFER_LIMIT = int(os.getenv("DAILY_TRANSFER_LIMIT", "100"))

# الوضع الآمن: True = يفرض كل حدود الأمان حتى لو حاولت تغيرها بالأوامر
SAFE_MODE = os.getenv("SAFE_MODE", "true").lower() in ("true", "1", "yes")

if API_ID == 0 or not API_HASH:
    print("⚠️  تنبيه: لازم تحط API_ID و API_HASH في config.py أو ملف .env")
    print("   جيبهم من: https://my.telegram.org/apps")
