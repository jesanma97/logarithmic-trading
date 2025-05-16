import os
import json
import pandas as pd
import alpaca_trade_api as tradeapi
import logging
from datetime import datetime
import requests
from utils.environment import ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, TELEGRAM_API_TOKEN, TELEGRAM_CHAT_ID

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("position_monitor")

# Configuración de Alpaca - Usando las variables importadas del módulo environment

# Archivo para almacenar información de las operaciones
TRADE_LOG_FILE = "trade_log.json"

# Función para enviar mensajes a Telegram
def send_telegram_message(message):
    """Envía un mensaje a través de Telegram."""
    try:
        if not TELEGRAM_API_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram API token o chat ID no configurados")
            return False
        
        url = f"https://api.telegram.org/bot{TELEGRAM_API_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error enviando mensaje a Telegram: {e}")
        return False

# Función para cargar el registro de operaciones
def load_trade_log():
    if os.path.exists(TRADE_LOG_FILE):
        try:
            with open(TRADE_LOG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error al decodificar {TRADE_LOG_FILE}. Creando nuevo registro.")
            return {}
    else:
        return {}

# Función para guardar el registro de operaciones
def save_trade_log(trade_log):
    with open(TRADE_LOG_FILE, 'w') as f:
        json.dump(trade_log, f, indent=4)

# Función para actualizar registro desde posiciones actuales en Alpaca
def update_trade_log_from_positions(api, trade_log):
    try:
        positions = api.list_positions()
        for position in positions:
            symbol = position.symbol
            if symbol not in trade_log:
                # Si la posición existe en Alpaca pero no en nuestro log, la añadimos
                entry_price = float(position.avg_entry_price)
                side = 'buy' if position.side == 'long' else 'sell'
                qty = abs(float(position.qty))
                
                # Calcular SL y TP basados en la volatilidad reciente
                df = api.get_bars(symbol, tradeapi.TimeFrame.Day, limit=20).df
                atr = calculate_atr(df)
                
                # Configurar SL y TP basados en ATR
                sl = entry_price * (0.97 if side == 'buy' else 1.03)
                tp = entry_price * (1.05 if side == 'buy' else 0.95)
                
                trade_log[symbol] = {
                    'entry': entry_price,
                    'qty': qty,
                    'side': side,
                    'sl': sl,
                    'tp': tp,
                    'entry_time': datetime.now().isoformat(),
                    'last_update': datetime.now().isoformat()
                }
                
                logger.info(f"Añadida posición encontrada en {symbol}: {side} {qty} @ {entry_price}")
                send_telegram_message(
                    f"🔍 Encontrada posición activa en {symbol}: {side} {qty} @ {entry_price}. "
                    f"SL: {sl:.2f}, TP: {tp:.2f}"
                )
        
        # Eliminar del log posiciones que ya no existen en Alpaca
        alpaca_symbols = [p.symbol for p in positions]
        for symbol in list(trade_log.keys()):
            if symbol not in alpaca_symbols:
                logger.info(f"Eliminando {symbol} del registro porque ya no existe la posición")
                del trade_log[symbol]
                
    except Exception as e:
        logger.error(f"Error al actualizar trade_log desde posiciones: {e}")
    
    return trade_log

# Calcular ATR para determinar volatilidad
def calculate_atr(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]
    return atr

# Función principal de monitoreo
def monitor_positions():
    try:
        api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, api_version='v2')
        
        # Cargar registro de operaciones
        trade_log = load_trade_log()
        
        # Actualizar registro con posiciones actuales en Alpaca
        trade_log = update_trade_log_from_positions(api, trade_log)
        
        # Verificar el estado del mercado
        clock = api.get_clock()
        market_open = clock.is_open
        
        if not market_open:
            logger.info("Mercado cerrado. Posiciones no monitorizadas.")
            return trade_log
        
        # Monitorizar cada posición
        for symbol in list(trade_log.keys()):
            try:
                # Obtener precio actual - Actualizado para usar el método correcto
                try:
                    last_trade = api.get_latest_trade(symbol)
                    price = last_trade.price
                except AttributeError:
                    # Intento alternativo si get_latest_trade no existe
                    try:
                        last_quote = api.get_latest_quote(symbol)
                        price = (last_quote.ask_price + last_quote.bid_price) / 2
                    except:
                        # Último intento usando barras
                        latest_bar = api.get_latest_bar(symbol)
                        price = latest_bar.c
                
                position_data = trade_log[symbol]
                side = position_data['side']
                sl = position_data['sl']
                tp = position_data['tp']
                qty = position_data['qty']
                entry = position_data['entry']
                
                # Calcular ganancias/pérdidas actuales
                pnl_pct = ((price - entry) / entry) * 100
                if side == 'sell':
                    pnl_pct = -pnl_pct
                
                # Verificar si se ha activado SL o TP
                sl_triggered = (side == 'buy' and price <= sl) or (side == 'sell' and price >= sl)
                tp_triggered = (side == 'buy' and price >= tp) or (side == 'sell' and price <= tp)
                
                if sl_triggered or tp_triggered:
                    close_side = 'sell' if side == 'buy' else 'buy'
                    logger.info(f"Ejecutando orden de cierre para {symbol} - {'SL' if sl_triggered else 'TP'} activado")
                    
                    try:
                        # Enviar orden de cierre
                        api.submit_order(
                            symbol=symbol,
                            qty=qty,
                            side=close_side,
                            type='market',
                            time_in_force='day'
                        )
                        
                        action = 'stop-loss' if sl_triggered else 'take-profit'
                        
                        # Mensaje detallado de P&L
                        pnl = (price - entry) * qty
                        if side == 'sell':
                            pnl = -pnl
                        
                        send_telegram_message(
                            f"{'🔴' if sl_triggered else '🟢'} Cierre automático de {symbol} por {action}\n"
                            f"Precio entrada: {entry:.2f}, Precio salida: {price:.2f}\n"
                            f"P&L: {pnl:.2f} USD ({pnl_pct:.2f}%)"
                        )
                        
                        # Eliminar del registro
                        del trade_log[symbol]
                        
                    except Exception as e:
                        logger.error(f"Error cerrando posición en {symbol}: {e}")
                        send_telegram_message(f"⚠️ Error al cerrar {symbol}: {e}")
                
                # Actualizar trailing stops
                adjust_stop_level(trade_log, symbol, side, price, entry)
                
                # Enviar actualizaciones periódicas
                send_position_updates(trade_log, symbol, position_data, price, pnl_pct)
                
            except Exception as e:
                logger.error(f"Error monitoreando {symbol}: {e}")
        
        # Guardar el registro actualizado
        save_trade_log(trade_log)
        return trade_log
        
    except Exception as e:
        logger.error(f"Error en monitor_positions: {e}")
        return trade_log

