from sqlalchemy import Column, Integer, String, Date, DECIMAL, DATETIME, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..core.database import Base
from sqlalchemy.sql import func

class TechnicalIndicator(Base):
    __tablename__ = "technical_indicators"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    indicator_date = Column(Date, nullable=False)
    
    # Indicadores
    rsi = Column(DECIMAL(5,2), nullable=True)
    macd = Column(DECIMAL(10,6), nullable=True)
    macd_signal = Column(DECIMAL(10,6), nullable=True)
    sma_20 = Column(DECIMAL(12,6), nullable=True)
    sma_50 = Column(DECIMAL(12,6), nullable=True)
    bb_upper = Column(DECIMAL(12,6), nullable=True)
    bb_lower = Column(DECIMAL(12,6), nullable=True)
    volatility = Column(DECIMAL(6,4), nullable=True)
    
    momentum_score = Column(DECIMAL(5,3), nullable=True)
    buy_signal = Column(Boolean, default=False)
    sell_signal = Column(Boolean, default=False)
    
    created_at = Column(DATETIME, server_default=func.now())
    
    # ✅ FIX: Índices + unique constraint correcto
    __table_args__ = (
        Index('idx_company_date', 'company_id', 'indicator_date'),
        # Unique constraint como tuple correcto
        Index('uq_company_date', 'company_id', 'indicator_date', unique=True),
    )

class TradingSignal(Base):
    __tablename__ = "trading_signals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    signal_date = Column(Date, nullable=False)
    
    predicted_price = Column(DECIMAL(12,6), nullable=True)
    confidence = Column(DECIMAL(5,3), nullable=True)
    action = Column(String(10), nullable=False)
    score = Column(DECIMAL(5,3), nullable=True)
    backtest_roi = Column(DECIMAL(7,4), nullable=True)
    
    created_at = Column(DATETIME, server_default=func.now())
    
    __table_args__ = (
        Index('idx_signal_company_date', 'company_id', 'signal_date'),
    )
