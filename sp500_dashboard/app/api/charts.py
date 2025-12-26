from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.sp500 import Company, DailyPrice
import plotly.graph_objects as go
import pandas as pd

router = APIRouter()

# ✅ FIX: ticker PRIMERO, db DESPUÉS
@router.get("/{ticker}")
async def get_price_chart(ticker: str, db: Session = Depends(get_db)):
    """Gráfico OHLCV"""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Ticker not found")
    
    prices = db.query(DailyPrice).filter(
        DailyPrice.company_id == company.id
    ).order_by(DailyPrice.price_date).limit(365).all()
    
    df_data = []
    for p in prices:
        if p.close:
            df_data.append({
                "date": p.price_date,
                "open": float(p.open) if p.open else float(p.close) * 0.99,
                "high": float(p.high) if p.high else float(p.close) * 1.01,
                "low": float(p.low) if p.low else float(p.close) * 0.98,
                "close": float(p.close),
                "volume": int(p.volume) if p.volume else 0
            })
    
    if not df_data:
        raise HTTPException(status_code=404, detail="No price data")
    
    df = pd.DataFrame(df_data)
    
    fig = go.Figure(data=[
        go.Candlestick(
            x=df['date'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close']
        )
    ])
    
    fig.update_layout(
        title=f"{ticker} - Histórico 1 año",
        template="plotly_dark",
        height=500
    )
    
    return {"chart": fig.to_json()}
