from sqlalchemy.orm import Session
from ..models.sp500 import Company, DailyPrice
from ..services.sp500_fetcher import MultiSourceFetcher
import pandas as pd
from typing import List
import logging
from sqlalchemy import func

logger = logging.getLogger(__name__)

class SP500DataLoader:
    def __init__(self, db: Session):
        self.db = db
        self.fetcher = MultiSourceFetcher() 
    
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
                    if hasattr(date, 'date'):
                        price_date = date.date()
                    else:
                        price_date = date
                    
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
            
    def load_historical_prices_incremental(self, days_back: int = 7):
        """🔄 CARGA INCREMENTAL: Solo NUEVOS días por ticker"""
        companies = self.db.query(Company).filter(Company.is_active == True).all()
        
        logger.info(f"🔄 Incremental: {len(companies)} tickers (últimos {days_back} días)")
        all_data = self.fetcher.download_historical_data(
            [c.ticker for c in companies], 
            days_back=days_back * 2  # Buffer para solapamiento
        )
        
        total_new_prices = 0
        
        for company in companies:
            ticker = company.ticker
            
            if ticker in all_data and not all_data[ticker].empty:
                prices_df = all_data[ticker]
                
                # Fecha MÁS RECIENTE en DB para este ticker
                last_date_db = self.db.query(
                    func.max(DailyPrice.price_date)
                ).filter(DailyPrice.company_id == company.id).scalar()
                
                new_prices = []
                for date, row in prices_df.iterrows():
                    price_date = date.date() if hasattr(date, 'date') else date
                    
                    # Solo si es NUEVO (después de última fecha DB)
                    if last_date_db is None or price_date > last_date_db:
                        existing = self.db.query(DailyPrice).filter(
                            DailyPrice.company_id == company.id,
                            DailyPrice.price_date == price_date
                        ).first()
                        
                        if not existing:
                            price = DailyPrice(
                                company_id=company.id,
                                price_date=price_date,
                                open=float(row['Open']) if pd.notna(row['Open']) else None,
                                high=float(row['High']) if pd.notna(row['High']) else None,
                                low=float(row['Low']) if pd.notna(row['Low']) else None,
                                close=float(row['Close']) if pd.notna(row['Close']) else None,
                                volume=int(row['Volume']) if pd.notna(row['Volume']) else None
                            )
                            new_prices.append(price)
                
                if new_prices:
                    self.db.add_all(new_prices)
                    total_new_prices += len(new_prices)
                    logger.info(f"💾 {ticker}: +{len(new_prices)} nuevos días (desde {last_date_db or 'inicio'})")
            
            self.db.commit()  # Commit por ticker (seguridad)
        
        logger.info(f"✅ Incremental completado: {total_new_prices:,} nuevos precios")
        return total_new_prices


