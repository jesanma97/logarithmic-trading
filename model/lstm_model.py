# === /model/lstm_model.py ===
import numpy as np
import pandas as pd
from keras.models import Sequential
from keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler

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
    for ticker in data.columns:
        series = data[ticker].dropna()
        scaler = MinMaxScaler()
        scaled_series = scaler.fit_transform(series.values.reshape(-1,1)).flatten()
        scalers[ticker] = scaler
        X, y = create_sequences(scaled_series, sequence_length)
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
    return models

def predict_lstm_returns(models, data):
    global scalers
    predictions = {}
    for ticker in data.columns:
        series = data[ticker].dropna()
        scaler = scalers[ticker]
        scaled_series = scaler.transform(series.values.reshape(-1,1)).flatten()
        X_test = scaled_series[-sequence_length:]
        X_test = X_test.reshape((1, sequence_length, 1))
        model = models[ticker]
        pred_scaled = model.predict(X_test, verbose=0)[0][0]
        pred_price = scaler.inverse_transform([[pred_scaled]])[0][0]
        last_price = series.values[-1]
        return_pct = (pred_price - last_price) / last_price
        predictions[ticker] = [return_pct]
    return predictions