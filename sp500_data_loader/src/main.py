import logging
from .core.database import get_db, engine, Base
from .services.data_loader import SP500DataLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_all_tables():
    """✅ CREA TODAS LAS TABLAS ANTES de cualquier uso"""
    logger.info("📊 Creando TODAS las tablas...")
    
    # Importar TODOS los models para registrar tablas
    from .models.sp500 import Company, DailyPrice
    from .models.predictions import TechnicalIndicator, TradingSignal
    
    Base.metadata.create_all(bind=engine)
    logger.info("✅ ✅ TABLAS CREADAS")

def main():
    logger.info("🚀 SP500 Data Loader + PREDICCIONES")
    
    # ✅ 1. CREAR TABLAS PRIMERO
    create_all_tables()
    
    db = next(get_db())
    loader = SP500DataLoader(db)
    
    try:
        # 2. Datos base
        logger.info("🏢 Cargando empresas...")
        loader.load_companies()
        
        logger.info("📈 Cargando precios...")
        loader.load_historical_prices(days_back=365)
        
        # 3. Predicciones
        logger.info("🎯 Generando indicadores...")
        from .services.predictions import generate_trading_signals, get_top_signals
        signals = generate_trading_signals(db, 501)
        
        # 4. TOP 10
        top_signals = get_top_signals(db, len(signals))
        logger.info(f"🏆 TOP {len(signals)}:")
        print("\n" + "="*80)
        for signal, company in top_signals:
            action_emoji = "🟢" if signal.action == "BUY" else "🔴" if signal.action == "SELL" else "🟡"
            print(f"{action_emoji} {signal.action:<6} {company.ticker:<8} {company.name:<35} Score: {signal.score:.3f}")
        print("="*80)
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
