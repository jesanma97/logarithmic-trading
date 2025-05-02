# === /utils/environment.py ===
import os
from dotenv import load_dotenv

# Intenta cargar variables desde .env (para desarrollo local)
load_dotenv()

def get_env_variable(key, default=None):
    """
    Obtiene una variable de entorno, con mejor manejo de errores.
    
    Args:
        key: Nombre de la variable de entorno.
        default: Valor por defecto si no se encuentra la variable.
    
    Returns:
        El valor de la variable de entorno o el valor por defecto.
    """
    value = os.getenv(key, default)
    if value is None:
        print(f"Advertencia: Variable de entorno {key} no encontrada.")
    return value

# Constantes usadas en toda la aplicación
ALPACA_API_KEY = get_env_variable("ALPACA_API_KEY")
ALPACA_SECRET_KEY = get_env_variable("ALPACA_SECRET_KEY")
BASE_URL = get_env_variable("BASE_URL", "https://paper-api.alpaca.markets")
TELEGRAM_API_TOKEN = get_env_variable("TELEGRAM_API_TOKEN")
TELEGRAM_CHAT_ID = get_env_variable("TELEGRAM_CHAT_ID")