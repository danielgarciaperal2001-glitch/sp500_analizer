from sqlalchemy import Column, Integer, String, Date, DECIMAL, DATETIME, Boolean, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from ..core.database import Base
from sqlalchemy.sql import func
from datetime import datetime

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
    
    __table_args__ = (
        Index('idx_company_date', 'company_id', 'indicator_date'),
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

class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    prediction_date = Column(Date)
    
    # Predicciones ML
    pred_price_1d = Column(DECIMAL(12,6))
    pred_price_5d = Column(DECIMAL(12,6))
    pred_price_20d = Column(DECIMAL(12,6))
    
    confidence_1d = Column(DECIMAL(5,3))  # 0-1
    confidence_5d = Column(DECIMAL(5,3))
    
    accuracy_1d = Column(DECIMAL(5,3))  # Histórica
    accuracy_5d = Column(DECIMAL(5,3))
    
    ml_score = Column(DECIMAL(5,3))  # 0-1 COMBINADO

class BacktestResult(Base):
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True)
    strategy = Column(String(50))
    company_id = Column(Integer, ForeignKey("companies.id"))
    start_date = Column(Date)
    end_date = Column(Date)
    total_return = Column(DECIMAL(10,4))
    sharpe_ratio = Column(DECIMAL(8,4))
    max_drawdown = Column(DECIMAL(8,4))
    win_rate = Column(DECIMAL(5,3))
    total_trades = Column(Integer)
    created_at = Column(DATETIME, default=datetime.utcnow)

class PortfolioRecommendation(Base):
    __tablename__ = "portfolio_recommendations"
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DATETIME, default=datetime.utcnow)
    total_recommended_positions = Column(Integer)
    expected_sharpe = Column(DECIMAL(5,3))
    kelly_fraction = Column(DECIMAL(5,3))
    recommendations = Column(JSON)  # [{"ticker": "NVDA", "weight": 0.12}]