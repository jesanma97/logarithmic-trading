# === /strategy/risk_manager.py ===
def generate_signals(data, predictions, threshold=0.01):
    signals = {}
    for ticker, pred in predictions.items():
        signals[ticker] = "BUY" if pred[0] > threshold else "SELL" if pred[0] < -threshold else "HOLD"
    return signals

def apply_risk_controls(signals, data):
    filtered = {}
    for ticker, signal in signals.items():
        if signal == "HOLD":
            continue

        # Stop-loss dinámico: desviación estándar de los últimos 10 días * factor de riesgo
        returns = data[ticker].pct_change().fillna(0)
        std = returns[-10:].std()
        risk_factor = 2.0
        stop_loss = std * risk_factor

        # Ejemplo de otra medida: evitar señales si el volumen es bajo (si se añadiera volumen al dataset)
        # if data[ticker].volume.mean() < threshold: continue

        filtered[ticker] = {
            "signal": signal,
            "stop_loss": stop_loss,
            "max_position": 0.2  # No más del 20% del capital en un solo activo
        }
    return filtered
