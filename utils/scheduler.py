# === /utils/scheduler.py ===
import os
import pickle
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from model.predictor import train_model
from model.lstm_model import train_lstm_model

# Configuración de logging
logger = logging.getLogger("trading_bot")

# Ruta para guardar modelos
MODEL_DIR = "./models"
LAST_TRAIN_FILE = os.path.join(MODEL_DIR, "last_train_date.txt")
RF_MODEL_FILE = os.path.join(MODEL_DIR, "rf_model.pkl")
LSTM_MODEL_FILE = os.path.join(MODEL_DIR, "lstm_model.pkl")

def schedule_training(data):
    """
    Gestiona el entrenamiento programado de modelos.
    Entrena modelos si aún no existen o si ha pasado el tiempo de reentrenamiento.
    
    Args:
        data: DataFrame con los datos históricos para entrenamiento
    
    Returns:
        tuple: (modelo_rf, modelo_lstm) - modelos entrenados o cargados
    """
    # Verificar si es necesario entrenar
    should_train = _check_training_required()
    
    # Si se requiere entrenamiento o los modelos no existen
    if should_train or not os.path.exists(RF_MODEL_FILE) or not os.path.exists(LSTM_MODEL_FILE):
        try:
            logger.info("Entrenando nuevos modelos...")
            
            # Entrenar modelos
            rf_model = train_model(data)
            lstm_model = train_lstm_model(data)
            
            # Guardar modelos entrenados
            _save_models(rf_model, lstm_model)
            
            # Actualizar fecha de último entrenamiento
            with open(LAST_TRAIN_FILE, 'w') as f:
                f.write(datetime.now().strftime('%Y-%m-%d'))
                
            logger.info("Modelos entrenados y guardados correctamente")
            return rf_model, lstm_model
            
        except Exception as e:
            logger.error(f"Error durante el entrenamiento programado: {e}")
            # En caso de error, intentar cargar modelos existentes
            rf_model, lstm_model = _load_models()
            return rf_model, lstm_model
    else:
        # Si no es necesario entrenar, cargar modelos existentes
        logger.info("Cargando modelos existentes...")
        rf_model, lstm_model = _load_models()
        return rf_model, lstm_model

def _check_training_required():
    """
    Determina si es necesario reentrenar los modelos basado en la fecha
    del último entrenamiento.
    
    Returns:
        bool: True si se requiere reentrenamiento, False en caso contrario
    """
    # Intervalo de reentrenamiento (en días)
    RETRAINING_INTERVAL = 7  # Reentrenar semanalmente
    
    # Si no existe archivo de control, reentrenar
    if not os.path.exists(LAST_TRAIN_FILE):
        logger.info("No existe registro de entrenamiento previo. Reentrenando...")
        return True
        
    # Obtener fecha del último entrenamiento
    try:
        with open(LAST_TRAIN_FILE, 'r') as f:
            last_train_date = datetime.strptime(f.read().strip(), '%Y-%m-%d')
        
        # Calcular si ha pasado el intervalo de reentrenamiento
        days_since_last_train = (datetime.now() - last_train_date).days
        if days_since_last_train >= RETRAINING_INTERVAL:
            logger.info(f"Han pasado {days_since_last_train} días desde el último entrenamiento. Reentrenando...")
            return True
        else:
            logger.info(f"Último entrenamiento hace {days_since_last_train} días. No es necesario reentrenar aún.")
            return False
            
    except Exception as e:
        logger.warning(f"Error verificando fecha de entrenamiento: {e}. Reentrenando por seguridad...")
        return True

def _save_models(rf_model, lstm_model):
    """
    Guarda los modelos entrenados en disco.
    
    Args:
        rf_model: Modelo RandomForest entrenado
        lstm_model: Modelo LSTM entrenado
    """
    # Crear directorio si no existe
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # Guardar modelos usando pickle
    try:
        with open(RF_MODEL_FILE, 'wb') as f:
            pickle.dump(rf_model, f)
            
        with open(LSTM_MODEL_FILE, 'wb') as f:
            pickle.dump(lstm_model, f)
            
        logger.info("Modelos guardados correctamente")
    except Exception as e:
        logger.error(f"Error guardando modelos: {e}")

def _load_models():
    """
    Carga los modelos previamente guardados.
    
    Returns:
        tuple: (modelo_rf, modelo_lstm) - modelos cargados o None si ocurre un error
    """
    rf_model = None
    lstm_model = None
    
    # Intentar cargar modelo RandomForest
    if os.path.exists(RF_MODEL_FILE):
        try:
            with open(RF_MODEL_FILE, 'rb') as f:
                rf_model = pickle.load(f)
            logger.info("Modelo RandomForest cargado correctamente")
        except Exception as e:
            logger.error(f"Error cargando modelo RandomForest: {e}")
    
    # Intentar cargar modelo LSTM
    if os.path.exists(LSTM_MODEL_FILE):
        try:
            with open(LSTM_MODEL_FILE, 'rb') as f:
                lstm_model = pickle.load(f)
            logger.info("Modelo LSTM cargado correctamente")
        except Exception as e:
            logger.error(f"Error cargando modelo LSTM: {e}")
    
    return rf_model, lstm_model

def combine_predictions(data, rf_predictions, lstm_predictions, rf_weight=0.6):
    """
    Combina las predicciones de los modelos RandomForest y LSTM.
    
    Args:
        data: DataFrame con los datos históricos
        rf_predictions: Predicciones del modelo RandomForest
        lstm_predictions: Predicciones del modelo LSTM
        rf_weight: Peso para el modelo RandomForest (entre 0 y 1)
    
    Returns:
        dict: Predicciones combinadas
    """
    combined = {}
    lstm_weight = 1 - rf_weight
    
    for ticker in data.columns:
        if ticker in rf_predictions and ticker in lstm_predictions:
            # Obtener predicciones individuales
            rf_pred = rf_predictions[ticker][0]
            lstm_pred = lstm_predictions[ticker][0]
            
            # Combinar con pesos
            combined_pred = (rf_weight * rf_pred) + (lstm_weight * lstm_pred)
            combined[ticker] = [combined_pred]
            
            logger.debug(f"{ticker}: RF={rf_pred:.4f}, LSTM={lstm_pred:.4f}, Combined={combined_pred:.4f}")
    
    return combined
