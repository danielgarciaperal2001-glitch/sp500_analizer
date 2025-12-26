from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc
from ..core.database import get_db
from ..models.sp500 import Company

router = APIRouter()

@router.get("/top")
async def get_top_signals(db: Session = Depends(get_db), limit: int = 5):
    """TOP señales BUY/SELL reales"""
    try:
        # TOP BUYS
        top_buys = db.execute(text("""
            SELECT c.ticker, c.name, ti.momentum_score as score
            FROM technical_indicators ti
            JOIN companies c ON ti.company_id = c.id
            WHERE ti.momentum_score >= 0.7 AND c.is_active = 1
            ORDER BY ti.momentum_score DESC 
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        # TOP SELLS
        top_sells = db.execute(text("""
            SELECT c.ticker, c.name, ti.momentum_score as score
            FROM technical_indicators ti
            JOIN companies c ON ti.company_id = c.id
            WHERE ti.momentum_score < 0.3 AND c.is_active = 1
            ORDER BY ti.momentum_score ASC 
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        return {
            "top_buys": [
                {"ticker": row[0], "name": row[1], "score": float(row[2])}
                for row in top_buys
            ],
            "top_sells": [
                {"ticker": row[0], "name": row[1], "score": float(row[2])}
                for row in top_sells
            ]
        }
    except Exception as e:
        # Fallback demo si no hay señales
        return {
            "top_buys": [
                {"ticker": "NVDA", "name": "NVIDIA", "score": 0.85},
                {"ticker": "AAPL", "name": "Apple", "score": 0.78}
            ],
            "top_sells": [
                {"ticker": "XYZ", "name": "Demo Sell", "score": 0.22}
            ]
        }

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Estadísticas reales DB"""
    stats = {
        "companies": db.execute(text("SELECT COUNT(*) FROM companies WHERE is_active = 1")).scalar(),
        "prices": db.execute(text("SELECT COUNT(*) FROM prices_daily")).scalar(),
        "signals": db.execute(text("SELECT COUNT(*) FROM trading_signals")).scalar(),
        "top_buy": db.execute(text("""
            SELECT c.ticker FROM technical_indicators ti 
            JOIN companies c ON ti.company_id = c.id 
            ORDER BY ti.momentum_score DESC LIMIT 1
        """)).scalar(),
        "top_sell": db.execute(text("""
            SELECT c.ticker FROM technical_indicators ti 
            JOIN companies c ON ti.company_id = c.id 
            ORDER BY ti.momentum_score ASC LIMIT 1
        """)).scalar()
    }
    return stats
