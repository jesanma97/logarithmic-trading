# Estructura base del sistema profesional de trading algorítmico con integración de Random Forest + LSTM para predicciones híbridas y autoentrenamiento programado

# === main.py ===

from data.data_loader import get_data
from model.predictor import train_model, predict_returns
from model.lstm_model import train_lstm_model, predict_lstm_returns
from strategy.risk_manager import generate_signals, apply_risk_controls
from execution.broker import execute_trades, close_positions
from utils.scheduler import schedule_training, combine_predictions
from utils.environment import ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL
from utils.telegram_notifier import send_telegram_message
import alpaca_trade_api as tradeapi
import pandas as pd
import logging
import traceback

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
            send_telegram_message(f"🤖 Sistema de trading iniciado. Equity: ${float(account.equity):.2f}")
        except Exception as e:
            error_msg = f"Error conectando con Alpaca API: {e}"
            logger.error(error_msg)
            send_telegram_message(f"⚠️ {error_msg}")
            return
        
        # Verificar si el mercado está abierto
        clock = api.get_clock()
        if not clock.is_open:
            message = f"El mercado está cerrado. Próxima apertura: {clock.next_open}"
            logger.info(message)
            send_telegram_message(f"ℹ️ {message}")
            # Continuamos con la ejecución para generar predicciones y mantener el sistema actualizado
        
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
        
        # Ejecutar operaciones solo si hay señales filtradas
        if filtered_signals:
            logger.info("Ejecutando operaciones...")
            execute_trades(filtered_signals)
            close_positions(filtered_signals)
            # Enviar resumen de operaciones a Telegram
            send_telegram_message(f"📊 Resumen de operaciones realizadas: {', '.join([f'{k}: {v:.2f}' for k, v in filtered_signals.items()])}")
        else:
            logger.info("No hay operaciones para ejecutar después del filtrado")
            send_telegram_message("ℹ️ No se ejecutaron operaciones hoy: las señales no pasaron los filtros de riesgo")
        
        logger.info("Ejecución del sistema de trading finalizada")
        
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"Error en la ejecución principal: {e}\n{error_detail}")
        send_telegram_message(f"🚨 Error en el sistema de trading: {e}")

if __name__ == "__main__":
    main()
