import pandas as pd
import requests
from typing import List, Dict
from io import StringIO, BytesIO
import logging
import time
from datetime import datetime, timedelta
import zipfile

logger = logging.getLogger(__name__)

class SP500Fetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_sp500_list(self) -> pd.DataFrame:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            df = pd.read_html(StringIO(response.text))[0]
            df = df[['Symbol', 'Security', 'GICS Sector', 'GICS Sub-Industry']]
            df.columns = ['ticker', 'name', 'sector', 'industry']
            df['ticker'] = df['ticker'].str.replace('.', '-', regex=False)
            logger.info(f"✅ Obtenidas {len(df)} empresas del S&P500")
            return df
        except Exception as e:
            logger.error(f"❌ Error Wikipedia: {str(e)}")
            return self.get_sp500_backup()

    def get_sp500_backup(self) -> pd.DataFrame:
        backup_data = {
            'ticker': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
            'name': ['Apple Inc.', 'Microsoft', 'Alphabet', 'Amazon', 'NVIDIA'],
            'sector': ['Technology', 'Technology', 'Communication', 'Consumer', 'Technology'],
            'industry': ['Electronics', 'Software', 'Internet', 'Retail', 'Semiconductors']
        }
        return pd.DataFrame(backup_data)

    def download_historical_data(self, tickers: List[str], days_back: int = 365) -> Dict[str, pd.DataFrame]:
        """✅ STOOQ.COM: Datos REALES diarios (SIN API KEY)"""
        logger.info(f"📊 STOOQ.COM: {len(tickers)} tickers reales")
        
        result = {}
        
        for i, ticker in enumerate(tickers):  # 100 tickers para velocidad
            try:
                # Stooq CSV directo (US stocks: us/d/)
                url = f"http://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
                
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                df = pd.read_csv(StringIO(response.text))
                
                if len(df) > 10 and 'Date' in df.columns:  # Datos válidos
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.rename(columns={
                        'Open': 'Open', 'High': 'High', 'Low': 'Low',
                        'Close': 'Close', 'Volume': 'Volume'
                    }).set_index('Date')
                    
                    # Solo días hábiles + últimos N días
                    df = df.dropna(subset=['Close']).tail(days_back)
                    
                    if not df.empty:
                        result[ticker] = df[['Open', 'High', 'Low', 'Close', 'Volume']]
                        logger.info(f"✅ {ticker}: {len(df)} días REALES (Stooq)")
                
                time.sleep(0.3)  # Rate limit suave
                
            except Exception as e:
                logger.warning(f"⚠️ Stooq {ticker}: {str(e)[:40]}")
                continue
        
        logger.info(f"✅ Stooq: {len([t for t in result if not result[t].empty])}/100 REALES")
        return result
