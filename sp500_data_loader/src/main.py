import logging
import sys
import traceback
from pathlib import Path
from .models.predictions import BacktestResult  
from .models.predictions import PortfolioRecommendation

# Database
from .core.database import get_db, engine, Base

# Models (IMPORTAR AQUÍ)
from .models.sp500 import Company, DailyPrice
from .models.predictions import TechnicalIndicator, TradingSignal, MLPrediction

# Services
from .services.data_loader import SP500DataLoader

# SQLAlchemy
from sqlalchemy.orm import Session
from sqlalchemy import text, func

# Config logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_all_tables():
    """Crea TODAS las tablas"""
    logger.info("📊 Creando esquema completo...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tablas creadas")

def main(mode: str = "incremental"):
    """incremental | full | ml_train"""
    create_all_tables()
    
    db = next(get_db())
    loader = SP500DataLoader(db)
    
    try:
        # Actualizar empresas
        logger.info("🏢 Actualizando empresas S&P500...")
        loader.load_companies()
        
        if mode == "full":
            logger.info("🔥 MODO FULL: Carga 5 años")
            loader.load_historical_prices(days_back=1825)
            
        elif mode == "incremental":
            logger.info("🔄 MODO INCREMENTAL: 7 días nuevos")
            loader.load_historical_prices_incremental(days_back=7)
            
        elif mode == "ml_train":
            logger.info("🤖 MODO ML: Entrenar predicciones")
            from .services.ml_predictor import MLPredictor
            predictor = MLPredictor()
            
            # TOP 20 empresas con datos
            companies = db.query(Company.id).join(
                DailyPrice, Company.id == DailyPrice.company_id
            ).group_by(Company.id).limit(20).all()
            
            for company_row in companies:
                company_id = company_row[0]
                predictor.train_predict(db, company_id)
            
            logger.info("✅ ML entrenado!")

        # Añadir al bloque elif:
        elif mode == "backtest":
            logger.info("📊 MODO BACKTEST: Validar estrategia histórica")
            from .services.backtester import Backtester
            bt = Backtester()
            results = bt.backtest_top_stocks(db, limit=20)
            logger.info(f"✅ Backtest completado: {len(results)} empresas analizadas")

        elif mode == "portfolio":
            logger.info("💼 MODO PORTFOLIO: Kelly + Sharpe Optimizer")
            from .services.portfolio_optimizer import PortfolioOptimizer
            optimizer = PortfolioOptimizer()
            recommendations = optimizer.optimize_portfolio(db, top_signals=20)
            if recommendations:
                logger.info(f"✅ Portfolio optimizado: {len(recommendations)} posiciones")
            else:
                logger.warning("⚠️ Sin datos suficientes para portfolio")

                    
        else:
            logger.error(f"❌ Modo inválido: {mode}")
            return
        
        # Stats finales
        stats = db.execute(text("""
            SELECT 
                (SELECT COUNT(*) FROM companies WHERE is_active=1) as empresas,
                (SELECT COUNT(*) FROM prices_daily) as precios,
                COALESCE((SELECT COUNT(*) FROM technical_indicators), 0) as indicadores,
                COALESCE((SELECT COUNT(*) FROM trading_signals), 0) as señales,
                COALESCE((SELECT COUNT(*) FROM ml_predictions), 0) as ml_predicciones
        """)).fetchone()
        
        logger.info(f"📊 ESTADO FINAL:")
        logger.info(f"   🏢 Empresas: {stats[0]}")
        logger.info(f"   💰 Precios: {stats[1]:,}")
        logger.info(f"   📈 Indicadores: {stats[2]}")
        logger.info(f"   🎯 Señales: {stats[3]}")
        logger.info(f"   🤖 ML Predicciones: {stats[4]}")
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    main(mode)
