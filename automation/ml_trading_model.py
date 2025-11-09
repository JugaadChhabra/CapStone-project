#!/usr/bin/env python3
"""
Advanced ML Trading Model

PURPOSE: Implements sophisticated machine learning models for trading signal generation
FEATURES:
- Multiple ML algorithms (RandomForest, XGBoost, Neural Networks)
- Advanced feature engineering for stock market data
- Model training pipeline with proper validation
- Feature importance analysis
- Model persistence and loading

USAGE: python ml_trading_model.py
"""

import pandas as pd
import numpy as np
import pickle
import joblib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ML Libraries
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
    from sklearn.feature_selection import SelectKBest, f_classif
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    logging.warning("XGBoost not available, using sklearn only")

try:
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import Dense, LSTM, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False
    logging.warning("TensorFlow not available, using sklearn only")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AdvancedFeatureEngineering:
    """Advanced feature engineering for trading data"""
    
    @staticmethod
    def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate comprehensive technical indicators"""
        data = df.copy()
        
        # Moving averages
        for period in [5, 10, 20, 50]:
            data[f'sma_{period}'] = data['close'].rolling(window=period).mean()
            data[f'ema_{period}'] = data['close'].ewm(span=period).mean()
        
        # Price momentum indicators
        for period in [1, 3, 5, 10]:
            data[f'price_change_{period}'] = data['close'].pct_change(periods=period)
            data[f'price_momentum_{period}'] = data['close'] / data['close'].shift(period) - 1
        
        # Volatility indicators
        for period in [5, 10, 20]:
            data[f'volatility_{period}'] = data['close'].rolling(window=period).std()
            data[f'atr_{period}'] = data[['high', 'low', 'close']].apply(
                lambda x: max(x['high'] - x['low'], 
                            abs(x['high'] - x['close']), 
                            abs(x['low'] - x['close'])), axis=1
            ).rolling(window=period).mean()
        
        # RSI
        for period in [14, 21]:
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            data[f'rsi_{period}'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = data['close'].ewm(span=12).mean()
        ema_26 = data['close'].ewm(span=26).mean()
        data['macd'] = ema_12 - ema_26
        data['macd_signal'] = data['macd'].ewm(span=9).mean()
        data['macd_histogram'] = data['macd'] - data['macd_signal']
        
        # Bollinger Bands
        for period in [20]:
            sma = data['close'].rolling(window=period).mean()
            std = data['close'].rolling(window=period).std()
            data[f'bb_upper_{period}'] = sma + (std * 2)
            data[f'bb_lower_{period}'] = sma - (std * 2)
            data[f'bb_position_{period}'] = (data['close'] - data[f'bb_lower_{period}']) / (data[f'bb_upper_{period}'] - data[f'bb_lower_{period}'])
        
        # Williams %R
        for period in [14]:
            highest_high = data['high'].rolling(window=period).max()
            lowest_low = data['low'].rolling(window=period).min()
            data[f'williams_r_{period}'] = -100 * (highest_high - data['close']) / (highest_high - lowest_low)
        
        # Stochastic Oscillator
        for period in [14]:
            lowest_low = data['low'].rolling(window=period).min()
            highest_high = data['high'].rolling(window=period).max()
            data[f'stoch_k_{period}'] = 100 * (data['close'] - lowest_low) / (highest_high - lowest_low)
            data[f'stoch_d_{period}'] = data[f'stoch_k_{period}'].rolling(window=3).mean()
        
        return data
    
    @staticmethod
    def calculate_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate volume-based indicators"""
        data = df.copy()
        
        # Volume moving averages
        for period in [5, 10, 20]:
            data[f'volume_sma_{period}'] = data['volume'].rolling(window=period).mean()
            data[f'volume_ratio_{period}'] = data['volume'] / data[f'volume_sma_{period}']
        
        # Price Volume Trend (PVT)
        data['price_change'] = data['close'].pct_change()
        data['pvt'] = (data['price_change'] * data['volume']).cumsum()
        
        # On Balance Volume (OBV)
        data['price_direction'] = np.where(data['close'] > data['close'].shift(1), 1, 
                                         np.where(data['close'] < data['close'].shift(1), -1, 0))
        data['obv'] = (data['volume'] * data['price_direction']).cumsum()
        
        # Volume Price Confirmation Number (VPCN)
        data['vpcn'] = data['volume'] * data['close']
        
        # Money Flow Index (MFI)
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        money_flow = typical_price * data['volume']
        
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window=14).sum()
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window=14).sum()
        
        money_ratio = positive_flow / negative_flow
        data['mfi'] = 100 - (100 / (1 + money_ratio))
        
        return data
    
    @staticmethod
    def calculate_market_microstructure(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate market microstructure features"""
        data = df.copy()
        
        # Bid-ask spread proxy (high-low spread)
        data['spread'] = data['high'] - data['low']
        data['spread_pct'] = data['spread'] / data['close']
        
        # Price efficiency measures
        data['efficiency'] = abs(data['close'] - data['open']) / (data['high'] - data['low'])
        
        # Gap analysis
        data['gap'] = data['open'] - data['close'].shift(1)
        data['gap_pct'] = data['gap'] / data['close'].shift(1)
        
        # Intraday patterns
        data['intraday_return'] = (data['close'] - data['open']) / data['open']
        data['overnight_return'] = (data['open'] - data['close'].shift(1)) / data['close'].shift(1)
        
        # Price position within the day's range
        data['price_position'] = (data['close'] - data['low']) / (data['high'] - data['low'])
        
        return data
    
    @staticmethod
    def calculate_time_features(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate time-based features"""
        data = df.copy()
        
        # Ensure datetime column exists
        if 'datetime' in data.columns:
            dt_col = 'datetime'
        elif 'time' in data.columns:
            # Convert time string to datetime for feature extraction
            data['datetime'] = pd.to_datetime(data['date'] + ' ' + data['time'])
            dt_col = 'datetime'
        else:
            return data
        
        # Time features
        data['hour'] = pd.to_datetime(data[dt_col]).dt.hour
        data['minute'] = pd.to_datetime(data[dt_col]).dt.minute
        data['day_of_week'] = pd.to_datetime(data[dt_col]).dt.dayofweek
        
        # Market session indicators
        data['is_market_open'] = ((data['hour'] == 9) & (data['minute'] >= 15)).astype(int)
        data['is_opening_session'] = ((data['hour'] == 9) & (data['minute'] <= 45)).astype(int)
        data['is_midday_session'] = ((data['hour'] >= 11) & (data['hour'] <= 14)).astype(int)
        data['is_closing_session'] = ((data['hour'] == 15) & (data['minute'] <= 30)).astype(int)
        
        # Time since market open
        market_open_time = 9 * 60 + 15  # 9:15 AM in minutes
        current_time_minutes = data['hour'] * 60 + data['minute']
        data['time_since_open'] = current_time_minutes - market_open_time
        data['time_since_open'] = np.where(data['time_since_open'] < 0, 0, data['time_since_open'])
        
        return data
    
    def create_comprehensive_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create comprehensive feature set"""
        # Apply all feature engineering methods
        data = self.calculate_technical_indicators(df)
        data = self.calculate_volume_indicators(data)
        data = self.calculate_market_microstructure(data)
        data = self.calculate_time_features(data)
        
        return data

class TradingMLModel:
    """Main ML model for trading signal generation"""
    
    def __init__(self, model_type: str = 'random_forest'):
        self.logger = logging.getLogger(__name__)
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_selector = None
        self.feature_columns = None
        self.label_encoder = LabelEncoder()
        self.feature_engineer = AdvancedFeatureEngineering()
        
        # Model parameters
        self.model_params = {
            'random_forest': {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42
            },
            'xgboost': {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'random_state': 42
            },
            'gradient_boost': {
                'n_estimators': 100,
                'max_depth': 5,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'random_state': 42
            }
        }
    
    def prepare_data(self, df: pd.DataFrame, target_col: str = None, create_target: bool = True) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare data for training"""
        # Create comprehensive features
        data = self.feature_engineer.create_comprehensive_features(df)
        
        # Create target variable if not provided and we're in training mode
        if create_target and (target_col is None or target_col not in data.columns):
            data = self.create_target_variable(data)
            target_col = 'target'
        
        # Select feature columns (exclude non-feature columns)
        exclude_cols = ['date', 'time', 'datetime', 'stock_code', 'exchange_name']
        if target_col:
            exclude_cols.append(target_col)
        
        # Also exclude future-looking columns during inference
        if not create_target:
            exclude_cols.extend(['target', 'future_return'])
            
        feature_cols = [col for col in data.columns if col not in exclude_cols]
        
        # Handle missing values
        X = data[feature_cols].fillna(method='bfill').fillna(method='ffill').fillna(0)
        
        if target_col and target_col in data.columns:
            y = data[target_col]
            # Remove rows where target is NaN
            valid_indices = ~y.isna()
            X = X[valid_indices]
            y = y[valid_indices]
        else:
            y = pd.Series([0] * len(X))  # Dummy target for inference
        
        self.feature_columns = feature_cols
        
        return X, y
    
    def create_target_variable(self, df: pd.DataFrame, 
                             lookahead_periods: int = 5,
                             threshold: float = 0.02) -> pd.DataFrame:
        """Create target variable for prediction"""
        data = df.copy()
        
        # Calculate future returns
        data['future_return'] = data['close'].shift(-lookahead_periods) / data['close'] - 1
        
        # Create target labels
        # 1: Strong Buy (future return > threshold)
        # 0: Hold (-threshold <= future return <= threshold)
        # -1: Strong Sell (future return < -threshold)
        
        data['target'] = np.where(
            data['future_return'] > threshold, 1,
            np.where(data['future_return'] < -threshold, -1, 0)
        )
        
        return data
    
    def initialize_model(self):
        """Initialize the ML model"""
        if self.model_type == 'random_forest':
            self.model = RandomForestClassifier(**self.model_params['random_forest'])
        
        elif self.model_type == 'xgboost' and HAS_XGBOOST:
            self.model = xgb.XGBClassifier(**self.model_params['xgboost'])
        
        elif self.model_type == 'gradient_boost':
            self.model = GradientBoostingClassifier(**self.model_params['gradient_boost'])
        
        elif self.model_type == 'lstm' and HAS_TENSORFLOW:
            self.model = self.create_lstm_model()
        
        else:
            self.logger.warning(f"Model type {self.model_type} not available, using Random Forest")
            self.model = RandomForestClassifier(**self.model_params['random_forest'])
    
    def create_lstm_model(self, sequence_length: int = 20, n_features: int = 50):
        """Create LSTM model for time series prediction"""
        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(sequence_length, n_features)),
            Dropout(0.2),
            LSTM(50, return_sequences=False),
            Dropout(0.2),
            Dense(25),
            Dense(3, activation='softmax')  # 3 classes: -1, 0, 1
        ])
        
        model.compile(optimizer=Adam(learning_rate=0.001), 
                     loss='categorical_crossentropy', 
                     metrics=['accuracy'])
        
        return model
    
    def train_model(self, X: pd.DataFrame, y: pd.Series, 
                   test_size: float = 0.2, 
                   feature_selection: bool = True,
                   cross_validate: bool = True):
        """Train the ML model"""
        self.logger.info(f"🚀 Training {self.model_type} model...")
        
        # Initialize model
        self.initialize_model()
        
        # Encode target variable to ensure proper class labels
        y_encoded = self.label_encoder.fit_transform(y)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=test_size, random_state=42, stratify=y_encoded
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Feature selection
        if feature_selection:
            self.feature_selector = SelectKBest(f_classif, k=min(50, X_train.shape[1]))
            X_train_scaled = self.feature_selector.fit_transform(X_train_scaled, y_train)
            X_test_scaled = self.feature_selector.transform(X_test_scaled)
        
        # Train model
        if self.model_type == 'lstm' and HAS_TENSORFLOW:
            # Reshape for LSTM
            X_train_lstm = self.prepare_lstm_sequences(X_train_scaled)
            X_test_lstm = self.prepare_lstm_sequences(X_test_scaled)
            
            # Convert target to categorical
            from tensorflow.keras.utils import to_categorical
            y_train_cat = to_categorical(y_train, num_classes=3)
            y_test_cat = to_categorical(y_test, num_classes=3)
            
            # Train LSTM
            callbacks = [
                EarlyStopping(patience=10, restore_best_weights=True),
                ModelCheckpoint('best_lstm_model.h5', save_best_only=True)
            ]
            
            history = self.model.fit(
                X_train_lstm, y_train_cat,
                validation_data=(X_test_lstm, y_test_cat),
                epochs=100,
                batch_size=32,
                callbacks=callbacks,
                verbose=0
            )
            
        else:
            # Train sklearn models
            self.model.fit(X_train_scaled, y_train)
        
        # Cross-validation
        if cross_validate and self.model_type != 'lstm':
            cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5, scoring='accuracy')
            self.logger.info(f"📊 Cross-validation accuracy: {cv_scores.mean():.3f} (+/- {cv_scores.std() * 2:.3f})")
        
        # Evaluate on test set
        if self.model_type == 'lstm':
            test_loss, test_accuracy = self.model.evaluate(X_test_lstm, y_test_cat, verbose=0)
            self.logger.info(f"📈 Test accuracy: {test_accuracy:.3f}")
        else:
            y_pred = self.model.predict(X_test_scaled)
            accuracy = accuracy_score(y_test, y_pred)
            self.logger.info(f"📈 Test accuracy: {accuracy:.3f}")
            
            # Classification report
            self.logger.info("\n📊 Classification Report:")
            print(classification_report(y_test, y_pred, 
                                       target_names=['Sell', 'Hold', 'Buy']))
        
        # Feature importance (for tree-based models)
        if hasattr(self.model, 'feature_importances_'):
            self.log_feature_importance(X.columns)
        
        self.logger.info("✅ Model training completed")
    
    def prepare_lstm_sequences(self, X: np.ndarray, sequence_length: int = 20):
        """Prepare sequences for LSTM training"""
        sequences = []
        for i in range(sequence_length, len(X)):
            sequences.append(X[i-sequence_length:i])
        return np.array(sequences)
    
    def log_feature_importance(self, feature_names: List[str], top_n: int = 20):
        """Log top feature importances"""
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            
            # Adjust for feature selection
            if self.feature_selector is not None:
                selected_features = self.feature_selector.get_support()
                full_importances = np.zeros(len(feature_names))
                full_importances[selected_features] = importances
                importances = full_importances
            
            # Get top features
            feature_importance_df = pd.DataFrame({
                'feature': feature_names,
                'importance': importances
            }).sort_values('importance', ascending=False)
            
            self.logger.info(f"\n🔍 Top {top_n} Most Important Features:")
            for i, row in feature_importance_df.head(top_n).iterrows():
                self.logger.info(f"  {row['feature']}: {row['importance']:.4f}")
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions"""
        if self.model is None:
            raise ValueError("Model not trained yet!")
        
        # Create features from the input data (without target variable)
        X_with_features = self.feature_engineer.create_comprehensive_features(X)
        
        # Select only the feature columns that were used during training
        # Exclude target and metadata columns
        exclude_cols = ['date', 'time', 'datetime', 'stock_code', 'exchange_name', 'target', 'future_return']
        available_feature_cols = [col for col in self.feature_columns if col in X_with_features.columns and col not in exclude_cols]
        
        if not available_feature_cols:
            # Fallback to basic prediction if no features available
            return np.array([0])
        
        X_features = X_with_features[available_feature_cols]
        X_features = X_features.fillna(method='bfill').fillna(method='ffill').fillna(0)
        
        # Handle case where we have fewer features than expected
        if len(available_feature_cols) < len(self.feature_columns):
            # Create a DataFrame with all expected features, filling missing ones with 0
            missing_cols = [col for col in self.feature_columns if col not in available_feature_cols and col not in exclude_cols]
            for col in missing_cols:
                X_features[col] = 0
            
            # Reorder columns to match training order
            feature_order = [col for col in self.feature_columns if col not in exclude_cols]
            X_features = X_features[feature_order]
        
        # Scale features
        X_scaled = self.scaler.transform(X_features)
        
        # Feature selection
        if self.feature_selector is not None:
            X_scaled = self.feature_selector.transform(X_scaled)
        
        # Make predictions
        if self.model_type == 'lstm':
            X_lstm = self.prepare_lstm_sequences(X_scaled)
            if len(X_lstm) == 0:
                return np.array([0])  # Return hold signal if insufficient data
            predictions = self.model.predict(X_lstm)
            # Convert probabilities to class predictions
            predictions = np.argmax(predictions, axis=1)
            # Map back to original labels
            return self.label_encoder.inverse_transform(predictions)
        else:
            predictions = self.model.predict(X_scaled)
            return self.label_encoder.inverse_transform(predictions)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get prediction probabilities"""
        if self.model is None:
            raise ValueError("Model not trained yet!")
        
        # Create features from the input data (without target variable)
        X_with_features = self.feature_engineer.create_comprehensive_features(X)
        
        # Select only the feature columns that were used during training
        # Exclude target and metadata columns
        exclude_cols = ['date', 'time', 'datetime', 'stock_code', 'exchange_name', 'target', 'future_return']
        available_feature_cols = [col for col in self.feature_columns if col in X_with_features.columns and col not in exclude_cols]
        
        if not available_feature_cols:
            # Fallback to neutral probabilities
            return np.array([[0.33, 0.34, 0.33]])
        
        X_features = X_with_features[available_feature_cols]
        X_features = X_features.fillna(method='bfill').fillna(method='ffill').fillna(0)
        
        # Handle case where we have fewer features than expected
        if len(available_feature_cols) < len(self.feature_columns):
            # Create a DataFrame with all expected features, filling missing ones with 0
            missing_cols = [col for col in self.feature_columns if col not in available_feature_cols and col not in exclude_cols]
            for col in missing_cols:
                X_features[col] = 0
            
            # Reorder columns to match training order
            feature_order = [col for col in self.feature_columns if col not in exclude_cols]
            X_features = X_features[feature_order]
        
        # Scale features
        X_scaled = self.scaler.transform(X_features)
        
        # Feature selection
        if self.feature_selector is not None:
            X_scaled = self.feature_selector.transform(X_scaled)
        
        # Get probabilities
        if self.model_type == 'lstm':
            X_lstm = self.prepare_lstm_sequences(X_scaled)
            if len(X_lstm) == 0:
                return np.array([[0.33, 0.34, 0.33]])  # Return neutral probabilities
            return self.model.predict(X_lstm)
        else:
            return self.model.predict_proba(X_scaled)
    
    def save_model(self, model_dir: str = "model"):
        """Save trained model and preprocessing components"""
        model_path = Path(model_dir)
        model_path.mkdir(exist_ok=True)
        
        # Save sklearn/xgboost models
        if self.model_type != 'lstm':
            joblib.dump(self.model, model_path / f"{self.model_type}_model.pkl")
        else:
            self.model.save(model_path / f"{self.model_type}_model.h5")
        
        # Save preprocessing components
        joblib.dump(self.scaler, model_path / "feature_scaler.pkl")
        
        if self.feature_selector is not None:
            joblib.dump(self.feature_selector, model_path / "feature_selector.pkl")
        
        joblib.dump(self.label_encoder, model_path / "label_encoder.pkl")
        
        # Save feature columns
        if self.feature_columns:
            with open(model_path / "feature_columns.pkl", 'wb') as f:
                pickle.dump(self.feature_columns, f)
        
        self.logger.info(f"💾 Model saved to {model_path}")
    
    def load_model(self, model_dir: str = "model"):
        """Load saved model and preprocessing components"""
        model_path = Path(model_dir)
        
        # Load model
        if self.model_type == 'lstm':
            if HAS_TENSORFLOW:
                self.model = load_model(model_path / f"{self.model_type}_model.h5")
            else:
                raise ImportError("TensorFlow not available for loading LSTM model")
        else:
            self.model = joblib.load(model_path / f"{self.model_type}_model.pkl")
        
        # Load preprocessing components
        self.scaler = joblib.load(model_path / "feature_scaler.pkl")
        
        if (model_path / "feature_selector.pkl").exists():
            self.feature_selector = joblib.load(model_path / "feature_selector.pkl")
        
        self.label_encoder = joblib.load(model_path / "label_encoder.pkl")
        
        # Load feature columns
        if (model_path / "feature_columns.pkl").exists():
            with open(model_path / "feature_columns.pkl", 'rb') as f:
                self.feature_columns = pickle.load(f)
        
        self.logger.info(f"📂 Model loaded from {model_path}")