# Función para ajustar dinámicamente SL basado en movimiento del precio
def adjust_stop_level(trade_log, symbol, side, price, entry):
    try:
        position_data = trade_log[symbol]
        # Trailing stop: Si el precio ha avanzado a nuestro favor más de 3%, 
        # mover el SL para asegurar al menos 1.5% de ganancia
        if side == 'buy':
            if price >= entry * 1.03:  # Si avanzó más de 3% a favor
                new_sl = max(position_data['sl'], entry * 1.015)  # Asegurar al menos 1.5% de ganancia
                if new_sl > position_data['sl']:
                    position_data['sl'] = new_sl
                    logger.info(f"Trailing stop ajustado para {symbol}: nuevo SL {new_sl:.2f}")
                    send_telegram_message(f"🔄 Trailing stop ajustado para {symbol}: nuevo SL {new_sl:.2f}")
        else:  # side == 'sell'
            if price <= entry * 0.97:  # Si avanzó más de 3% a favor (para venta)
                new_sl = min(position_data['sl'], entry * 0.985)  # Asegurar al menos 1.5% de ganancia
                if new_sl < position_data['sl']:
                    position_data['sl'] = new_sl
                    logger.info(f"Trailing stop ajustado para {symbol}: nuevo SL {new_sl:.2f}")
                    send_telegram_message(f"🔄 Trailing stop ajustado para {symbol}: nuevo SL {new_sl:.2f}")
                    
        trade_log[symbol] = position_data
    except Exception as e:
        logger.error(f"Error ajustando stops para {symbol}: {e}")

# Función para enviar actualizaciones periódicas sobre posiciones
def send_position_updates(trade_log, symbol, position_data, price, pnl_pct):
    try:
        # Añadir log cada hora en GitHub Actions para posiciones abiertas
        current_time = datetime.now()
        entry_time = datetime.fromisoformat(position_data.get('entry_time', current_time.isoformat()))
        last_update = datetime.fromisoformat(position_data.get('last_update', entry_time.isoformat()))
        
        minutes_since_update = (current_time - last_update).total_seconds() / 60
        
        if minutes_since_update >= 60:  # Actualizar cada hora
            entry = position_data['entry']
            sl = position_data['sl']
            tp = position_data['tp']
            
            logger.info(f"Actualización de posición en {symbol}: Precio actual {price:.2f}, P&L {pnl_pct:.2f}%")
            send_telegram_message(
                f"📊 Actualización de {symbol}\n"
                f"Entrada: {entry:.2f}, Actual: {price:.2f}\n"
                f"P&L: {pnl_pct:.2f}%\n"
                f"SL: {sl:.2f}, TP: {tp:.2f}"
            )
            trade_log[symbol]['last_update'] = current_time.isoformat()
    except Exception as e:
        logger.error(f"Error enviando actualización para {symbol}: {e}")

if __name__ == "__main__":
    logger.info("Iniciando monitorización de posiciones (GitHub Actions)")
        
    # Ejecutar monitoreo
    trade_log = monitor_positions()
    
    # Guardar registro actualizado
    save_trade_log(trade_log)
    
    logger.info("Monitorización completada")
