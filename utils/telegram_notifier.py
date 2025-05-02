import requests
from utils.environment import TELEGRAM_API_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    """
    Envía un mensaje a través de Telegram usando el token y chat ID definidos
    en las variables de entorno.
    
    Args:
        message: Texto del mensaje a enviar
    
    Returns:
        bool: True si el mensaje se envió con éxito, False en caso contrario
    """
    if not TELEGRAM_API_TOKEN or not TELEGRAM_CHAT_ID:
        print("Advertencia: Token de Telegram o Chat ID no configurados")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Excepción enviando mensaje: {e}")
        return False