def train_trading_model(data_path: str, model_type: str = 'random_forest'):
    """Train a trading model on historical data"""
    logger = logging.getLogger(__name__)
    logger.info(f"🚀 Training {model_type} trading model...")
    
    # Load data
    df = pd.read_csv(data_path)
    
    # Filter to a single stock for initial training (can be expanded later)
    if 'stock_code' in df.columns:
        available_stocks = df['stock_code'].unique()
        selected_stock = available_stocks[0]  # Use first stock for training
        df = df[df['stock_code'] == selected_stock]
        logger.info(f"Training on stock: {selected_stock}")
    
    # Initialize and train model
    ml_model = TradingMLModel(model_type=model_type)
    
    # Prepare data
    X, y = ml_model.prepare_data(df)
    
    logger.info(f"📊 Training data shape: {X.shape}")
    logger.info(f"📊 Target distribution:")
    print(pd.Series(y).value_counts().sort_index())
    
    # Train model
    ml_model.train_model(X, y)
    
    # Save model
    ml_model.save_model()
    
    return ml_model

if __name__ == "__main__":
    # Example usage
    data_path = "data/NSE_AllStocks_historical_data_5min.csv"
    
    if Path(data_path).exists():
        # Train different types of models
        for model_type in ['random_forest', 'gradient_boost']:
            try:
                model = train_trading_model(data_path, model_type)
                print(f"\n✅ Successfully trained {model_type} model")
            except Exception as e:
                print(f"\n❌ Failed to train {model_type} model: {e}")
    else:
        print(f"❌ Data file not found: {data_path}")
        print("Please ensure the historical data file exists in the correct location.")