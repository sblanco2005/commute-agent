import os
import requests
from dotenv import load_dotenv
from twilio.rest import Client

# ✅ Load .env values
load_dotenv()

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_FROM = os.getenv("TWILIO_PHONE_FROM")
TWILIO_PHONE_TO = os.getenv("TWILIO_PHONE_TO")

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_alert_whatsapp(message: str):
    print(f"📤 From: {TWILIO_PHONE_FROM}, To: {TWILIO_PHONE_TO}")

    if not TWILIO_PHONE_TO:
        print("❌ TWILIO_PHONE_TO is missing!")
        return

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        client.messages.create(
            from_=TWILIO_PHONE_FROM,
            to=TWILIO_PHONE_TO,
            body=message
        )
        print("✅ WhatsApp message sent.")
    except Exception as e:
        print(f"❌ WhatsApp send failed: {e}")


def send_alert_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not set.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        print("✅ Telegram message sent.")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")


def send_alert(message: str, channels=("whatsapp", "telegram")):
    if "whatsapp" in channels:
        send_alert_whatsapp(message)
    if "telegram" in channels:
        send_alert_telegram(message)