# Estructura base del sistema profesional de trading algorítmico con integración de Random Forest + LSTM para predicciones híbridas y autoentrenamiento programado

# === main.py ===

from data.data_loader import get_data
from model.predictor import train_model, predict_returns
from model.lstm_model import train_lstm_model, predict_lstm_returns
from strategy.risk_manager import generate_signals, apply_risk_controls
from execution.broker import execute_trades, close_positions
from utils.scheduler import schedule_training, combine_predictions
from utils.environment import ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL
import alpaca_trade_api as tradeapi
import pandas as pd
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("trading_bot")

# Inicialización de la API con las variables de entorno importadas
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, api_version='v2')

def main():
    try:
        logger.info("Iniciando sistema de trading")
        
        # Verificar que podemos conectar con Alpaca
        try:
            account = api.get_account()
            logger.info(f"Cuenta conectada. Equity: ${float(account.equity):.2f}")
        except Exception as e:
            logger.error(f"Error conectando con Alpaca API: {e}")
            return
        
        # Obtener datos
        logger.info("Descargando datos de mercado...")
        price_data = get_data()
        logger.info(f"Datos descargados para {len(price_data.columns)} tickers")
        
        # Entrenamiento programado
        logger.info("Verificando si es necesario reentrenar modelos...")
        rf_model, lstm_model = schedule_training(price_data)
        
        # Si no se reentrenó, cargar los modelos existentes
        if rf_model is None or lstm_model is None:
            logger.info("Entrenando modelos...")
            rf_model = train_model(price_data)
            lstm_model = train_lstm_model(price_data)
        
        # Predicciones
        logger.info("Generando predicciones...")
        rf_predictions = predict_returns(rf_model, price_data)
        lstm_predictions = predict_lstm_returns(lstm_model, price_data)
        
        # Combinación de modelos con validación cruzada
        combined_predictions = combine_predictions(price_data, rf_predictions, lstm_predictions)
        
        # Generación de señales y ejecución
        logger.info("Calculando señales de trading...")
        
        # Obtener equity actual de la cuenta
        account_equity = float(api.get_account().equity)
        
        # Calcular rendimientos históricos
        historical_returns = price_data.pct_change().dropna()
        
        # Generar señales
        signals = generate_signals(price_data, combined_predictions)
        logger.info(f"Señales generadas: {signals}")
        
        # Aplicar controles de riesgo
        filtered_signals = apply_risk_controls(signals, price_data, account_equity, historical_returns)
        logger.info(f"Señales filtradas: {filtered_signals}")
        
        # Ejecutar operaciones
        logger.info("Ejecutando operaciones...")
        execute_trades(filtered_signals)
        close_positions(filtered_signals)
        
        logger.info("Ejecución del sistema de trading finalizada")
        
    except Exception as e:
        logger.error(f"Error en la ejecución principal: {e}")

if __name__ == "__main__":
    main()
