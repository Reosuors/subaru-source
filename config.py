# -*- coding: utf-8 -*-
"""
إعدادات سورس سوبارو
حط بياناتك هنا، أو حطها في ملف .env
"""
import os

# python-dotenv اختياري: إذا مش مثبّت (مثل Pydroid) بنقرأ ملف .env يدوياً
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    try:
        _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(_env_path):
            with open(_env_path, encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if not _line or _line.startswith("#") or "=" not in _line:
                        continue
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
    except Exception:
        pass

# من موقع https://my.telegram.org/apps
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")

SESSION_NAME = os.getenv("SESSION_NAME", "subaru")

# نسخة الاستضافة: جلسة نصية بدل ملف subaru.session
# لأن ملفات الاستضافة المجانية بتنمسح مع كل إعادة تشغيل،
# الجلسة بتنحفظ كنص في متغير SESSION_STRING.
# عندك 3 طرق تحط الجلسة بيدك — اختار وحدة:
#   1) متغير بيئة SESSION_STRING في Render (الطريقة المفضلة)
#   2) ملف session_string.txt جنب main.py — الصق فيه النص واحفظه
#   3) سكربت get_session.py --paste — بيسألك تلصق النص وهو بيتحقق منه
# إذا ما كان في جلسة نصية، السورس بيرجع لملف الجلسة العادي subaru.session
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
if not SESSION_STRING:
    try:
        _session_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_string.txt")
        if os.path.exists(_session_file):
            with open(_session_file, encoding="utf-8") as _f:
                SESSION_STRING = _f.read().strip()
    except Exception:
        pass

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
