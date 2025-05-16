import yfinance as yf
import pandas as pd

TICKERS = ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'GLD', 'TLT', 'LQD']

def get_data():
    """
    Descarga datos históricos de precios para los tickers definidos.
    
    Returns:
        pandas.DataFrame: DataFrame con los precios de cierre de todos los tickers.
    """
    # Primero, descargar datos para el primer ticker para establecer el índice
    first_ticker = TICKERS[0]
    all_data = yf.download(first_ticker, period="1y", interval="1d", auto_adjust=True)
    
    # Inicializar el DataFrame con el primer ticker
    data = pd.DataFrame(index=all_data.index)
    data[first_ticker] = all_data['Close']
    
    # Añadir el resto de tickers
    for ticker in TICKERS[1:]:
        df = yf.download(ticker, period="1y", interval="1d", auto_adjust=True)
        # Usar solo los datos que coinciden con el índice existente
        data[ticker] = df['Close']
    
    return data
