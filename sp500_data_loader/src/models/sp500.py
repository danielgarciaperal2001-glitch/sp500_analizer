from sqlalchemy import Column, Integer, String, Date, DECIMAL, DATETIME, Boolean, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base
from sqlalchemy.sql import func

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=True)
    industry = Column(String(255), nullable=True)
    exchange = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DATETIME, server_default=func.now())
    updated_at = Column(DATETIME, server_default=func.now(), onupdate=func.now())
    
    # Relación 1:N con precios
    prices = relationship("DailyPrice", back_populates="company", cascade="all, delete-orphan")

class DailyPrice(Base):
    __tablename__ = "prices_daily"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    price_date = Column(Date, nullable=False, index=True)
    
    open = Column(DECIMAL(16, 6), nullable=True)
    high = Column(DECIMAL(16, 6), nullable=True)
    low = Column(DECIMAL(16, 6), nullable=True)
    close = Column(DECIMAL(16, 6), nullable=True)
    adj_close = Column(DECIMAL(16, 6), nullable=True)
    volume = Column(BigInteger, nullable=True)
    
    created_at = Column(DATETIME, server_default=func.now())
    updated_at = Column(DATETIME, server_default=func.now(), onupdate=func.now())
    
    # Relación inversa
    company = relationship("Company", back_populates="prices")
    
    __table_args__ = (
        {"mysql_engine": "InnoDB"},
    )