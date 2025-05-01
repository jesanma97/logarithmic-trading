# === /model/predictor.py ===
from sklearn.ensemble import RandomForestRegressor
import numpy as np

model = None

def train_model(data):
    global model
    X, y = [], []
    for ticker in data.columns:
        series = data[ticker].pct_change().fillna(0)
        for i in range(20, len(series) - 1):
            features = [
                np.mean(series[i-5:i]),
                np.std(series[i-5:i]),
                np.mean(series[i-10:i]),
                np.std(series[i-10:i])
            ]
            X.append(features)
            y.append(series[i+1])
    model = RandomForestRegressor(n_estimators=100)
    model.fit(X, y)
    return model

def predict_returns(model, data):
    predictions = {}
    for ticker in data.columns:
        series = data[ticker].pct_change().fillna(0)
        features = [
            np.mean(series[-5:]),
            np.std(series[-5:]),
            np.mean(series[-10:]),
            np.std(series[-10:])
        ]
        prediction = model.predict([features])[0]
        predictions[ticker] = [prediction]
    return predictions