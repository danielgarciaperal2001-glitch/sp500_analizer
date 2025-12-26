import pandas as pd
import numpy as np
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models.sp500 import Company, DailyPrice
from ..models.predictions import TechnicalIndicator
from ..core.database import Base, engine

def ensure_tables():
    Base.metadata.create_all(bind=engine)

def calculate_indicators(db: Session, company_id: int, days_back: int = 60):
    """Con chequeo de tabla"""
    ensure_tables()  # ✅ SEGURIDAD

logger = logging.getLogger(__name__)

def calculate_indicators(db: Session, company_id: int, days_back: int = 60):
    """Calcula TODOS los indicadores técnicos"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return
    
    prices = db.query(DailyPrice).filter(
        DailyPrice.company_id == company_id
    ).order_by(DailyPrice.price_date.desc()).limit(days_back * 2).all()
    
    if len(prices) < 30:
        logger.warning(f"⏭️ Datos insuficientes para {company.ticker}")
        return
    
    df = pd.DataFrame([
        {
            'date': p.price_date,
            'close': float(p.close) if p.close else 0,
            'high': float(p.high) if p.high else 0,
            'low': float(p.low) if p.low else 0,
            'volume': int(p.volume) if p.volume else 0
        }
        for p in prices
    ]).sort_values('date').reset_index(drop=True)
    
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # RSI (14 días)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9).mean()
    
    # Medias móviles
    sma20 = df['close'].rolling(20).mean()
    sma50 = df['close'].rolling(50).mean()
    
    # Bollinger Bands
    sma20_bb = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    bb_upper = sma20_bb + (std20 * 2)
    bb_lower = sma20_bb - (std20 * 2)
    
    # Volatilidad
    volatility = df['close'].pct_change().rolling(20).std() * 100 * np.sqrt(252)
    
    latest = {
        'rsi': float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None,
        'macd': float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else None,
        'macd_signal': float(macd_signal.iloc[-1]) if not pd.isna(macd_signal.iloc[-1]) else None,
        'sma_20': float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else None,
        'sma_50': float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else None,
        'bb_upper': float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else None,
        'bb_lower': float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else None,
        'volatility': float(volatility.iloc[-1]) if not pd.isna(volatility.iloc[-1]) else None,
    }
    
    # Score momentum
    current_price = float(df['close'].iloc[-1])
    latest['momentum_score'] = calculate_momentum_score(latest, current_price)
    latest['buy_signal'] = latest['momentum_score'] > 0.7 if latest['momentum_score'] else False
    latest['sell_signal'] = latest['momentum_score'] < 0.3 if latest['momentum_score'] else False
    
    # Guardar
    existing = db.query(TechnicalIndicator).filter(
        TechnicalIndicator.company_id == company_id,
        TechnicalIndicator.indicator_date == df.index[-1].date()
    ).first()
    
    if not existing:
        indicator = TechnicalIndicator(company_id=company_id, indicator_date=df.index[-1].date(), **latest)
        db.add(indicator)
        db.commit()
        logger.info(f"📊 {company.ticker}: RSI={latest['rsi']:.1f}, Score={latest['momentum_score']:.3f}")

def calculate_momentum_score(indicators, current_price):
    score = 0
    if indicators['rsi'] and indicators['rsi'] < 30: score += 0.3
    elif indicators['rsi'] and indicators['rsi'] > 70: score -= 0.3
    if indicators['macd'] and indicators['macd_signal'] and indicators['macd'] > indicators['macd_signal']: score += 0.25
    if indicators['sma_20'] and current_price > indicators['sma_20']: score += 0.2
    if indicators['sma_50'] and current_price > indicators['sma_50']: score += 0.15
    if indicators['volatility'] and indicators['volatility'] < 30: score += 0.1
    return max(0, min(1, score))
