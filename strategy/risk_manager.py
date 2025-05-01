import numpy as np

def generate_signals(data, predictions, threshold=0.01):
    signals = {}
    for ticker, pred in predictions.items():
        signals[ticker] = "BUY" if pred[0] > threshold else "SELL" if pred[0] < -threshold else "HOLD"
    return signals

def apply_risk_controls(signals, data, account_equity, historical_returns):
    filtered = {}
    max_drawdown_allowed = 0.15  # Máximo drawdown permitido antes de frenar operaciones

    # Calcular drawdown actual
    cumulative_returns = (1 + historical_returns).cumprod()
    rolling_max = cumulative_returns.cummax()
    drawdown = (rolling_max - cumulative_returns) / rolling_max
    current_drawdown = drawdown.iloc[-1]

    if current_drawdown > max_drawdown_allowed:
        print("⚠️ Drawdown demasiado alto. No se ejecutarán nuevas operaciones.")
        return filtered  # No operar

    for ticker, signal in signals.items():
        if signal == "HOLD":
            continue

        df = data[ticker]
        closes = df['close']

        # ATR (Average True Range) como mejor indicador de riesgo
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        # Filtro de volatilidad (evitar activos extremadamente volátiles)
        if atr / closes.iloc[-1] > 0.1:  # Volatilidad mayor al 10%
            continue

        # Filtro de tendencia: solo operar en dirección de la media móvil de 50 días
        ma_50 = closes.rolling(window=50).mean().iloc[-1]
        price = closes.iloc[-1]
        if signal == "BUY" and price < ma_50:
            continue
        if signal == "SELL" and price > ma_50:
            continue

        # Calcular tamaño máximo permitido de posición (por ejemplo, 2% del capital en riesgo)
        risk_per_trade = 0.02 * account_equity
        stop_loss = atr  # Usamos ATR como distancia SL
        max_position_size = risk_per_trade / stop_loss
        max_position_weight = min(0.2, (max_position_size * price) / account_equity)

        filtered[ticker] = {
            "signal": signal,
            "stop_loss": stop_loss,
            "max_position": max_position_weight
        }

    return filtered
