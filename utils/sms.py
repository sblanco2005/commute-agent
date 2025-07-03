# ✅ utils/sms.py
from twilio.rest import Client
import os

# Load credentials (env variables or replace inline)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_FROM = os.getenv("TWILIO_PHONE_FROM")
TWILIO_PHONE_TO = os.getenv("TWILIO_PHONE_TO")


def send_alert_whatsapp(message: str):
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

