# === /utils/scheduler.py ===
import datetime
import os
import numpy as np
import pandas as pd
from model.predictor import train_model
from model.lstm_model import train_lstm_model

last_trained = None

TRAIN_FILE = "last_trained.txt"

def schedule_training(data, retrain_interval_days=7):
    today = datetime.date.today()

    # Leer última fecha de entrenamiento
    if os.path.exists(TRAIN_FILE):
        with open(TRAIN_FILE, "r") as f:
            last_date = datetime.datetime.strptime(f.read().strip(), "%Y-%m-%d").date()
        delta_days = (today - last_date).days
    else:
        delta_days = retrain_interval_days

    if delta_days >= retrain_interval_days:
        rf_model = train_model(data)
        lstm_model = train_lstm_model(data)
        # Guardar nueva fecha
        with open(TRAIN_FILE, "w") as f:
            f.write(today.strftime("%Y-%m-%d"))
        return rf_model, lstm_model

    return None, None

def combine_predictions(data, rf_preds, lstm_preds, steps=10):
    tickers = rf_preds.keys()
    combined_preds = {}
    for ticker in tickers:
        best_score = -np.inf
        best_alpha = 0.5
        y_true = get_true_returns(data[ticker])
        for alpha in np.linspace(0, 1, steps + 1):
            y_pred = alpha * np.array(rf_preds[ticker]) + (1 - alpha) * np.array(lstm_preds[ticker])
            score = sharpe_ratio(y_pred)
            if score > best_score:
                best_score = score
                best_alpha = alpha
        combined_preds[ticker] = (best_alpha * np.array(rf_preds[ticker]) + (1 - best_alpha) * np.array(lstm_preds[ticker])).tolist()
    return combined_preds

def get_true_returns(series):
    return series.pct_change().fillna(0).values[-len(series):]

def sharpe_ratio(returns, risk_free=0):
    excess_ret = np.array(returns) - risk_free
    return np.mean(excess_ret) / (np.std(excess_ret) + 1e-6)