# === /data/data_loader.py ===
import yfinance as yf
import pandas as pd

TICKERS = ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'GLD', 'TLT', 'LQD']

def get_data():
    data = {}
    for ticker in TICKERS:
        df = yf.download(ticker, period="1y", interval="1d")
        data[ticker] = df['Close']
    return pd.DataFrame(data)
