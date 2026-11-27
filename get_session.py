# -*- coding: utf-8 -*-
"""
جلسة نسخة الاستضافة — عندك طرق، اختار اللي بدك إياها:

1) توليد تلقائي (الافتراضي):
    python get_session.py
   بيطلب رقم هاتفك والكود، وبيطلع لك SESSION_STRING جاهز.

2) دخول بالـ QR — بدون كود أبداً (إذا الكود ما عم يوصلك):
    python get_session.py --qr
   بيطبع لك كود QR بالشاشة، افتح تيليجرام ← الإعدادات ←
   الأجهزة ← ربط جهاز، وامسحه. إذا بتشغله على تلفونك نفسه
   والـ QR ما بينمسح، افتحه على كمبيوتر أو تلفون ثاني.

3) الكود برسالة SMS بدل تيليجرام:
    python get_session.py --sms
   بيجبر تيليجرام يبعت الكود SMS على خطك.

4) يدوي — أنت بتلصق الجلسة بيدك (مثلاً جلسة عندك من قبل،
   أو جلسة طلعتها من بوت / أداة تانية):
    python get_session.py --paste
   بيسألك تلصق النص، بيتحقق إنه جلسة صحيحة، وبيحفظها
   بملف session_string.txt (ما بينرفع على GitHub أبداً).

5) تحويل ملف جلسة عندك لنص:
    python convert_session.py
   بيحوّل ملف subaru.session اللي عندك لـ SESSION_STRING.

⚠️ الجلسة مفتاح حسابك — لا تشاركها مع حدا أبداً.
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")


def save_manual_session(text):
    """يتحقق من نص جلسة لصقته بيدك ويحفظه."""
    text = (text or "").strip()
    if not text:
        print("❌ ما لصقت شي.")
        return False
    try:
        StringSession(text)  # بيطلع خطأ إذا النص مو جلسة صحيحة
    except Exception as e:
        print(f"❌ هالنص مو جلسة صحيحة: {e}")
        print("   تأكد إنك نسخت النص كامل بدون مسافات زيادة أو نقص.")
        return False
    with open("session_string.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("✅ الجلسة صحيحة وانحفظت بملف session_string.txt")
    print("   هسا تقدر تنسخ محتواه وتحطه في Render كمتغير SESSION_STRING،")
    print("   أو تترك الملف هون إذا بتشغل السورس على جهازك.")
    print("   ⚠️ لا ترفع هالملف على GitHub — هو مفتاح حسابك.")
    return True


def finish(client):
    """بعد تسجيل الدخول: يحفظ الجلسة ويعرض إرسالها للمحفوظات."""
    session = client.session.save()
    print("\n✅ انسخ هالنص كامل وحطه في Render كمتغير SESSION_STRING:\n")
    print(session)
    print("\n💾 وبحفظه لك كمان بملف session_string.txt عشان تلاقيه جاهز.")
    with open("session_string.txt", "w", encoding="utf-8") as f:
        f.write(session)
    # إرسال الجلسة مقسّمة للرسائل المحفوظة (Saved Messages)
    send = input("\n📩 بدك أبعت الجلسة لرسائلك المحفوظة على تيليجرام؟ (y/n): ").strip().lower()
    if send in ("y", "yes", "نعم", "اه"):
        parts = [session[i:i + 100] for i in range(0, len(session), 100)]
        client.send_message("me", f"🍥 جلسة سورس سوبارو — {len(parts)} أجزاء، اجمعهم ورا بعض بدون مسافات:")
        for i, part in enumerate(parts, 1):
            client.send_message("me", f"جزء {i}/{len(parts)}:\n`{part}`")
        client.send_message("me", "✅ هاي جلستك كاملة — لا تشاركها مع حدا، هي مفتاح حسابك.")
        print(f"✅ انبعتت الجلسة لرسائلك المحفوظة على {len(parts)} جزء.")
    print("⚠️ لا تشاركها مع حدا — هي مفتاح حسابك.")


def main():
    if "--paste" in sys.argv or "--manual" in sys.argv:
        print("📋 الصق الجلسة النصية تبعك هون واضغط Enter:")
        text = input().strip()
        if not text:
            # إذا لصق نص طويل على سطور، input بياخد أول سطر بس
            print("❌ ما وصل نص. جرّب تلصقه بسطر واحد كامل.")
            return

        save_manual_session(text)
        return

    if API_ID == 0 or not API_HASH:
        print("❌ حط API_ID و API_HASH في ملف .env أولاً (من https://my.telegram.org/apps)")
        raise SystemExit(1)

    # ── دخول بالـ QR: بدون كود، بتمسح الكود من تيليجرام ──
    if "--qr" in sys.argv:
        print("📷 دخول بالـ QR — ما رح يوصلك أي كود.")
        print("   افتح تيليجرام ← الإعدادات ← الأجهزة ← ربط جهاز، وامسح الكود اللي تحت:")
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        client.connect()
        qr = client.qr_login()
        try:
            import qrcode
            code = qrcode.QRCode(border=1)
            code.add_data(qr.url)
            code.make()
            code.print_ascii(invert=True)
        except Exception:
            print(f"   رابط الـ QR: {qr.url}")
        print("   ⏳ بستنى تمسح الكود من تلفونك...")
        qr.wait()
        print("✅ تم تسجيل الدخول بالـ QR!")
        finish(client)
        client.disconnect()
        return

    # ── الكود SMS: بيجبر تيليجرام يبعت الكود رسالة نصية ──
    if "--sms" in sys.argv:
        phone = input("📱 رقم هاتفك مع رمز الدولة (مثال +447746129451): ").strip()
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        client.connect()
        client.send_code_request(phone, force_sms=True)
        print("📩 الكود انبعت SMS على خطك — اكتبه هون:")
        code = input("الكود: ").strip()
        try:
            client.sign_in(phone, code)
        except SessionPasswordNeededError:
            pw = input("🔑 عندك تحقق بخطوتين — اكتب كلمة سر التحقق: ").strip()
            client.sign_in(password=pw)
        print("✅ تم تسجيل الدخول!")
        finish(client)
        client.disconnect()
        return

    print("📱 بيوصلك كود على تيليجرام — اكتبه هون.")
    print("   (إذا الكود ما عم يوصلك جرّب: python get_session.py --qr  أو  --sms)")
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        finish(client)


if __name__ == "__main__":
    main()
