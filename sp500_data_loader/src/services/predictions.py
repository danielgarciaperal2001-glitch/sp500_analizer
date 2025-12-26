import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from ..models.sp500 import Company
from ..models.predictions import TradingSignal, TechnicalIndicator
from ..core.database import Base, engine
from .indicators import calculate_indicators

logger = logging.getLogger(__name__)

def ensure_tables_exist():
    """✅ Garantiza que tablas existan"""
    Base.metadata.create_all(bind=engine)

def generate_trading_signals(db: Session, top_n: int = 10):
    """Genera señales con chequeo de tablas"""
    ensure_tables_exist()  # ✅ SEGURIDAD EXTRA
    
    companies = db.query(Company).filter(Company.is_active == True).limit(50).all()
    
    for company in companies:
        try:
            calculate_indicators(db, company.id)
        except Exception as e:
            logger.warning(f"⚠️ Skip {company.ticker}: {str(e)[:40]}")
            continue
    
    # Crear señales TOP
    signals = []
    recent_indicators = db.query(
        TechnicalIndicator.company_id,
        func.max(TechnicalIndicator.indicator_date).label('latest_date')
    ).filter(TechnicalIndicator.momentum_score.isnot(None)).group_by(TechnicalIndicator.company_id).subquery()
    
    indicators = db.query(TechnicalIndicator).outerjoin(
        recent_indicators,
        and_(
            TechnicalIndicator.company_id == recent_indicators.c.company_id,
            TechnicalIndicator.indicator_date == recent_indicators.c.latest_date
        )
    ).filter(TechnicalIndicator.momentum_score.isnot(None)).order_by(
        desc(TechnicalIndicator.momentum_score)
    ).limit(top_n * 2).all()
    
    for ind in indicators:
        action = "BUY" if ind.momentum_score > 0.7 else "SELL" if ind.momentum_score < 0.3 else "HOLD"
        
        signal = TradingSignal(
            company_id=ind.company_id,
            signal_date=ind.indicator_date,
            action=action,
            score=float(ind.momentum_score),
            confidence=0.75
        )
        db.add(signal)
        signals.append(signal)
    
    db.commit()
    logger.info(f"🎯 {len(signals)} señales generadas")
    return signals

def get_top_signals(db: Session, limit: int = 10):
    """TOP señales con JOIN"""
    return db.query(TradingSignal, Company).join(
        Company, TradingSignal.company_id == Company.id
    ).order_by(
        desc(TradingSignal.score), desc(TradingSignal.signal_date)
    ).limit(limit).all()
