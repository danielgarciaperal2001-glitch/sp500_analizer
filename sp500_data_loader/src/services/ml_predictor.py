import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sqlalchemy.orm import Session
import logging
from ..models.sp500 import Company, DailyPrice
from ..models.predictions import MLPrediction

logger = logging.getLogger(__name__)

class MLPredictor:
    def __init__(self):
        self.models = {}
        self.scalers = {}
    
    def rsi(self, prices: pd.Series, window: int = 14) -> pd.Series:
        """RSI manual (pandas puro)"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=window).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """30+ features ML profesionales"""
        if 'Close' not in df.columns:
            logger.error(f"❌ DataFrame sin 'Close': {df.columns.tolist()}")
            return pd.DataFrame()
        
        features = pd.DataFrame(index=df.index)
        close = df['Close']
        volume = df['Volume'].fillna(0)
        
        # 1. Price momentum
        features['price'] = close.values
        features['price_change'] = close.pct_change().fillna(0)
        features['price_change_5d'] = close.pct_change(5).fillna(0)
        features['volatility_5'] = close.pct_change().rolling(5).std().fillna(0)
        features['volatility_20'] = close.pct_change().rolling(20).std().fillna(0)
        
        # 2. RSI
        features['rsi_14'] = self.rsi(close, 14)
        features['rsi_7'] = self.rsi(close, 7)
        
        # 3. MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9).mean()
        features['macd'] = (macd_line / close).fillna(0)
        features['macd_signal'] = (macd_signal / close).fillna(0)
        features['macd_histogram'] = features['macd'] - features['macd_signal']
        
        # 4. Medias móviles
        for period in [5, 10, 20, 50]:
            sma = close.rolling(period).mean()
            features[f'sma_ratio_{period}'] = (close / sma).fillna(1.0)
        
        # 5. Bollinger Bands
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = sma20 + (std20 * 2)
        bb_lower = sma20 - (std20 * 2)
        features['bb_position'] = ((close - bb_lower) / (bb_upper - bb_lower)).fillna(0.5)
        
        # 6. Volumen
        vol_sma20 = volume.rolling(20).mean()
        features['volume_ratio'] = (volume / vol_sma20).fillna(1.0)
        
        # 7. Momentum
        features['momentum_5'] = (close / close.shift(5)).fillna(1.0)
        features['momentum_20'] = (close / close.shift(20)).fillna(1.0)
        
        # 8. High-Low range
        features['hl_range'] = (df['High'] - df['Low']) / df['Close']
        features['hl_pct'] = features['hl_range'].rolling(20).mean().fillna(0)
        
        return features.dropna()
    
    def train_predict(self, db: Session, company_id: int, days_back: int = 500):
        """XGBoost completo - Predicción + confianza"""
        company = db.query(Company).get(company_id)
        if not company:
            logger.warning(f"⚠️ Empresa ID {company_id} no encontrada")
            return
        
        logger.info(f"🤖 {company.ticker}...")
        
        # Datos DB
        prices = db.query(DailyPrice).filter(
            DailyPrice.company_id == company_id
        ).order_by(DailyPrice.price_date.asc()).limit(days_back).all()
        
        if len(prices) < 100:
            logger.warning(f"⚠️ {company.ticker}: {len(prices)} días insuficientes")
            return
        
        # DataFrame correcto
        df_data = []
        for p in prices:
            if p.close:
                df_data.append({
                    'date': p.price_date,
                    'Open': float(p.open or p.close),
                    'High': float(p.high or p.close),
                    'Low': float(p.low or p.close),
                    'Close': float(p.close),
                    'Volume': float(p.volume or 0)
                })
        
        df = pd.DataFrame(df_data)
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        
        if len(df) < 100:
            logger.warning(f"⚠️ {company.ticker}: Solo {len(df)} precios válidos")
            return
        
        # Features + Targets
        features = self.prepare_features(df)
        if features.empty or len(features) < 50:
            logger.warning(f"⚠️ {company.ticker}: Features insuficientes")
            return
        
        features['target_1d'] = df['Close'].shift(-1)
        features['target_5d'] = df['Close'].shift(-5)
        
        # Train data
        train_data = features.dropna()
        if len(train_data) < 30:
            logger.warning(f"⚠️ {company.ticker}: Train data insuficiente")
            return
        
        X = train_data.drop(['target_1d', 'target_5d'], axis=1)
        y_1d = train_data['target_1d']
        y_5d = train_data['target_5d']
        
        # ✅ XGBoost PRO
        model_1d = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42
        )
        model_5d = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42
        )
        
        model_1d.fit(X, y_1d)
        model_5d.fit(X, y_5d)
        
        # Predicción RECIENTE ✅ FIX
        last_features = X.iloc[[-1]]  # Última fila válida
        pred_1d = model_1d.predict(last_features)[0]
        pred_5d = model_5d.predict(last_features)[0]
        
        current_price = df['Close'].iloc[-1]
        pred_date = df.index[-1]  # ✅ SIN .date()
        
        # Accuracy histórica (dirección)
        if len(X) > 25:
            test_size = min(25, len(X) // 4)
            X_test = X.iloc[-test_size:]
            y_test = y_1d.iloc[-test_size:]
            prices_test = df['Close'].iloc[-test_size:]
            
            preds = model_1d.predict(X_test)
            direction_correct = np.mean(
                np.sign(preds - prices_test.values) == np.sign(y_test - prices_test.values)
            )
        else:
            direction_correct = 0.5
        
        # ML Score (dirección + momentum)
        change_1d_pct = (pred_1d / current_price - 1)
        ml_score = direction_correct * 0.7 + max(0, min(1, change_1d_pct * 10)) * 0.3
        
        # ✅ GUARDAR (evitar duplicados)
        existing = db.query(MLPrediction).filter(
            MLPrediction.company_id == company_id,
            MLPrediction.prediction_date == pred_date
        ).first()
        
        if not existing:
            prediction = MLPrediction(
                company_id=company_id,
                prediction_date=pred_date,
                pred_price_1d=float(pred_1d),
                pred_price_5d=float(pred_5d),
                confidence_1d=float(direction_correct),
                ml_score=float(ml_score)
            )
            db.add(prediction)
            db.commit()
            
            change_pct = change_1d_pct * 100
            logger.info(f"🤖 {company.ticker}: 1d=${pred_1d:.1f} "
                       f"({change_pct:+.1f}%) C:{direction_correct:.0%} ML:{ml_score:.3f}")
        else:
            logger.info(f"ℹ️ {company.ticker}: Predicción ya existe ({pred_date})")
