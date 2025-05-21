# === /main.py ===
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("trading_bot")

# Importar módulos del bot
from data.data_loader import get_data
from model.predictor import predict_returns
from model.lstm_model import predict_lstm_returns
from strategy.risk_manager import generate_signals, apply_risk_controls
from utils.scheduler import schedule_training, combine_predictions
from utils.telegram_notifier import send_telegram_message

def main():
    try:
        logger.info("=== INICIANDO TRADING BOT ===")
        
        # Cargar datos históricos
        logger.info("Cargando datos históricos...")
        try:
            price_data = get_data()
            if price_data.empty:
                logger.error("No se pudieron obtener datos históricos. Abortando ejecución.")
                return
            logger.info(f"Datos cargados correctamente: {len(price_data)} filas, {price_data.columns.size} columnas")
        except Exception as e:
            logger.error(f"Error fatal cargando datos: {e}")
            return
            
        # Calcular retornos históricos para análisis de riesgo
        historical_returns = price_data.pct_change().dropna()
        
        # Entrenar o cargar modelos según programación
        try:
            logger.info("Gestionando modelos...")
            rf_model, lstm_model = schedule_training(price_data)
            if rf_model is None:
                logger.warning("No se pudo cargar/entrenar el modelo RandomForest")
            if not lstm_model:
                logger.warning("No se pudieron cargar/entrenar los modelos LSTM")
        except Exception as e:
            logger.error(f"Error gestionando modelos: {e}")
            rf_model = None
            lstm_model = {}
        
        # Obtener predicciones de modelos
        rf_predictions = {}
        lstm_predictions = {}
        
        try:
            # Obtener predicciones del modelo RandomForest
            if rf_model is not None:
                logger.info("Generando predicciones con RandomForest...")
                rf_predictions = predict_returns(rf_model, price_data)
                logger.info(f"Predicciones RandomForest generadas para {len(rf_predictions)} activos")
        except Exception as e:
            logger.error(f"Error generando predicciones RandomForest: {e}")
        
        try:
            # Obtener predicciones del modelo LSTM
            if lstm_model:
                logger.info("Generando predicciones con LSTM...")
                lstm_predictions = predict_lstm_returns(lstm_model, price_data)
                logger.info(f"Predicciones LSTM generadas para {len(lstm_predictions)} activos")
        except Exception as e:
            logger.error(f"Error generando predicciones LSTM: {e}")
        
        # Combinar predicciones
        try:
            logger.info("Combinando predicciones...")
            
            # Verificar si tenemos suficientes predicciones
            if not rf_predictions and not lstm_predictions:
                logger.error("No se pudo generar ninguna predicción. Abortando.")
                return
                
            predictions = combine_predictions(price_data, rf_predictions, lstm_predictions)
            logger.info(f"Predicciones combinadas para {len(predictions)} activos")
            
            # Generar señales
            threshold = 0.005  # 0.5% mínimo de retorno esperado
            signals = generate_signals(price_data, predictions, threshold)
            logger.info(f"Señales generadas: {signals}")
        except Exception as e:
            logger.error(f"Error combinando predicciones o generando señales: {e}")
            return
        
        # Aplicar controles de riesgo
        try:
            account_equity = 10000  # Simulación de capital, en un caso real vendría de la API de broker
            filtered_signals = apply_risk_controls(signals, price_data, account_equity, historical_returns, predictions)
            
            if not filtered_signals:
                logger.warning("No hay señales después de filtros de riesgo")
                send_telegram_message("⚠️ No hay operaciones para hoy según los filtros de riesgo.")
                return
                
            logger.info(f"Señales después de filtros de riesgo: {filtered_signals}")
        except Exception as e:
            logger.error(f"Error aplicando controles de riesgo: {e}")
            return
            
        # En un sistema real, aquí ejecutaríamos las órdenes mediante la API del broker
        # Simulación de ejecutar órdenes
        message = "🤖 <b>Operaciones para hoy:</b>\n\n"
        
        for ticker, weight in filtered_signals.items():
            direction = "COMPRA" if weight > 0 else "VENTA"
            target_price = price_data[ticker].iloc[-1] * (1 + predictions.get(ticker, [0])[0])
            message += f"✅ <b>{ticker}</b>: {direction} - Objetivo: ${target_price:.2f} ({abs(weight)*100:.1f}% del capital)\n"
            
        # Enviar notificación
        logger.info("Enviando notificación...")
        send_telegram_message(message)
        
        logger.info("=== EJECUCIÓN COMPLETADA ===")
        
    except Exception as e:
        logger.critical(f"Error no controlado: {e}")
        send_telegram_message(f"❌ Error crítico en el sistema: {e}")

if __name__ == "__main__":
    main()
