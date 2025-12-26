from fastapi import FastAPI, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from .core.database import get_db, Base, engine

app = FastAPI(title="SP500 Trading Dashboard 🚀")

# ✅ STATIC + TEMPLATES
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ✅ IMPORTAR TODOS LOS ROUTERS
from .api.companies import router as companies_router
from .api.charts import router as charts_router
from .api.signals import router as signals_router  # Si existe

# ✅ INCLUIR ROUTERS
app.include_router(companies_router, prefix="/api/companies", tags=["Companies"])
app.include_router(charts_router, prefix="/api/charts", tags=["Charts"])
if 'signals_router' in locals():
    app.include_router(signals_router, prefix="/api/signals", tags=["Signals"])

@app.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Dashboard principal"""
    result = db.execute(text("SELECT ticker FROM companies WHERE is_active = 1 LIMIT 10")).fetchall()
    tickers = [row[0] for row in result]
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tickers": tickers
    })

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
