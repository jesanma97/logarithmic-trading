import alpaca_trade_api as tradeapi
import os
from utils.telegram_notifier import send_telegram_message

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, api_version='v2')

trade_log = {}

def execute_trades(positions):
    global trade_log
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
                trade_log[ticker] = {'entry': price, 'qty': amount, 'side': side, 'sl': sl, 'tp': tp}
                
                # Enviar mensaje por Telegram sobre la compra/venta
                action = "comprado" if side == 'buy' else "vendido"
                send_telegram_message(
                    f"📈 Operación realizada: {action} {amount} de {ticker} a {price:.2f} EUR. "
                    f"Inversión: {investment:.2f} EUR. SL: {sl:.2f}, TP: {tp:.2f}"
                )
        except Exception as e:
            print(f"Error al operar {ticker}: {e}")
            send_telegram_message(f"⚠️ Error al operar {ticker}: {e}")

def close_positions(target_positions):
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
                if symbol in trade_log:
                    del trade_log[symbol]
                send_telegram_message(f"🔴 Cerrada posición en {symbol} ({'venta' if side == 'sell' else 'compra'})")

            except Exception as e:
                print(f"Error al cerrar {symbol}: {e}")
                send_telegram_message(f"⚠️ Error al cerrar {symbol}: {e}")

def monitor_stops():
    global trade_log
    for symbol in list(trade_log):
        try:
            price = api.get_last_trade(symbol).price
            side = trade_log[symbol]['side']
            sl = trade_log[symbol]['sl']
            tp = trade_log[symbol]['tp']
            qty = trade_log[symbol]['qty']
            if (side == 'buy' and (price <= sl or price >= tp)) or (side == 'sell' and (price >= sl or price <= tp)):
                close_side = 'sell' if side == 'buy' else 'buy'
                api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side=close_side,
                    type='market',
                    time_in_force='day'
                )
                action = 'stop-loss' if price <= sl or price >= sl else 'take-profit'
                send_telegram_message(f"⚠️ Cierre automático de {symbol} por {action} (precio actual: {price})")
                del trade_log[symbol]
        except Exception as e:
            print(f"Error monitoreando SL/TP en {symbol}: {e}")
            send_telegram_message(f"⚠️ Error monitoreando SL/TP en {symbol}: {e}")