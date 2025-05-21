import numpy as np
import pandas as pd
import logging

# Configuración de logging
logger = logging.getLogger("trading_bot")

def generate_signals(data, predictions, threshold=0.005):  # Umbral reducido a 0.5%
    signals = {}
    for ticker, pred in predictions.items():
        signals[ticker] = "BUY" if pred[0] > threshold else "SELL" if pred[0] < -threshold else "HOLD"
    return signals

def apply_risk_controls(signals, data, account_equity, historical_returns, predictions):
    filtered = {}
    max_drawdown_allowed = 0.20  # Aumentado de 0.15 a 0.20 para ser menos restrictivo
    
    # Log para depuración
    logger.info(f"Aplicando control de riesgo a {len(signals)} señales")

    # Calcular drawdown actual
    try:
        cumulative_returns = (1 + historical_returns).cumprod()
        rolling_max = cumulative_returns.cummax()
        drawdown = (rolling_max - cumulative_returns) / rolling_max
        
        # Obtener el máximo drawdown actual (por ticker)
        if not drawdown.empty:
            current_drawdown = drawdown.iloc[-1].max()
            logger.info(f"Drawdown actual: {current_drawdown:.4f}, límite: {max_drawdown_allowed}")
            
            # Verificar si el drawdown excede nuestro límite
            if current_drawdown > max_drawdown_allowed:
                logger.warning(f"⚠️ Drawdown demasiado alto ({current_drawdown:.4f}). No se ejecutarán nuevas operaciones.")
                return filtered  # No operar
    except Exception as e:
        logger.warning(f"Error calculando drawdown: {e}. Continuando con el proceso.")

    # Si no hay posiciones para filtrar, retornamos diccionario vacío
    if not signals:
        logger.warning("No hay señales para filtrar")
        return filtered

    # Procesamos cada señal
    for ticker, signal in signals.items():
        logger.info(f"Evaluando {ticker}: señal {signal}")
        
        if signal == "HOLD":
            logger.info(f"{ticker}: Señal HOLD, omitiendo")
            continue
            
        # Verificar que el ticker esté en los datos
        if ticker not in data.columns:
            logger.warning(f"{ticker} no encontrado en los datos")
            continue

        # Obtenemos los precios de cierre
        closes = data[ticker]
        
        # Para el cálculo de ATR necesitamos más datos que solo el cierre
        # Como solo tenemos precios de cierre, usamos un cálculo simplificado de volatilidad
        volatility = closes.pct_change().rolling(window=14).std().iloc[-1]
        atr_estimate = volatility * closes.iloc[-1]  # Estimación simple del ATR
        
        logger.info(f"{ticker}: Volatilidad {volatility:.4f}, ATR estimado {atr_estimate:.2f}")
        
        # Filtro de volatilidad (evitar activos extremadamente volátiles)
        # Aumentado de 0.03 a 0.05 para ser menos restrictivo
        if volatility > 0.05:  # Más del 5% de volatilidad diaria (antes era 3%)
            logger.info(f"{ticker}: Rechazado por alta volatilidad ({volatility:.4f} > 0.05)")
            continue

        # Filtro de tendencia: solo operar en dirección de la media móvil de 50 días
        # (si hay suficientes datos)
        trend_check_passed = True
        if len(closes) >= 50:
            ma_50 = closes.rolling(window=50).mean().iloc[-1]
            price = closes.iloc[-1]
            
            # Añadimos un margen de tolerancia del 1%
            if signal == "BUY" and price < ma_50 * 0.99:
                logger.info(f"{ticker}: Rechazado por tendencia (precio {price:.2f} < MA50 {ma_50:.2f})")
                trend_check_passed = False
            if signal == "SELL" and price > ma_50 * 1.01:
                logger.info(f"{ticker}: Rechazado por tendencia (precio {price:.2f} > MA50 {ma_50:.2f})")
                trend_check_passed = False
                
        # Si al menos una señal ha estado bloqueada por más de 3 días, 
        # ignoramos los filtros de tendencia (para forzar operaciones)
        if not trend_check_passed:
            # En un sistema real, se implementaría una verificación del tiempo bloqueado
            # Por ahora, solo log informativo
            continue

        # Calcular tamaño máximo permitido de posición (por ejemplo, 2% del capital en riesgo)
        risk_per_trade = 0.02 * account_equity
        stop_loss = atr_estimate  # Usamos nuestra estimación de ATR como distancia SL
        
        # Evitar divisiones por cero
        if stop_loss > 0:
            max_position_size = risk_per_trade / stop_loss
            price = closes.iloc[-1]
            # Aumentamos el peso máximo de posición de 0.2 a 0.25
            max_position_weight = min(0.25, (max_position_size * price) / account_equity)
            
            # En lugar de signal, usamos un valor numérico para la posición
            position_value = max_position_weight if signal == "BUY" else -max_position_weight
            filtered[ticker] = position_value
            logger.info(f"{ticker}: Señal aprobada con peso {position_value:.4f}")

    if not filtered:
        # Si después de todos los filtros aún no tenemos señales, permitimos la señal más fuerte
        # Este es un safety valve para asegurar que siempre habrá al menos una operación
        strongest_signal = None
        max_strength = 0
        
        for ticker, signal in signals.items():
            if signal != "HOLD" and ticker in data.columns:
                # Calculamos la "fuerza" de la señal (puede ser basada en la predicción original)
                strength = abs(predictions.get(ticker, [0])[0])
                if strength > max_strength:
                    max_strength = strength
                    strongest_signal = ticker
        
        if strongest_signal:
            signal = signals[strongest_signal]
            position_value = 0.1 if signal == "BUY" else -0.1  # Posición más pequeña (10% del equity)
            filtered[strongest_signal] = position_value
            logger.info(f"Forzando señal en {strongest_signal} con peso {position_value} (safety valve)")

    logger.info(f"Señales filtradas finales: {filtered}")
    return filtered
