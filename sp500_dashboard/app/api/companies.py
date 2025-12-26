from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.database import get_db
from ..models.sp500 import Company

router = APIRouter()

@router.get("/")
async def get_companies(db: Session = Depends(get_db), limit: int = 100):
    """Lista empresas S&P500"""
    companies = db.query(Company).filter(Company.is_active == True).limit(limit).all()
    return [{"id": c.id, "ticker": c.ticker, "name": c.name, "sector": c.sector} for c in companies]

# ✅ NUEVO: Endpoint para TODOS los tickers del selector
@router.get("/tickers")
async def get_all_tickers(db: Session = Depends(get_db)):
    """TODOS los tickers activos para selector (501 empresas)"""
    tickers = db.execute(text("""
        SELECT ticker, name 
        FROM companies 
        WHERE is_active = 1 
        ORDER BY ticker ASC
    """)).fetchall()
    
    return [
        {
            "value": row[0],
            "label": f"{row[0]} - {row[1]}"
        }
        for row in tickers
    ]


@router.get("/{ticker}")
async def get_company_data(ticker: str, db: Session = Depends(get_db)):
    """Datos empresa específica"""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"ticker": company.ticker, "name": company.name, "sector": company.sector}

