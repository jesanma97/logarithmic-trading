import alpaca_trade_api as tradeapi
import os
import json
from datetime import datetime
from utils.telegram_notifier import send_telegram_message
from utils.environment import ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL

# Inicializar la API con las variables importadas
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, api_version='v2')

# Archivo para almacenar información de las operaciones
TRADE_LOG_FILE = "trade_log.json"

def load_trade_log():
    if os.path.exists(TRADE_LOG_FILE):
        try:
            with open(TRADE_LOG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    else:
        return {}

def save_trade_log(trade_log):
    with open(TRADE_LOG_FILE, 'w') as f:
        json.dump(trade_log, f, indent=4)

def execute_trades(positions):
    """
    Ejecuta operaciones basadas en las posiciones calculadas.
    
    Args:
        positions: Diccionario con ticker como clave y peso como valor.
                  Peso positivo = posición larga, negativo = posición corta
    """
    trade_log = load_trade_log()
    
    # Si no hay posiciones para ejecutar, retornamos
    if not positions:
        print("No hay nuevas posiciones para ejecutar")
        return
    
    # Obtener el efectivo disponible en la cuenta
    try:
        cash = float(api.get_account().cash)
    except Exception as e:
        print(f"Error obteniendo información de la cuenta: {e}")
        send_telegram_message(f"⚠️ Error obteniendo información de la cuenta: {e}")
        return
    
    # Ejecutar operaciones para cada ticker
    for ticker, weight in positions.items():
        try:
            # Obtener precio actual - Actualizado para usar el método correcto en la API de Alpaca
            # En versiones recientes se usa get_latest_trade en lugar de get_last_trade
            try:
                last_trade = api.get_latest_trade(ticker)
                price = last_trade.price
            except AttributeError:
                # Intento alternativo si get_latest_trade no existe
                try:
                    last_quote = api.get_latest_quote(ticker)
                    price = (last_quote.ask_price + last_quote.bid_price) / 2
                except:
                    # Último intento usando barras
                    latest_bar = api.get_latest_bar(ticker)
                    price = latest_bar.c
            
            # Calcular cantidad de acciones a comprar/vender
            amount = int((cash * abs(weight)) // price)
            
            # Si la cantidad es 0, no ejecutamos
            if amount <= 0:
                continue
                
            investment = amount * price
            side = 'buy' if weight > 0 else 'sell'
            
            # Ejecutamos la orden
            api.submit_order(
                symbol=ticker,
                qty=amount,
                side=side,
                type='market',
                time_in_force='day'
            )
            
            # Calcular niveles de SL/TP
            sl = price * 0.97 if side == 'buy' else price * 1.03
            tp = price * 1.05 if side == 'buy' else price * 0.95
            
            # Guardar en el registro de operaciones
            trade_log[ticker] = {
                'entry': price,
                'qty': amount,
                'side': side,
                'sl': sl,
                'tp': tp,
                'entry_time': datetime.now().isoformat(),
                'last_update': datetime.now().isoformat()
            }
            
            # Enviar mensaje por Telegram
            action = "comprado" if side == 'buy' else "vendido"
            send_telegram_message(
                f"📈 Operación realizada: {action} {amount} de {ticker} a {price:.2f} USD. "
                f"Inversión: {investment:.2f} USD. SL: {sl:.2f}, TP: {tp:.2f}"
            )
        except Exception as e:
            print(f"Error al operar {ticker}: {e}")
            send_telegram_message(f"⚠️ Error al operar {ticker}: {e}")
    
    # Guardar el registro de operaciones actualizado
    save_trade_log(trade_log)

def close_positions(target_positions):
    """
    Cierra posiciones que ya no están en la lista de posiciones objetivo.
    
    Args:
        target_positions: Diccionario con posiciones objetivo
    """
    trade_log = load_trade_log()
    
    try:
        current_positions = api.list_positions()
    except Exception as e:
        print(f"Error al obtener posiciones actuales: {e}")
        return
        
    for pos in current_positions:
        symbol = pos.symbol
        qty = int(float(pos.qty))
        
        # Si el símbolo no está en posiciones objetivo o tiene peso 0, cerramos
        if symbol not in target_positions or abs(target_positions.get(symbol, 0)) < 0.01:
            side = 'sell' if pos.side == 'long' else 'buy'
            try:
                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    type='market',
                    time_in_force='day'
                )
                
                # Eliminar del registro de operaciones
                if symbol in trade_log:
                    del trade_log[symbol]
                
                send_telegram_message(f"🔴 Cerrada posición en {symbol} ({'venta' if side == 'sell' else 'compra'})")

            except Exception as e:
                print(f"Error al cerrar {symbol}: {e}")
                send_telegram_message(f"⚠️ Error al cerrar {symbol}: {e}")
    
    # Guardar el registro de operaciones actualizado
    save_trade_log(trade_log)
