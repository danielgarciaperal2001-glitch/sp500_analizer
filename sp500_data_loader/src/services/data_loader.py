from sqlalchemy.orm import Session
from ..models.sp500 import Company, DailyPrice
from ..services.sp500_fetcher import SP500Fetcher
import pandas as pd
from typing import List
import logging
from sqlalchemy import func

logger = logging.getLogger(__name__)

class SP500DataLoader:
    def __init__(self, db: Session):
        self.db = db
        self.fetcher = SP500Fetcher()
    
    def create_schema(self):
        """Crea el esquema si no existe"""
        from ..core.database import Base
        Base.metadata.create_all(bind=self.db.bind)
        logger.info("📊 Esquema de base de datos creado/existe")
    
    def load_companies(self) -> List[Company]:
        """Carga/actualiza lista de empresas S&P500"""
        sp500_df = self.fetcher.get_sp500_list()
        
        existing_tickers = {
            c.ticker for c in self.db.query(Company.ticker).all()
        }
        
        new_companies = []
        updated_companies = []
        
        for _, row in sp500_df.iterrows():
            company = self.db.query(Company).filter(Company.ticker == row['ticker']).first()
            
            if company:
                # Actualizar si cambió algo
                if (company.name != row['name'] or 
                    company.sector != row['sector'] or 
                    company.industry != row['industry']):
                    company.name = row['name']
                    company.sector = row['sector']
                    company.industry = row['industry']
                    company.is_active = True
                    updated_companies.append(company)
            else:
                # Nueva empresa
                company = Company(
                    ticker=row['ticker'],
                    name=row['name'],
                    sector=row['sector'],
                    industry=row['industry'],
                    exchange='NYSE/NASDAQ',
                    is_active=True
                )
                self.db.add(company)
                new_companies.append(company)
        
        # Desactivar empresas que ya no están en S&P500
        inactive_companies = self.db.query(Company).filter(
            Company.ticker.notin_(sp500_df['ticker'].tolist()),
            Company.is_active == True
        ).update({Company.is_active: False}, synchronize_session=False)
        
        self.db.commit()
        logger.info(f"📈 Nuevas: {len(new_companies)}, Actualizadas: {len(updated_companies)}, Inactivas: {inactive_companies}")
        logger.info(f"🏢 Total empresas activas: {len(sp500_df)}")
        return new_companies
    
    def load_historical_prices(self, days_back: int = 365):
        """Carga precios históricos"""
        companies = self.db.query(Company).filter(Company.is_active == True).all()
        tickers = [c.ticker for c in companies]
        
        logger.info(f"📦 Batch download {len(tickers)} tickers ({days_back} días)")
        all_data = self.fetcher.download_historical_data(tickers, days_back=days_back)
        
        total_prices = 0
        failed_tickers = []
        
        for company in companies:
            if company.ticker in all_data and not all_data[company.ticker].empty:
                prices_df = all_data[company.ticker]
                
                batch_prices = []
                for date, row in prices_df.iterrows():
                    # ✅ FIX: Manejo correcto de fecha
                    if hasattr(date, 'date'):
                        price_date = date.date()
                    else:
                        price_date = date  # Ya es date
                    
                    # Verificar duplicados
                    existing = self.db.query(DailyPrice).filter(
                        DailyPrice.company_id == company.id,
                        DailyPrice.price_date == price_date
                    ).first()
                    
                    if not existing:
                        price = DailyPrice(
                            company_id=company.id,
                            price_date=price_date,
                            open=(float(row['Open']) if 'Open' in row and pd.notna(row['Open']) else None),
                            high=(float(row['High']) if 'High' in row and pd.notna(row['High']) else None),
                            low=(float(row['Low']) if 'Low' in row and pd.notna(row['Low']) else None),
                            close=(float(row['Close']) if 'Close' in row and pd.notna(row['Close']) else None),
                            volume=(int(row['Volume']) if 'Volume' in row and pd.notna(row['Volume']) else None)
                        )
                        batch_prices.append(price)
                
                if batch_prices:
                    self.db.add_all(batch_prices)
                    total_prices += len(batch_prices)
                    logger.info(f"💾 {company.ticker}: {len(batch_prices)} nuevos días")
                
                self.db.commit()
            else:
                failed_tickers.append(company.ticker)
        
        logger.info(f"✅ Total precios guardados: {total_prices:,}")
        if failed_tickers:
            logger.warning(f"⚠️ Sin datos: {len(failed_tickers)} tickers")

