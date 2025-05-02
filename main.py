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

# Inicialización de la API con las variables de entorno importadas
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, api_version='v2')

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
# Obtener equity actual de la cuenta
account_equity = float(api.get_account().equity)

# Calcular rendimientos históricos
historical_returns = price_data.pct_change().dropna()

signals = generate_signals(price_data, combined_predictions)
filtered_signals = apply_risk_controls(signals, price_data, account_equity, historical_returns)

execute_trades(filtered_signals)
close_positions(filtered_signals)