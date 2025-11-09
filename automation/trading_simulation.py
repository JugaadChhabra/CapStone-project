#!/usr/bin/env python3
"""
Trading Simulation Engine with ML Model Integration

PURPOSE: Simulates live trading using historical data and ML models to make entry/exit decisions
FEATURES:
- Uses existing .pkl model (feature_scaler.pkl) for predictions
- Feeds historical data incrementally to simulate live market
- Maintains proper trade ledger with entry/exit prices
- Risk management with stop-loss and take-profit
- Position sizing and portfolio tracking

USAGE: python trading_simulation.py
"""

import pandas as pd
import numpy as np
import pickle
import joblib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
import os
from pathlib import Path

# Import existing modules
from trading_config import *
from icici_functions import load_stock_data_from_csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_simulation.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class Trade:
    """Individual trade record"""
    trade_id: int
    symbol: str
    action: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    timestamp: datetime
    signal: str  # Model prediction signal
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
@dataclass
class Position:
    """Current position in a stock"""
    symbol: str
    quantity: int
    avg_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0

class FeatureEngineering:
    """Calculate technical indicators and features for ML model"""
    
    @staticmethod
    def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
        """Simple Moving Average"""
        return prices.rolling(window=window).mean()
    
    @staticmethod
    def calculate_ema(prices: pd.Series, span: int) -> pd.Series:
        """Exponential Moving Average"""
        return prices.ewm(span=span).mean()
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD indicator"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series, window: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands"""
        sma = prices.rolling(window=window).mean()
        std = prices.rolling(window=window).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band
    
    @staticmethod
    def calculate_volume_indicators(data: pd.DataFrame) -> pd.DataFrame:
        """Volume-based indicators"""
        # Volume Moving Average
        data['volume_sma_10'] = data['volume'].rolling(window=10).mean()
        
        # Volume Rate of Change
        data['volume_roc'] = data['volume'].pct_change(periods=5) * 100
        
        # Price Volume Trend
        data['pvt'] = ((data['close'] - data['close'].shift(1)) / data['close'].shift(1) * data['volume']).cumsum()
        
        return data
    
    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create comprehensive feature set for ML model"""
        df = data.copy()
        
        # Price-based features
        df['sma_5'] = self.calculate_sma(df['close'], 5)
        df['sma_10'] = self.calculate_sma(df['close'], 10)
        df['sma_20'] = self.calculate_sma(df['close'], 20)
        df['ema_12'] = self.calculate_ema(df['close'], 12)
        df['ema_26'] = self.calculate_ema(df['close'], 26)
        
        # RSI
        df['rsi'] = self.calculate_rsi(df['close'])
        
        # MACD
        df['macd'], df['macd_signal'], df['macd_histogram'] = self.calculate_macd(df['close'])
        
        # Bollinger Bands
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = self.calculate_bollinger_bands(df['close'])
        
        # Price ratios
        df['price_to_sma_20'] = df['close'] / df['sma_20']
        df['sma_5_to_sma_20'] = df['sma_5'] / df['sma_20']
        
        # Volatility
        df['volatility_10'] = df['close'].rolling(window=10).std()
        df['high_low_ratio'] = df['high'] / df['low']
        
        # Volume features
        df = self.calculate_volume_indicators(df)
        
        # Price momentum
        df['price_change_1'] = df['close'].pct_change(periods=1)
        df['price_change_5'] = df['close'].pct_change(periods=5)
        df['price_change_10'] = df['close'].pct_change(periods=10)
        
        # Gap detection
        df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        # Market session features (time-based)
        df['hour'] = pd.to_datetime(df['time'], format='%H:%M:%S').dt.hour
        df['minute'] = pd.to_datetime(df['time'], format='%H:%M:%S').dt.minute
        df['is_opening_session'] = ((df['hour'] == 9) & (df['minute'] <= 30)).astype(int)
        df['is_closing_session'] = ((df['hour'] >= 15) & (df['minute'] >= 15)).astype(int)
        
        return df

class TradingSimulator:
    """Main trading simulation engine with ML integration"""
    
    def __init__(self, initial_capital: float = 500000):
        self.logger = logging.getLogger(__name__)
        self.logger.info("🚀 Initializing Trading Simulator...")
        
        # Portfolio state
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.trade_counter = 1
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_portfolio_value = initial_capital
        
        # Load ML components
        self.feature_engineer = FeatureEngineering()
        self.ml_model = None  # Will be set in load_ml_model
        self.load_ml_model()
        
        # Load historical data
        self.load_historical_data()
        
        self.logger.info("✅ Trading Simulator initialized")
    
    def load_ml_model(self):
        """Load the pre-trained ML model and scaler"""
        try:
            # Try to import and use the advanced ML model
            try:
                from ml_trading_model import TradingMLModel
                self.ml_model = TradingMLModel()
                
                model_dir = Path(__file__).parent / "model"
                if model_dir.exists() and any(model_dir.glob("*.pkl")):
                    self.ml_model.load_model()
                    self.logger.info("✅ Advanced ML model loaded successfully")
                else:
                    self.logger.warning("⚠️  No saved ML model found, will train on-the-fly")
                    self.ml_model = None
                    
            except ImportError:
                self.logger.warning("⚠️  Advanced ML model not available, using basic model")
                self.ml_model = None
            
            # Fallback to basic model loading
            if self.ml_model is None:
                model_dir = Path(__file__).parent / "model"
                scaler_path = model_dir / "feature_scaler.pkl"
                
                if scaler_path.exists():
                    with open(scaler_path, 'rb') as f:
                        self.scaler = pickle.load(f)
                    self.logger.info("✅ Feature scaler loaded successfully")
                else:
                    self.logger.warning("⚠️  Feature scaler not found, creating dummy scaler")
                    # Create a dummy scaler for demonstration
                    from sklearn.preprocessing import StandardScaler
                    self.scaler = StandardScaler()
                
                # Look for model file (common extensions)
                model_files = list(model_dir.glob("*.pkl")) + list(model_dir.glob("*.joblib"))
                model_files = [f for f in model_files if 'scaler' not in f.name.lower()]
                
                if model_files:
                    model_path = model_files[0]
                    if model_path.suffix == '.pkl':
                        with open(model_path, 'rb') as f:
                            self.model = pickle.load(f)
                    else:
                        self.model = joblib.load(model_path)
                    self.logger.info(f"✅ ML model loaded: {model_path.name}")
                else:
                    self.logger.warning("⚠️  No ML model found, creating dummy model")
                    # Create a dummy model for demonstration
                    self.model = self.create_dummy_model()
                
        except Exception as e:
            self.logger.error(f"❌ Error loading ML model: {e}")
            self.model = self.create_dummy_model()
            self.ml_model = None
    
    def create_dummy_model(self):
        """Create a dummy model for demonstration purposes"""
        class DummyModel:
            def predict(self, X):
                """Simple momentum-based prediction"""
                # Use price change and RSI for basic signal generation
                predictions = []
                for row in X:
                    # Assuming features are in order: [price_change_1, rsi, ...]
                    price_change = row[0] if len(row) > 0 else 0
                    rsi = row[1] if len(row) > 1 else 50
                    
                    # Simple rules:
                    # BUY signal (1) if: positive momentum and RSI < 70
                    # SELL signal (-1) if: negative momentum or RSI > 80
                    if price_change > 0.02 and rsi < 70:  # 2% positive change, not overbought
                        predictions.append(1)
                    elif price_change < -0.02 or rsi > 80:  # 2% negative change or overbought
                        predictions.append(-1)
                    else:
                        predictions.append(0)  # HOLD
                
                return np.array(predictions)
            
            def predict_proba(self, X):
                """Return dummy probabilities"""
                preds = self.predict(X)
                # Convert to probabilities [prob_sell, prob_hold, prob_buy]
                probabilities = []
                for pred in preds:
                    if pred == 1:  # BUY
                        probabilities.append([0.1, 0.2, 0.7])
                    elif pred == -1:  # SELL
                        probabilities.append([0.7, 0.2, 0.1])
                    else:  # HOLD
                        probabilities.append([0.2, 0.6, 0.2])
                return np.array(probabilities)
        
        return DummyModel()
    
    def load_historical_data(self):
        """Load historical stock data"""
        try:
            data_path = Path(__file__).parent / "data" / "NSE_AllStocks_historical_data_5min.csv"
            
            if not data_path.exists():
                raise FileNotFoundError(f"Historical data file not found: {data_path}")
            
            self.logger.info("📊 Loading historical data...")
            self.historical_data = pd.read_csv(data_path)
            
            # Convert date and time columns
            self.historical_data['datetime'] = pd.to_datetime(
                self.historical_data['date'] + ' ' + self.historical_data['time']
            )
            
            # Sort by datetime
            self.historical_data = self.historical_data.sort_values(['stock_code', 'datetime'])
            
            # Get list of available stocks
            self.available_stocks = self.historical_data['stock_code'].unique().tolist()
            
            self.logger.info(f"✅ Loaded data for {len(self.available_stocks)} stocks")
            self.logger.info(f"📅 Date range: {self.historical_data['date'].min()} to {self.historical_data['date'].max()}")
            
        except Exception as e:
            self.logger.error(f"❌ Error loading historical data: {e}")
            raise
    
    def prepare_features(self, stock_data: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML prediction"""
        # Create technical indicators
        features_df = self.feature_engineer.create_features(stock_data)
        
        # Select relevant features for model (adjust based on your actual model)
        feature_columns = [
            'price_change_1', 'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'price_to_sma_20', 'sma_5_to_sma_20', 'volatility_10',
            'volume_roc', 'bb_upper', 'bb_lower', 'is_opening_session', 'is_closing_session'
        ]
        
        # Fill missing values
        features_df = features_df.fillna(method='bfill').fillna(method='ffill').fillna(0)
        
        return features_df[feature_columns]
    
    def get_ml_signal(self, stock_data: pd.DataFrame) -> Tuple[int, float]:
        """Get trading signal from ML model"""
        try:
            # Use advanced ML model if available
            if self.ml_model is not None:
                # Prepare comprehensive features using the advanced model
                if len(stock_data) >= 20:  # Need sufficient data
                    # Use only the current data for prediction (no future-looking)
                    prediction = self.ml_model.predict(stock_data)
                    
                    if len(prediction) > 0:
                        pred_value = prediction[-1]  # Get the latest prediction
                        
                        # Get probability if available
                        try:
                            probabilities = self.ml_model.predict_proba(stock_data)
                            if len(probabilities) > 0:
                                confidence = max(probabilities[-1])
                            else:
                                confidence = 0.7 if abs(pred_value) == 1 else 0.5
                        except:
                            confidence = 0.7 if abs(pred_value) == 1 else 0.5
                        
                        return int(pred_value), confidence
            
            # Fallback to basic model
            # Prepare features
            features_df = self.prepare_features(stock_data)
            
            if len(features_df) == 0:
                return 0, 0.5
            
            # Get the latest row for prediction
            latest_features = features_df.iloc[-1:].values
            
            # Scale features if scaler is available
            if hasattr(self.scaler, 'transform'):
                try:
                    # Handle case where scaler hasn't been fitted
                    if hasattr(self.scaler, 'mean_'):
                        latest_features = self.scaler.transform(latest_features)
                    else:
                        # Fit scaler on available data for demonstration
                        if len(features_df) > 1:
                            self.scaler.fit(features_df.values)
                            latest_features = self.scaler.transform(latest_features)
                except Exception as e:
                    self.logger.warning(f"⚠️  Scaler transform failed: {e}")
            
            # Get prediction
            prediction = self.model.predict(latest_features)[0]
            
            # Get probability if available
            try:
                probabilities = self.model.predict_proba(latest_features)[0]
                confidence = max(probabilities)
            except:
                confidence = 0.7 if abs(prediction) == 1 else 0.5
            
            return int(prediction), confidence
            
        except Exception as e:
            self.logger.debug(f"❌ Error getting ML signal: {e}")
            # Fallback to simple momentum strategy
            try:
                if len(stock_data) >= 10:
                    recent_data = stock_data.tail(10)
                    price_change = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
                    
                    # Simple momentum strategy
                    if price_change > 0.03:  # 3% gain
                        return 1, 0.6  # Buy signal
                    elif price_change < -0.03:  # 3% loss
                        return -1, 0.6  # Sell signal
                    else:
                        return 0, 0.5  # Hold
                else:
                    return 0, 0.5
            except:
                return 0, 0.5
    
    def should_enter_position(self, symbol: str, current_data: pd.DataFrame) -> Tuple[bool, str]:
        """Determine if we should enter a new position"""
        # Check if we already have a position
        if symbol in self.positions:
            return False, "Already in position"
        
        # Check if we have enough capital
        position_size = min(POSITION_SIZE, self.current_capital * 0.2)  # Max 20% per position
        if position_size < MIN_QUANTITY * current_data['close'].iloc[-1]:
            return False, "Insufficient capital"
        
        # Check maximum positions
        if len(self.positions) >= MAX_POSITIONS:
            return False, "Maximum positions reached"
        
        # Get ML signal
        signal, confidence = self.get_ml_signal(current_data)
        
        # Log the signal for debugging (only occasionally to avoid spam)
        if len(current_data) % 20 == 0:  # Log every 20th check
            self.logger.debug(f"🔍 {symbol}: Signal={signal}, Confidence={confidence:.2f}")
        
        # More lenient entry criteria for testing
        if abs(signal) == 1 and confidence > 0.5:  # Lowered confidence threshold
            return True, f"ML Signal: {signal} (confidence: {confidence:.2f})"
        
        return False, f"Weak signal: {signal} (confidence: {confidence:.2f})"
    
    def should_exit_position(self, symbol: str, position: Position, current_price: float) -> Tuple[bool, str]:
        """Determine if we should exit an existing position"""
        # Check stop loss
        if position.quantity > 0:  # Long position
            if current_price <= position.stop_loss:
                return True, "Stop loss hit"
            if current_price >= position.take_profit:
                return True, "Take profit hit"
        else:  # Short position
            if current_price >= position.stop_loss:
                return True, "Stop loss hit"
            if current_price <= position.take_profit:
                return True, "Take profit hit"
        
        # Check time-based exit (hold for maximum of 4 hours = 48 candles of 5min each)
        current_time = datetime.now()
        if (current_time - position.entry_time).total_seconds() > 4 * 3600:  # 4 hours
            return True, "Time-based exit"
        
        return False, "Continue holding"
    
    def calculate_position_size(self, price: float) -> int:
        """Calculate position size based on available capital"""
        max_position_value = min(POSITION_SIZE, self.current_capital * 0.2)
        quantity = int(max_position_value / price)
        return max(quantity, MIN_QUANTITY)
    
    def enter_position(self, symbol: str, signal: int, price: float, timestamp: datetime, ml_signal: str):
        """Enter a new position"""
        quantity = self.calculate_position_size(price)
        
        # Adjust quantity based on signal (positive for long, negative for short)
        if signal == -1:
            quantity = -quantity  # Short position
        
        # Calculate stop loss and take profit
        if signal == 1:  # Long position
            stop_loss = price * (1 - STOP_LOSS_PERCENT / 100)
            take_profit = price * (1 + TARGET_PROFIT_PERCENT / 100)
        else:  # Short position
            stop_loss = price * (1 + STOP_LOSS_PERCENT / 100)
            take_profit = price * (1 - TARGET_PROFIT_PERCENT / 100)
        
        # Create position
        position = Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=price,
            entry_time=timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_price=price
        )
        
        # Create trade record
        trade = Trade(
            trade_id=self.trade_counter,
            symbol=symbol,
            action='BUY' if signal == 1 else 'SELL',
            quantity=abs(quantity),
            price=price,
            timestamp=timestamp,
            signal=ml_signal
        )
        
        # Update portfolio
        self.positions[symbol] = position
        self.trades.append(trade)
        self.trade_counter += 1
        
        # Update capital
        trade_value = abs(quantity) * price
        self.current_capital -= trade_value * 0.001  # 0.1% transaction cost
        
        self.logger.info(f"📈 ENTERED {trade.action} position: {symbol} @ ₹{price:.2f} qty:{abs(quantity)} | {ml_signal}")
    
    def exit_position(self, symbol: str, reason: str, price: float, timestamp: datetime):
        """Exit an existing position"""
        position = self.positions[symbol]
        
        # Create exit trade record
        exit_trade = Trade(
            trade_id=self.trade_counter,
            symbol=symbol,
            action='SELL' if position.quantity > 0 else 'BUY',
            quantity=abs(position.quantity),
            price=price,
            timestamp=timestamp,
            signal=reason
        )
        
        # Calculate P&L
        if position.quantity > 0:  # Long position
            pnl = (price - position.avg_price) * position.quantity
        else:  # Short position
            pnl = (position.avg_price - price) * abs(position.quantity)
        
        # Update portfolio
        trade_value = abs(position.quantity) * price
        self.current_capital += trade_value - (trade_value * 0.001)  # Subtract transaction cost
        self.current_capital += pnl
        
        # Update statistics
        self.total_trades += 1
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1
        
        # Update drawdown
        current_portfolio_value = self.get_portfolio_value()
        if current_portfolio_value > self.peak_portfolio_value:
            self.peak_portfolio_value = current_portfolio_value
        else:
            drawdown = (self.peak_portfolio_value - current_portfolio_value) / self.peak_portfolio_value
            self.max_drawdown = max(self.max_drawdown, drawdown)
        
        self.trades.append(exit_trade)
        self.trade_counter += 1
        del self.positions[symbol]
        
        pnl_color = "🟢" if pnl > 0 else "🔴"
        self.logger.info(f"📉 EXITED position: {symbol} @ ₹{price:.2f} | P&L: {pnl_color} ₹{pnl:.2f} | {reason}")
    
    def get_portfolio_value(self) -> float:
        """Calculate current portfolio value"""
        total_value = self.current_capital
        for position in self.positions.values():
            if position.quantity > 0:  # Long position
                position_value = position.quantity * position.current_price
            else:  # Short position
                position_value = abs(position.quantity) * (2 * position.avg_price - position.current_price)
            total_value += position_value
        return total_value
    
    def update_positions(self, symbol: str, current_price: float):
        """Update position with current price"""
        if symbol in self.positions:
            position = self.positions[symbol]
            position.current_price = current_price
            
            # Calculate unrealized P&L
            if position.quantity > 0:  # Long position
                position.unrealized_pnl = (current_price - position.avg_price) * position.quantity
            else:  # Short position
                position.unrealized_pnl = (position.avg_price - current_price) * abs(position.quantity)
    
    def simulate_trading_day(self, date: str):
        """Simulate trading for a specific day"""
        self.logger.info(f"\n🗓️  Simulating trading day: {date}")
        
        # Get data for the day
        day_data = self.historical_data[self.historical_data['date'] == date]
        
        if len(day_data) == 0:
            self.logger.warning(f"⚠️  No data for {date}")
            return
        
        # Group by stock
        for symbol in day_data['stock_code'].unique():
            stock_day_data = day_data[day_data['stock_code'] == symbol].sort_values('datetime')
            
            if len(stock_day_data) < 20:  # Need minimum data for indicators
                continue
            
            # Process each time interval
            for i, (_, row) in enumerate(stock_day_data.iterrows()):
                current_price = row['close']
                timestamp = row['datetime']
                
                # Get historical data up to current point for ML prediction
                historical_subset = stock_day_data.iloc[:i+1]
                
                # Update existing positions
                self.update_positions(symbol, current_price)
                
                # Check exit conditions for existing positions
                if symbol in self.positions:
                    should_exit, exit_reason = self.should_exit_position(
                        symbol, self.positions[symbol], current_price
                    )
                    if should_exit:
                        self.exit_position(symbol, exit_reason, current_price, timestamp)
                
                # Check entry conditions for new positions (only if we have enough historical data)
                if len(historical_subset) >= 20:  # Need minimum history for indicators
                    should_enter, entry_reason = self.should_enter_position(symbol, historical_subset)
                    if should_enter:
                        signal, confidence = self.get_ml_signal(historical_subset)
                        if abs(signal) == 1:
                            self.enter_position(symbol, signal, current_price, timestamp, entry_reason)
    
    def run_simulation(self, start_date: str = None, end_date: str = None):
        """Run the complete trading simulation"""
        self.logger.info("🚀 Starting Trading Simulation with ML Model")
        self.logger.info("=" * 60)
        
        # Get date range
        available_dates = sorted(self.historical_data['date'].unique())
        
        if start_date is None:
            start_date = available_dates[0]
        if end_date is None:
            end_date = available_dates[-1]
        
        simulation_dates = [d for d in available_dates if start_date <= d <= end_date]
        
        self.logger.info(f"📅 Simulation period: {start_date} to {end_date}")
        self.logger.info(f"💰 Initial capital: ₹{self.initial_capital:,.2f}")
        
        # Run simulation day by day
        for date in simulation_dates[:10]:  # Limit to first 10 days for demo
            try:
                self.simulate_trading_day(date)
            except Exception as e:
                self.logger.error(f"❌ Error simulating {date}: {e}")
        
        # Final portfolio summary
        self.generate_final_report()
    
    def generate_final_report(self):
        """Generate final trading report"""
        final_portfolio_value = self.get_portfolio_value()
        total_return = (final_portfolio_value - self.initial_capital) / self.initial_capital * 100
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 FINAL TRADING SIMULATION REPORT")
        self.logger.info("=" * 60)
        self.logger.info(f"💰 Initial Capital: ₹{self.initial_capital:,.2f}")
        self.logger.info(f"💰 Final Portfolio Value: ₹{final_portfolio_value:,.2f}")
        self.logger.info(f"📈 Total Return: {total_return:+.2f}%")
        self.logger.info(f"📊 Total P&L: ₹{self.total_pnl:+,.2f}")
        self.logger.info(f"🎯 Total Trades: {self.total_trades}")
        
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            self.logger.info(f"🏆 Win Rate: {win_rate:.1f}% ({self.winning_trades}/{self.total_trades})")
            self.logger.info(f"📉 Max Drawdown: {self.max_drawdown:.2%}")
        
        self.logger.info(f"💼 Open Positions: {len(self.positions)}")
        
        # Save trade ledger
        self.save_trade_ledger()
    
    def save_trade_ledger(self):
        """Save trade ledger to CSV file"""
        if not self.trades:
            self.logger.warning("⚠️  No trades to save")
            return
        
        # Convert trades to DataFrame
        trades_data = []
        for trade in self.trades:
            trades_data.append({
                'Trade_ID': trade.trade_id,
                'Symbol': trade.symbol,
                'Action': trade.action,
                'Quantity': trade.quantity,
                'Price': trade.price,
                'Timestamp': trade.timestamp,
                'Signal': trade.signal,
                'Value': trade.quantity * trade.price
            })
        
        df = pd.DataFrame(trades_data)
        
        # Calculate P&L for each completed trade pair
        df['P&L'] = 0.0
        df['Trade_Status'] = 'Open'
        
        # Group by symbol and match entry/exit pairs
        for symbol in df['Symbol'].unique():
            symbol_trades = df[df['Symbol'] == symbol].copy()
            
            i = 0
            while i < len(symbol_trades) - 1:
                entry_trade = symbol_trades.iloc[i]
                exit_trade = symbol_trades.iloc[i + 1]
                
                if entry_trade['Action'] != exit_trade['Action']:
                    # Calculate P&L
                    if entry_trade['Action'] == 'BUY':
                        pnl = (exit_trade['Price'] - entry_trade['Price']) * entry_trade['Quantity']
                    else:
                        pnl = (entry_trade['Price'] - exit_trade['Price']) * entry_trade['Quantity']
                    
                    # Update both trades
                    df.loc[df.index[df['Trade_ID'] == entry_trade['Trade_ID']], 'P&L'] = pnl
                    df.loc[df.index[df['Trade_ID'] == exit_trade['Trade_ID']], 'P&L'] = pnl
                    df.loc[df.index[df['Trade_ID'] == entry_trade['Trade_ID']], 'Trade_Status'] = 'Closed'
                    df.loc[df.index[df['Trade_ID'] == exit_trade['Trade_ID']], 'Trade_Status'] = 'Closed'
                    
                    i += 2  # Skip both trades
                else:
                    i += 1
        
        # Save to CSV
        output_file = f"trade_ledger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        
        self.logger.info(f"💾 Trade ledger saved to: {output_file}")
        
        # Print sample trades
        self.logger.info("\n📋 Sample Trade Ledger:")
        print(df.head(10).to_string(index=False))

def main():
    """Main function to run the trading simulation"""
    try:
        # Initialize simulator
        simulator = TradingSimulator(initial_capital=500000)
        
        # Run simulation
        simulator.run_simulation()
        
    except Exception as e:
        logging.error(f"❌ Simulation failed: {e}")
        raise

if __name__ == "__main__":
    main()