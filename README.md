Smart Commute Agent

An AI-powered assistant that helps optimize your daily commute using real-time transit data, weather alerts, and smart notifications via WhatsApp and Telegram.

🚀 Features
	•	🚌 Transit Tracking: Monitors NJ Transit buses and trains to Newark Penn Station.
	•	🚇 Subway Arrivals: Displays the next 3 downtown subway trains at 59th & Lexington.
	•	🌤 Weather Alerts: Integrates OpenWeatherMap for smart weather-based decisions.
	•	📍 Location Awareness: Optional geolocation-triggered actions.
	•	📱 Notifications: Sends smart summaries via Telegram or WhatsApp.
	•	💡 LLM-Ready: Prepped for integrating generative AI recommendations.

🛠 Tech Stack
	•	FastAPI – Backend API and coordination logic
	•	httpx + asyncio – For concurrent API requests
	•	Playwright – Optional web scraping for transit data
	•	Twilio / Telegram Bot API – For sending commute summaries
	•	OpenWeatherMap API – For weather conditions and alerts
	•	Docker – Containerized deployment
	•	Fly.io – Cloud hosting for live agent

📦 Setup
	1.	Clone the repo:
git clone https://github.com/yourusername/smart_commute_agent.git
cd smart_commute_agent

python -m venv .commute
source .commute/bin/activate
pip install -r requirements.txt

TELEGRAM_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_FROM=whatsapp:+14155238886
TWILIO_PHONE_TO=whatsapp:+1234567890
WEATHER_KEY=your_openweather_api_key


uvicorn api.server:app --host 0.0.0.0 --port 8502
