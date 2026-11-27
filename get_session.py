# -*- coding: utf-8 -*-
"""
جلسة نسخة الاستضافة — عندك طريقتين، اختار اللي بدك إياها:

1) توليد تلقائي (الافتراضي):
    python get_session.py
   بيطلب رقم هاتفك والكود، وبيطلع لك SESSION_STRING جاهز.

2) يدوي — أنت بتلصق الجلسة بيدك (مثلاً جلسة عندك من قبل،
   أو جلسة طلعتها من بوت / أداة تانية):
    python get_session.py --paste
   بيسألك تلصق النص، بيتحقق إنه جلسة صحيحة، وبيحفظها
   بملف session_string.txt (ما بينرفع على GitHub أبداً).

3) تحويل ملف جلسة عندك لنص:
    python convert_session.py
   بيحوّل ملف subaru.session اللي عندك لـ SESSION_STRING.

⚠️ الجلسة مفتاح حسابك — لا تشاركها مع حدا أبداً.
"""
import os
import sys
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

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

    print("📱 بيوصلك كود على تيليجرام — اكتبه هون.")
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
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


if __name__ == "__main__":
    main()
