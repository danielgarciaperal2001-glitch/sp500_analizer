import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import logging
from ..models.sp500 import Company, DailyPrice
from ..models.predictions import MLPrediction, BacktestResult  # ✅ CORRECTO

logger = logging.getLogger(__name__)

class Backtester:
    def run_single_stock(self, db: Session, company_id: int, days_back: int = 365):
        """Backtest 1 empresa (ML signals)"""
        company = db.query(Company).get(company_id)
        if not company:
            return None
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"📊 Backtest {company.ticker} ({days_back} días)...")
        
        # Precios período
        prices = db.query(DailyPrice).filter(
            DailyPrice.company_id == company_id,
            DailyPrice.price_date >= start_date
        ).order_by(DailyPrice.price_date).all()
        
        if len(prices) < 50:
            logger.warning(f"⚠️ {company.ticker}: Pocos datos")
            return None
        
        df_prices = pd.DataFrame([{
            'date': p.price_date,
            'close': float(p.close)
        } for p in prices if p.close])
        df_prices.set_index('date', inplace=True)
        
        # ✅ ML Signals (ml_score > 0.7 BUY, < 0.3 SELL)
        ml_signals = db.execute(text("""
            SELECT prediction_date as signal_date, ml_score, pred_price_1d
            FROM ml_predictions 
            WHERE company_id = :company_id 
            AND prediction_date >= :start_date
            AND prediction_date <= :end_date
            ORDER BY prediction_date ASC
        """), {
            'company_id': company_id, 
            'start_date': start_date,
            'end_date': end_date
        }).fetchall()
        
        if not ml_signals:
            logger.warning(f"⚠️ {company.ticker}: Sin señales ML")
            return None
        
        # Simular portfolio $10K
        portfolio_value = 10000.0
        position_shares = 0
        equity_curve = [10000.0]
        trades = []
        
        for signal_date, ml_score, pred_price in ml_signals:
            if signal_date not in df_prices.index:
                continue
                
            current_price = df_prices.loc[signal_date, 'close']
            
            # BUY: ML Score > 0.7
            if ml_score > 0.7 and position_shares == 0:
                position_shares = portfolio_value / current_price
                trades.append(('BUY', signal_date, current_price, ml_score))
                
            # SELL: ML Score < 0.3
            elif ml_score < 0.3 and position_shares > 0:
                portfolio_value = position_shares * current_price
                trades.append(('SELL', signal_date, current_price, ml_score))
                position_shares = 0
            
            # Equity actual (diario)
            current_equity = portfolio_value if position_shares == 0 else position_shares * current_price
            equity_curve.append(current_equity)
        
        # Cierre final (si position abierta)
        final_price = df_prices['close'].iloc[-1]
        final_equity = portfolio_value if position_shares == 0 else position_shares * final_price
        
        # Métricas
        total_return_pct = ((final_equity / 10000.0) - 1) * 100
        
        # Buy&Hold benchmark
        buy_hold_return = ((final_price / df_prices['close'].iloc[0]) - 1) * 100
        
        # Sharpe + Drawdown
        returns_daily = pd.Series(equity_curve).pct_change().dropna()
        sharpe_ratio = returns_daily.mean() / returns_daily.std() * np.sqrt(252) if returns_daily.std() > 0 else 0
        
        peak = pd.Series(equity_curve).cummax()
        drawdown = (peak - equity_curve) / peak * 100
        max_drawdown = drawdown.max()
        
        win_rate = len([t for t in trades if t[0] == 'SELL']) / max(1, len(trades) / 2)
        
        # Guardar resultado
        result = BacktestResult(
            strategy='ML_Momentum',
            company_id=company_id,
            start_date=start_date,
            end_date=end_date,
            total_return=float(total_return_pct),
            sharpe_ratio=float(sharpe_ratio),
            max_drawdown=float(max_drawdown),
            win_rate=float(win_rate),
            total_trades=len(trades)
        )
        db.add(result)
        db.commit()
        
        logger.info(f"📊 {company.ticker}: ML:{total_return_pct:+.1f}% | "
                   f"Buy&Hold:{buy_hold_return:+.1f}% | "
                   f"Alpha:{total_return_pct-buy_hold_return:+.1f}% | "
                   f"Sharpe:{sharpe_ratio:.2f} | Trades:{len(trades)}")
        
        return {
            'ticker': company.ticker,
            'ml_return': total_return_pct,
            'buy_hold': buy_hold_return,
            'alpha': total_return_pct - buy_hold_return,
            'sharpe': sharpe_ratio,
            'trades': len(trades),
            'win_rate': win_rate
        }
    
    def backtest_top_stocks(self, db: Session, limit: int = 20):
        """Backtest TOP 20 empresas con ML"""
        logger.info(f"🚀 BACKTEST MASIVO: {limit} empresas...")
        
        # Empresas con ML predictions
        companies_with_ml = db.execute(text("""
            SELECT DISTINCT c.id 
            FROM companies c
            JOIN ml_predictions p ON c.id = p.company_id
            WHERE c.is_active = 1
            LIMIT :limit
        """), {'limit': limit}).fetchall()
        
        results = []
        for row in companies_with_ml:
            result = self.run_single_stock(db, row[0])
            if result:
                results.append(result)
        
        if not results:
            logger.warning("⚠️ Sin empresas con ML predictions")
            return []
        
        # Estadísticas agregadas
        df_results = pd.DataFrame(results)
        avg_ml = df_results['ml_return'].mean()
        avg_bh = df_results['buy_hold'].mean()
        avg_alpha = df_results['alpha'].mean()
        avg_sharpe = df_results['sharpe'].mean()
        total_trades = df_results['trades'].sum()
        
        logger.info("\n" + "="*60)
        logger.info("📈 RESULTADOS BACKTEST AGREGADOS")
        logger.info("="*60)
        logger.info(f"   🎯 ML Strategy:     {avg_ml:+.1f}%")
        logger.info(f"   📉 Buy&Hold:        {avg_bh:+.1f}%")
        logger.info(f"   ⭐ ALPHA (vs mercado):{avg_alpha:+.1f}%")
        logger.info(f"   ⚡ Sharpe Ratio:    {avg_sharpe:.2f}")
        logger.info(f"   🎲 Total Trades:    {total_trades}")
        logger.info(f"   ✅ Empresas:        {len(results)}")
        logger.info("="*60)
        
        return results
