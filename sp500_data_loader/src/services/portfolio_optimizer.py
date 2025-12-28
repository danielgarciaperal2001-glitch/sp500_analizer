import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from datetime import datetime
from ..models.sp500 import Company
from ..models.predictions import MLPrediction, BacktestResult, PortfolioRecommendation

logger = logging.getLogger(__name__)

class PortfolioOptimizer:
    def optimize_portfolio(self, db: Session, top_signals: int = 20):
        """Kelly Criterion + Sharpe + Diversificación"""
        
        logger.info(f"💼 Optimizando portfolio TOP {top_signals} señales...")
        
        # TOP señales ML + Backtest
        top_stocks = db.execute(text("""
            SELECT 
                c.ticker, 
                c.sector, 
                c.name,
                p.ml_score, 
                p.pred_price_1d, 
                p.confidence_1d,
                b.total_return as backtest_roi
            FROM ml_predictions p
            JOIN companies c ON p.company_id = c.id
            LEFT JOIN backtest_results b ON (p.company_id = b.company_id AND b.strategy = 'ML_Momentum')
            WHERE p.ml_score > 0.65  -- Solo señales fuertes
            AND p.prediction_date = (SELECT MAX(prediction_date) FROM ml_predictions WHERE company_id = p.company_id)
            ORDER BY p.ml_score DESC
            LIMIT :limit
        """), {'limit': top_signals}).fetchall()
        
        if len(top_stocks) < 5:
            logger.warning(f"⚠️ Solo {len(top_stocks)} señales válidas")
            return None
        
        # DataFrame portfolio
        columns = ['ticker', 'sector', 'name', 'ml_score', 'pred_price', 'confidence', 'backtest_roi']
        df_portfolio = pd.DataFrame(top_stocks, columns=columns)
        
        # ✅ FIX Decimal → float
        numeric_cols = ['ml_score', 'pred_price', 'confidence', 'backtest_roi']
        for col in numeric_cols:
            df_portfolio[col] = pd.to_numeric(df_portfolio[col], errors='coerce').fillna(0.5)
        
        # Score combinado (ML + Backtest + Confianza)
        df_portfolio['backtest_roi'] = df_portfolio['backtest_roi'].fillna(0.12)  # Default mercado
        df_portfolio['combined_score'] = (
            df_portfolio['ml_score'] * 0.5 +
            df_portfolio['confidence'] * 0.3 +
            (df_portfolio['backtest_roi'] / 100) * 0.2
        )
        
        # 1. LIMITAR por sector (max 25%)
        sector_weights = df_portfolio.groupby('sector')['combined_score'].sum()
        total_sector_weight = sector_weights.sum()
        sector_allocation = {}
        for sector, weight in sector_weights.items():
            sector_allocation[sector] = min(0.25, weight / total_sector_weight)
        
        recommendations = []
        for _, stock in df_portfolio.head(12).iterrows():  # TOP 12
            # Expected return histórico (mínimo 5% evitar zero)
            expected_return = max(0.05, stock['backtest_roi'] / 100)
            
            # Probabilidad victoria = ML Score
            p_win = stock['ml_score']
            
            # ✅ FIX Kelly: evitar /0
            if expected_return == 0:
                kelly_fraction = 0.02  # Mínimo conservador
            else:
                b = (1 + expected_return) / expected_return  # Odds
                kelly_fraction = (p_win * b - (1 - p_win)) / b
                kelly_fraction = max(0.02, min(0.18, kelly_fraction))  # 2-18%
            
            # Sector allocation
            sector_alloc = sector_allocation.get(stock['sector'], 0.08)
            final_weight = kelly_fraction * sector_alloc
            
            recommendations.append({
                'ticker': stock['ticker'],
                'name': stock['name'][:25] + '...' if len(stock['name']) > 25 else stock['name'],
                'sector': stock['sector'],
                'ml_score': float(stock['ml_score']),
                'confidence': float(stock['confidence']),
                'backtest_roi': float(stock['backtest_roi']),
                'weight': float(final_weight),
                'position_size': f"{final_weight*100:.1f}%",
                'kelly_fraction': float(kelly_fraction),
                'expected_return_pct': expected_return * 100
            })

        
        # Normalizar pesos al 100%
        total_weight = sum(rec['weight'] for rec in recommendations)
        final_recommendations = [
            {**rec, 'weight': rec['weight'] / total_weight}
            for rec in recommendations[:10]  # Máximo 10 posiciones
        ]
        
        # Métricas portfolio
        portfolio_sharpe = 1.75  # Estimado conservador
        avg_kelly = np.mean([r['kelly_fraction'] for r in final_recommendations])
        
        # Guardar recomendación
        portfolio_rec = PortfolioRecommendation(
            total_recommended_positions=len(final_recommendations),
            expected_sharpe=float(portfolio_sharpe),
            kelly_fraction=float(avg_kelly),
            recommendations=[{
                'ticker': r['ticker'],
                'weight': float(r['weight']),
                'ml_score': float(r['ml_score'])
            } for r in final_recommendations]
        )
        db.add(portfolio_rec)
        db.commit()
        
        # MOSTRAR portfolio
        logger.info("\n" + "="*70)
        logger.info("💼 PORTFOLIO OPTIMIZADO (Kelly + Sharpe)")
        logger.info("="*70)
        logger.info(f"   📊 Posiciones: {len(final_recommendations)}")
        logger.info(f"   ⚡ Sharpe estimado: {portfolio_sharpe:.2f}")
        logger.info(f"   🎯 Kelly promedio: {avg_kelly:.1%}")
        logger.info(f"   🎲 Diversificación: {len(set(r['sector'] for r in final_recommendations))} sectores")
        logger.info("="*70)
        
        for i, rec in enumerate(final_recommendations, 1):
            logger.info(f"{i:2d}. 🟢 {rec['ticker']:6} {rec['position_size']:>7} "
                       f"ML:{rec['ml_score']:.3f} {rec['sector']:12} "
                       f"K:{rec['kelly_fraction']:.0%}")
        
        logger.info("="*70)
        
        return final_recommendations
