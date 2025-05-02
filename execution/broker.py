import alpaca_trade_api as tradeapi
import os
import json
from datetime import datetime
from utils.telegram_notifier import send_telegram_message

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("BASE_URL", "https://paper-api.alpaca.markets")

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
    trade_log = load_trade_log()
    
    current_date = positions.index[-1]
    row = positions.loc[current_date]
    
    for ticker, weight in row.items():
        try:
            price = api.get_last_trade(ticker).price
            cash = float(api.get_account().cash)
            amount = int((cash * abs(weight)) // price)
            investment = amount * price
            
            if amount > 0:
                side = 'buy' if weight > 0 else 'sell'
                
                # Ejecutamos la orden de compra o venta
                api.submit_order(
                    symbol=ticker,
                    qty=amount,
                    side=side,
                    type='market',
                    time_in_force='day'
                )
                
                # Registrar precio de entrada y niveles de SL/TP
                sl = price * 0.97 if side == 'buy' else price * 1.03
                tp = price * 1.05 if side == 'buy' else price * 0.95
                
                # Guardar en el registro de operaciones para el monitor continuo
                trade_log[ticker] = {
                    'entry': price,
                    'qty': amount,
                    'side': side,
                    'sl': sl,
                    'tp': tp,
                    'entry_time': datetime.now().isoformat(),
                    'last_update': datetime.now().isoformat()
                }
                
                # Enviar mensaje por Telegram sobre la compra/venta
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
    trade_log = load_trade_log()
    
    current_positions = api.list_positions()
    for pos in current_positions:
        symbol = pos.symbol
        qty = int(float(pos.qty))
        target_weight = target_positions.iloc[-1].get(symbol, 0)
        
        if target_weight == 0:
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