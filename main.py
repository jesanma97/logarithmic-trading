# Estructura base del sistema profesional de trading algorítmico con integración de Random Forest + LSTM para predicciones híbridas y autoentrenamiento programado

# === main.py ===

from data.data_loader import get_data
from model.predictor import train_model, predict_returns
from model.lstm_model import train_lstm_model, predict_lstm_returns
from strategy.risk_manager import generate_signals, apply_risk_controls
from execution.broker import execute_trades, close_positions, monitor_stops
from utils.scheduler import schedule_training, combine_predictions

# Obtener datos
price_data = get_data()

# Entrenamiento programado
rf_model, lstm_model = schedule_training(price_data)

# Si no se reentrenó, cargar los modelos existentes
if rf_model is None or lstm_model is None:
    rf_model = train_model(price_data)
    lstm_model = train_lstm_model(price_data)

# Predicciones
rf_predictions = predict_returns(rf_model, price_data)
lstm_predictions = predict_lstm_returns(lstm_model, price_data)

# Combinación de modelos con validación cruzada
combined_predictions = combine_predictions(price_data, rf_predictions, lstm_predictions)

# Generación de señales y ejecución
signals = generate_signals(price_data, combined_predictions)
filtered_signals = apply_risk_controls(signals, price_data)

execute_trades(filtered_signals)
close_positions(filtered_signals)
monitor_stops()