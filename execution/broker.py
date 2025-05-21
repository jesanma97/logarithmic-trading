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
        account = api.get_account()
        cash = float(account.cash)
        equity = float(account.equity)
        
        # Para calcular correctamente los tamaños de posición usamos el equity total
        available_capital = equity
    except Exception as e:
        print(f"Error obteniendo información de la cuenta: {e}")
        send_telegram_message(f"⚠️ Error obteniendo información de la cuenta: {e}")
        return
    
    # Ejecutar operaciones para cada ticker
    for ticker, weight in positions.items():
        # Omitir si el peso es demasiado pequeño
        if abs(weight) < 0.01:
            continue
            
        try:
            # Determinar el lado de la operación
            side = 'buy' if weight > 0 else 'sell'
            
            # Obtener precio actual - Actualizado para usar el método correcto en la API de Alpaca
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
            
            # Calcular cantidad de acciones a comprar/vender basado en el peso asignado
            target_position_value = available_capital * abs(weight)
            amount = int(target_position_value // price)
            
            # Si la cantidad es 0, no ejecutamos
            if amount <= 0:
                print(f"Cantidad calculada para {ticker} es 0, omitiendo operación")
                continue
                
            investment = amount * price
            
            # Verificar posición actual para no duplicar órdenes
            try:
                current_position = api.get_position(ticker)
                current_qty = int(float(current_position.qty))
                current_side = current_position.side
                
                # Si ya tenemos una posición en la misma dirección, ajustamos la cantidad
                if (side == 'buy' and current_side == 'long') or (side == 'sell' and current_side == 'short'):
                    print(f"Ya existe posición en {ticker} en la misma dirección. Ajustando cantidad.")
                    send_telegram_message(f"ℹ️ Ya existe posición en {ticker}. Ajustando en lugar de abrir nueva.")
                    
                    # Calcular la diferencia en la cantidad
                    if side == 'buy':
                        qty_diff = amount - current_qty
                    else:
                        qty_diff = amount - abs(current_qty)
                    
                    # Si necesitamos ajustar la posición
                    if abs(qty_diff) > 0:
                        adj_side = side if qty_diff > 0 else ('sell' if side == 'buy' else 'buy')
                        api.submit_order(
                            symbol=ticker,
                            qty=abs(qty_diff),
                            side=adj_side,
                            type='market',
                            time_in_force='day'
                        )
                        send_telegram_message(
                            f"🔄 Ajustada posición en {ticker}: {adj_side} {abs(qty_diff)} acciones."
                        )
                    continue
                
                # Si tenemos una posición en dirección opuesta, la cerramos primero
                if (side == 'buy' and current_side == 'short') or (side == 'sell' and current_side == 'long'):
                    print(f"Cerrando posición opuesta en {ticker} antes de abrir nueva.")
                    close_side = 'buy' if current_side == 'short' else 'sell'
                    api.submit_order(
                        symbol=ticker,
                        qty=abs(current_qty),
                        side=close_side,
                        type='market',
                        time_in_force='day'
                    )
                    send_telegram_message(f"🔄 Cerrada posición opuesta en {ticker} antes de abrir nueva.")
                    
            except Exception as e:
                # Si no existe posición, continuamos normalmente
                if "position does not exist" not in str(e).lower():
                    print(f"Error verificando posición actual de {ticker}: {e}")
            
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
