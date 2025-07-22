import requests


def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"  # or "HTML" if preferred
    }
    response = requests.post(url, json=payload)
    if response.ok:
        print("✅ Message sent!")
    else:
        print("❌ Failed to send:", response.text)

send_telegram_message("*Commute Alert!*\n\n🚇 Next train: 4 min\n🌧️ Weather: Rain\n⚠️ Consider leaving early.")