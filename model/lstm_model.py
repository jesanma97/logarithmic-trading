# === /model/lstm_model.py ===
import numpy as np
import pandas as pd
import pickle
import os
import logging
from keras.models import Sequential, load_model
from keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler

# Configuración de logging
logger = logging.getLogger("trading_bot")

# Directory for saving models and scalers
MODEL_DIR = "./models"
os.makedirs(MODEL_DIR, exist_ok=True)

sequence_length = 60
models = {}
scalers = {}

def create_sequences(data, seq_length=60):
    X, y = [], []
    for i in range(len(data) - seq_length - 1):
        X.append(data[i:(i + seq_length)])
        y.append(data[i + seq_length])
    return np.array(X), np.array(y)

def train_lstm_model(data):
    global models, scalers
    models = {}
    scalers = {}
    
    for ticker in data.columns:
        try:
            series = data[ticker].dropna()
            if len(series) <= sequence_length:
                logger.warning(f"Not enough data for {ticker} to train LSTM model. Need more than {sequence_length} points.")
                continue
                
            scaler = MinMaxScaler()
            scaled_series = scaler.fit_transform(series.values.reshape(-1,1)).flatten()
            scalers[ticker] = scaler
            
            X, y = create_sequences(scaled_series, sequence_length)
            if len(X) == 0 or len(y) == 0:
                logger.warning(f"Could not create training sequences for {ticker}")
                continue
                
            X = X.reshape((X.shape[0], X.shape[1], 1))

            model = Sequential()
            model.add(LSTM(64, return_sequences=True, input_shape=(X.shape[1], 1)))
            model.add(Dropout(0.2))
            model.add(LSTM(64, return_sequences=False))
            model.add(Dropout(0.2))
            model.add(Dense(1))

            model.compile(optimizer='adam', loss='mean_squared_error')
            model.fit(X, y, epochs=10, batch_size=32, verbose=0)

            models[ticker] = model
            
            # Save individual model and scaler
            model_path = os.path.join(MODEL_DIR, f"lstm_{ticker}_model.keras")
            scaler_path = os.path.join(MODEL_DIR, f"lstm_{ticker}_scaler.pkl")
            
            model.save(model_path)
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
                
            logger.info(f"Saved LSTM model and scaler for {ticker}")
        except Exception as e:
            logger.error(f"Error training LSTM for {ticker}: {e}")
    
    # Save the scalers dictionary separately as well for safety
    all_scalers_path = os.path.join(MODEL_DIR, "lstm_all_scalers.pkl")
    try:
        with open(all_scalers_path, 'wb') as f:
            pickle.dump(scalers, f)
        logger.info(f"Saved all LSTM scalers to {all_scalers_path}")
    except Exception as e:
        logger.error(f"Error saving all scalers: {e}")
            
    return models

def load_lstm_models(tickers):
    """
    Load saved LSTM models and scalers for the given tickers.
    """
    global models, scalers
    models = {}
    scalers = {}
    
    # First try to load all scalers from the combined file
    all_scalers_path = os.path.join(MODEL_DIR, "lstm_all_scalers.pkl")
    if os.path.exists(all_scalers_path):
        try:
            with open(all_scalers_path, 'rb') as f:
                scalers = pickle.load(f)
            logger.info(f"Loaded all scalers from {all_scalers_path}")
        except Exception as e:
            logger.error(f"Error loading all scalers: {e}")
    
    # Load individual models and scalers
    for ticker in tickers:
        model_path = os.path.join(MODEL_DIR, f"lstm_{ticker}_model.keras")
        scaler_path = os.path.join(MODEL_DIR, f"lstm_{ticker}_scaler.pkl")
        
        try:
            # Load model if exists
            if os.path.exists(model_path):
                models[ticker] = load_model(model_path)
                logger.info(f"Loaded LSTM model for {ticker}")
                
                # If the ticker scaler wasn't loaded from the combined file
                if ticker not in scalers and os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as f:
                        scalers[ticker] = pickle.load(f)
                    logger.info(f"Loaded scaler for {ticker}")
        except Exception as e:
            logger.error(f"Error loading LSTM model/scaler for {ticker}: {e}")
    
    return models, scalers

def predict_lstm_returns(models, data):
    global scalers
    
    # If scalers dictionary is empty, try to load it
    if not scalers:
        logger.info("Scalers dictionary is empty, attempting to load from disk...")
        _, loaded_scalers = load_lstm_models(data.columns)
        if loaded_scalers:
            logger.info(f"Successfully loaded {len(loaded_scalers)} scalers")
    
    predictions = {}
    for ticker in data.columns:
        try:
            # Skip if we don't have a model for this ticker
            if ticker not in models:
                logger.warning(f"No LSTM model found for {ticker}, skipping prediction")
                continue
                
            # Skip if we don't have a scaler for this ticker
            if ticker not in scalers:
                logger.warning(f"No scaler found for {ticker}, skipping prediction")
                continue
                
            series = data[ticker].dropna()
            if len(series) <= sequence_length:
                logger.warning(f"Not enough data for {ticker} to make LSTM prediction")
                continue
                
            scaler = scalers[ticker]
            scaled_series = scaler.transform(series.values.reshape(-1,1)).flatten()
            
            X_test = scaled_series[-sequence_length:]
            X_test = X_test.reshape((1, sequence_length, 1))
            
            model = models[ticker]
            pred_scaled = model.predict(X_test, verbose=0)[0][0]
            
            # Sometimes prediction can be outside the scaled range, clip it
            pred_scaled = np.clip(pred_scaled, 0, 1)
            
            pred_price = scaler.inverse_transform([[pred_scaled]])[0][0]
            last_price = series.values[-1]
            
            # Sanity check on the prediction
            if pred_price <= 0 or pred_price > last_price * 1.2:  # Cap at 20% up move
                logger.warning(f"Unrealistic prediction for {ticker}: {pred_price} (last: {last_price})")
                return_pct = 0  # Neutral prediction
            else:
                return_pct = (pred_price - last_price) / last_price
                
            predictions[ticker] = [return_pct]
            logger.info(f"LSTM prediction for {ticker}: {return_pct:.4f}")
        except Exception as e:
            logger.error(f"Error predicting LSTM returns for {ticker}: {e}")
            # Provide a neutral prediction in case of error
            predictions[ticker] = [0.0]
    
    return predictions
