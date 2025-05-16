import numpy as np
import pandas as pd

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
    
    # Obtener el máximo drawdown actual (por ticker)
    # Usamos .max() para obtener el peor drawdown entre todos los activos
    if not drawdown.empty:
        current_drawdown = drawdown.iloc[-1].max()
        
        # Verificar si el drawdown excede nuestro límite
        if current_drawdown > max_drawdown_allowed:
            print("⚠️ Drawdown demasiado alto. No se ejecutarán nuevas operaciones.")
            return filtered  # No operar

    # Si no hay posiciones para filtrar, retornamos diccionario vacío
    if not signals:
        return filtered

    # Procesamos cada señal
    for ticker, signal in signals.items():
        if signal == "HOLD":
            continue
            
        # Verificar que el ticker esté en los datos
        if ticker not in data.columns:
            continue

        # Obtenemos los precios de cierre
        closes = data[ticker]
        
        # Para el cálculo de ATR necesitamos más datos que solo el cierre
        # Como solo tenemos precios de cierre, usamos un cálculo simplificado de volatilidad
        volatility = closes.pct_change().rolling(window=14).std().iloc[-1]
        atr_estimate = volatility * closes.iloc[-1]  # Estimación simple del ATR
        
        # Filtro de volatilidad (evitar activos extremadamente volátiles)
        if volatility > 0.03:  # Más del 3% de volatilidad diaria
            continue

        # Filtro de tendencia: solo operar en dirección de la media móvil de 50 días
        # (si hay suficientes datos)
        if len(closes) >= 50:
            ma_50 = closes.rolling(window=50).mean().iloc[-1]
            price = closes.iloc[-1]
            if signal == "BUY" and price < ma_50:
                continue
            if signal == "SELL" and price > ma_50:
                continue

        # Calcular tamaño máximo permitido de posición (por ejemplo, 2% del capital en riesgo)
        risk_per_trade = 0.02 * account_equity
        stop_loss = atr_estimate  # Usamos nuestra estimación de ATR como distancia SL
        
        # Evitar divisiones por cero
        if stop_loss > 0:
            max_position_size = risk_per_trade / stop_loss
            price = closes.iloc[-1]
            max_position_weight = min(0.2, (max_position_size * price) / account_equity)
            
            # En lugar de signal, usamos un valor numérico para la posición
            position_value = max_position_weight if signal == "BUY" else -max_position_weight
            filtered[ticker] = position_value

    return filtered
