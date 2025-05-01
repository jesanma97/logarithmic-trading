import requests
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=data)
        if response.status_code != 200:
            print("Error enviando mensaje:", response.text)
    except Exception as e:
        print("Excepción enviando mensaje:", e)
