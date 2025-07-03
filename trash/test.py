from twilio.rest import Client
from dotenv import load_dotenv
import os

# Load .env variables
load_dotenv()

# Pull from env
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_whatsapp = os.getenv("TWILIO_PHONE_FROM")
to_whatsapp = os.getenv("TWILIO_PHONE_TO")

# Create client and send message
client = Client(account_sid, auth_token)

try:
    message = client.messages.create(
        from_=from_whatsapp,
        to=to_whatsapp,
        body="🚀 WhatsApp test: This is your AI commuter agent reporting for duty!"
    )
    print("✅ Message SID:", message.sid)
except Exception as e:
    print("❌ Failed to send WhatsApp message:", e)