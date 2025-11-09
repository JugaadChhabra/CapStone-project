#!/usr/bin/env python3

import pandas as pd
import numpy as np
import pickle
import logging
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import existing modules (optional - standalone simulation)
try:
    import trading_config
except ImportError:
    trading_config = None

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiStockTradingSimulator:
    def __init__(self, ml_model_path='model/trading_model.pkl', initial_capital=1000000):
        """
        Enhanced multi-stock trading simulator that properly handles time-sorted data
        and manages multiple positions across different stocks simultaneously.
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.ml_model_path = ml_model_path
        self.ml_model = None
        self.scaler = None
        
        # Multi-stock portfolio management
        self.open_positions = {}  # {stock_code: position_info}
        self.trade_ledger = []
        self.max_positions = 5  # Maximum number of simultaneous positions
        self.position_size_pct = 0.15  # 15% of capital per position
        
        # Realistic trading parameters
        self.min_position_hold_time = 30  # Minimum 30 candles (2.5 hours)
        self.max_position_hold_time = 288  # Maximum 288 candles (24 hours/1 day)
        self.profit_target_pct = 2.0  # 2% profit target
        self.stop_loss_pct = 1.0  # 1% stop loss
        self.trailing_stop_pct = 0.5  # 0.5% trailing stop
        
        # Trading hours
        self.trading_start_time = "09:15:00"
        self.trading_end_time = "15:30:00"
        
        logger.info(f"Initialized MultiStockTradingSimulator with {initial_capital:,.2f} capital")
        
    def load_ml_model(self):
        """Load the trained ML model and scaler"""
        try:
            # Try to load the random forest model
            model_path = 'model/random_forest_model.pkl'
            scaler_path = 'model/feature_scaler.pkl'
            
            if os.path.exists(model_path):
                with open(model_path, 'rb') as f:
                    self.ml_model = pickle.load(f)
                logger.info("Loaded Random Forest model successfully")
                
                # Try to load scaler
                if os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as f:
                        self.scaler = pickle.load(f)
                    logger.info("Loaded feature scaler successfully")
                else:
                    self.scaler = None
                    logger.warning("No feature scaler found")
            else:
                logger.warning("No ML model found - will use technical analysis only")
                self.ml_model = None
                self.scaler = None
                
        except Exception as e:
            logger.warning(f"Could not load ML model: {e}. Using technical analysis only.")
            self.ml_model = None
            self.scaler = None
    
    def prepare_data(self, data_file):
        """
        Load and prepare the multi-stock dataset by sorting chronologically
        """
        logger.info("Loading and preparing multi-stock data...")
        
        # Load the dataset
        df = pd.read_csv(data_file)
        logger.info(f"Loaded {len(df)} total records")
        
        # Create datetime column
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        
        # Sort by datetime first, then by stock_code for consistent ordering
        df = df.sort_values(['datetime', 'stock_code']).reset_index(drop=True)
        
        # Get stock info
        stocks = df['stock_code'].unique()
        logger.info(f"Found {len(stocks)} stocks: {list(stocks)}")
        
        # Filter trading hours
        df['hour'] = df['datetime'].dt.hour
        df['minute'] = df['datetime'].dt.minute
        df = df[
            ((df['hour'] == 9) & (df['minute'] >= 15)) |
            ((df['hour'] >= 10) & (df['hour'] <= 14)) |
            ((df['hour'] == 15) & (df['minute'] <= 30))
        ]
        
        logger.info(f"After filtering trading hours: {len(df)} records")
        
        return df
    
    def calculate_technical_indicators(self, stock_data):
        """
        Calculate technical indicators for a single stock's data
        """
        df = stock_data.copy()
        
        # Price-based indicators
        df['returns'] = df['close'].pct_change()
        df['volatility'] = df['returns'].rolling(20).std()
        
        # Moving averages
        df['sma_5'] = df['close'].rolling(5).mean()
        df['sma_10'] = df['close'].rolling(10).mean()
        df['sma_20'] = df['close'].rolling(20).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # ATR for volatility-based position sizing
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        df['atr'] = true_range.rolling(14).mean()
        
        return df
    
    def generate_ml_features(self, stock_data):
        """
        Generate features for ML model prediction
        """
        df = stock_data.copy()
        
        # Basic price features
        feature_cols = [
            'open', 'high', 'low', 'close', 'volume',
            'returns', 'volatility', 'sma_5', 'sma_10', 'sma_20',
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'bb_middle', 'bb_upper', 'bb_lower', 'bb_position',
            'volume_sma', 'volume_ratio', 'atr'
        ]
        
        # Additional technical features
        df['price_change'] = df['close'].pct_change()
        df['high_low_pct'] = (df['high'] - df['low']) / df['low']
        df['close_open_pct'] = (df['close'] - df['open']) / df['open']
        
        # Momentum indicators
        df['momentum_1'] = df['close'] / df['close'].shift(1) - 1
        df['momentum_3'] = df['close'] / df['close'].shift(3) - 1
        df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
        
        feature_cols.extend([
            'price_change', 'high_low_pct', 'close_open_pct',
            'momentum_1', 'momentum_3', 'momentum_5'
        ])
        
        # Return features that exist
        available_features = [col for col in feature_cols if col in df.columns]
        
        return df[available_features]
    
    def should_enter_position(self, stock_code, current_data, ml_features):
        """
        Determine if we should enter a position based on ML prediction and technical analysis
        """
        # Check if we already have a position in this stock
        if stock_code in self.open_positions:
            return False, "Already have position in this stock"
        
        # Check if we have too many open positions
        if len(self.open_positions) >= self.max_positions:
            return False, "Maximum positions reached"
        
        # Check if we have enough capital
        position_value = self.capital * self.position_size_pct
        if position_value < 10000:  # Minimum position size
            return False, "Insufficient capital for position"
        
        try:
            # ML prediction
            ml_signal = 0
            if self.ml_model is not None and not ml_features.isnull().any():
                features_array = ml_features.values.reshape(1, -1)
                if self.scaler:
                    features_array = self.scaler.transform(features_array)
                
                prediction = self.ml_model.predict(features_array)[0]
                prediction_proba = self.ml_model.predict_proba(features_array)[0]
                
                if prediction == 1 and prediction_proba[1] > 0.6:  # 60% confidence threshold
                    ml_signal = 1
                    
            # Technical analysis signals
            rsi = current_data.get('rsi', 50)
            macd_histogram = current_data.get('macd_histogram', 0)
            bb_position = current_data.get('bb_position', 0.5)
            volume_ratio = current_data.get('volume_ratio', 1.0)
            momentum_3 = current_data.get('momentum_3', 0)
            
            # Entry conditions
            conditions = []
            
            # RSI oversold but recovering
            if 25 <= rsi <= 45:
                conditions.append("RSI_RECOVERY")
            
            # MACD turning positive
            if macd_histogram > 0:
                conditions.append("MACD_POSITIVE")
            
            # Price near lower Bollinger Band (potential bounce)
            if bb_position <= 0.3:
                conditions.append("BB_OVERSOLD")
            
            # High volume (interest/momentum)
            if volume_ratio >= 1.5:
                conditions.append("HIGH_VOLUME")
            
            # Positive momentum
            if momentum_3 > 0.005:  # 0.5% momentum
                conditions.append("POSITIVE_MOMENTUM")
            
            # ML signal
            if ml_signal == 1:
                conditions.append("ML_BUY_SIGNAL")
            
            # Require at least 2 conditions including either ML signal OR strong technical signals
            if len(conditions) >= 2 and (ml_signal == 1 or len(conditions) >= 3):
                reason = f"Entry signals: {', '.join(conditions)}"
                return True, reason
            
            return False, f"Insufficient signals. Found: {', '.join(conditions) if conditions else 'None'}"
            
        except Exception as e:
            logger.error(f"Error in entry analysis for {stock_code}: {e}")
            return False, f"Analysis error: {e}"
    
    def should_exit_position(self, stock_code, current_data, position_info):
        """
        Determine if we should exit a position based on risk management and time
        """
        current_price = current_data['close']
        entry_price = position_info['entry_price']
        candles_held = position_info['candles_held']
        
        # Calculate P&L
        pnl_pct = (current_price - entry_price) / entry_price * 100
        
        # Update trailing stop
        if pnl_pct > position_info.get('best_pnl_pct', 0):
            position_info['best_pnl_pct'] = pnl_pct
            position_info['trailing_stop_price'] = current_price * (1 - self.trailing_stop_pct / 100)
        
        # Exit conditions
        
        # 1. Stop loss hit
        if pnl_pct <= -self.stop_loss_pct:
            return True, f"STOP_LOSS: {pnl_pct:.2f}%"
        
        # 2. Profit target hit
        if pnl_pct >= self.profit_target_pct:
            return True, f"PROFIT_TARGET: {pnl_pct:.2f}%"
        
        # 3. Trailing stop hit
        trailing_stop_price = position_info.get('trailing_stop_price')
        if trailing_stop_price and current_price <= trailing_stop_price:
            return True, f"TRAILING_STOP: {pnl_pct:.2f}%"
        
        # 4. Minimum hold time not met
        if candles_held < self.min_position_hold_time:
            return False, f"Holding {candles_held}/{self.min_position_hold_time} candles"
        
        # 5. Maximum hold time reached
        if candles_held >= self.max_position_hold_time:
            return True, f"MAX_HOLD_TIME: {pnl_pct:.2f}%"
        
        # 6. Technical exit signals (after minimum hold time)
        try:
            rsi = current_data.get('rsi', 50)
            macd_histogram = current_data.get('macd_histogram', 0)
            bb_position = current_data.get('bb_position', 0.5)
            
            exit_signals = []
            
            # RSI overbought
            if rsi >= 75:
                exit_signals.append("RSI_OVERBOUGHT")
            
            # MACD turning negative
            if macd_histogram < 0:
                exit_signals.append("MACD_NEGATIVE")
            
            # Price at upper Bollinger Band
            if bb_position >= 0.9:
                exit_signals.append("BB_OVERBOUGHT")
            
            # If we have profit and strong exit signals
            if pnl_pct > 0.5 and len(exit_signals) >= 2:
                return True, f"TECHNICAL_EXIT ({', '.join(exit_signals)}): {pnl_pct:.2f}%"
                
        except Exception as e:
            logger.error(f"Error in technical exit analysis: {e}")
        
        return False, f"Holding: {pnl_pct:.2f}% P&L"
    
    def execute_entry(self, stock_code, current_data, reason):
        """Execute position entry"""
        current_price = current_data['close']
        position_value = self.capital * self.position_size_pct
        shares = int(position_value / current_price)
        
        if shares <= 0:
            return False
        
        actual_position_value = shares * current_price
        
        # Create position
        position_info = {
            'entry_datetime': current_data['datetime'],
            'entry_price': current_price,
            'shares': shares,
            'position_value': actual_position_value,
            'candles_held': 0,
            'best_pnl_pct': 0,
            'trailing_stop_price': None,
            'entry_reason': reason
        }
        
        self.open_positions[stock_code] = position_info
        self.capital -= actual_position_value
        
        logger.info(f"ENTRY: {stock_code} @ {current_price:.2f}, Shares: {shares}, Value: {actual_position_value:,.2f}")
        
        return True
    
    def execute_exit(self, stock_code, current_data, reason):
        """Execute position exit"""
        if stock_code not in self.open_positions:
            return False
        
        position_info = self.open_positions[stock_code]
        current_price = current_data['close']
        
        # Calculate P&L
        exit_value = position_info['shares'] * current_price
        pnl = exit_value - position_info['position_value']
        pnl_pct = (pnl / position_info['position_value']) * 100
        
        # Update capital
        self.capital += exit_value
        
        # Record trade
        trade_record = {
            'stock_code': stock_code,
            'entry_datetime': position_info['entry_datetime'],
            'exit_datetime': current_data['datetime'],
            'entry_price': position_info['entry_price'],
            'exit_price': current_price,
            'shares': position_info['shares'],
            'position_value': position_info['position_value'],
            'exit_value': exit_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'candles_held': position_info['candles_held'],
            'entry_reason': position_info['entry_reason'],
            'exit_reason': reason,
            'capital_after_trade': self.capital
        }
        
        self.trade_ledger.append(trade_record)
        
        # Remove position
        del self.open_positions[stock_code]
        
        logger.info(f"EXIT: {stock_code} @ {current_price:.2f}, P&L: {pnl:,.2f} ({pnl_pct:.2f}%)")
        
        return True
    
    def run_simulation(self, data_file):
        """Run the multi-stock trading simulation"""
        logger.info("Starting multi-stock trading simulation...")
        
        # Load ML model
        self.load_ml_model()
        
        # Prepare data
        df = self.prepare_data(data_file)
        
        # Group by stock for technical indicator calculation
        processed_stocks = {}
        for stock_code in df['stock_code'].unique():
            stock_data = df[df['stock_code'] == stock_code].copy().reset_index(drop=True)
            stock_data_with_indicators = self.calculate_technical_indicators(stock_data)
            processed_stocks[stock_code] = stock_data_with_indicators
            logger.info(f"Processed {len(stock_data_with_indicators)} candles for {stock_code}")
        
        # Get all unique timestamps and sort them
        all_timestamps = sorted(df['datetime'].unique())
        logger.info(f"Simulating across {len(all_timestamps)} unique timestamps")
        
        simulation_start = datetime.now()
        processed_timestamps = 0
        
        # Process each timestamp
        for timestamp in all_timestamps:
            processed_timestamps += 1
            
            if processed_timestamps % 1000 == 0:
                elapsed = datetime.now() - simulation_start
                logger.info(f"Processed {processed_timestamps}/{len(all_timestamps)} timestamps. "
                           f"Elapsed: {elapsed}. Open positions: {len(self.open_positions)}")
            
            # Get current data for all stocks at this timestamp
            current_stocks_data = df[df['datetime'] == timestamp]
            
            # Update position hold times
            for stock_code in list(self.open_positions.keys()):
                self.open_positions[stock_code]['candles_held'] += 1
            
            # Process each stock at this timestamp
            for _, current_row in current_stocks_data.iterrows():
                stock_code = current_row['stock_code']
                
                # Get the stock's processed data up to this point
                stock_data = processed_stocks[stock_code]
                
                # Find the current row index in the stock's data
                current_idx = stock_data[stock_data['datetime'] == timestamp].index
                if len(current_idx) == 0:
                    continue
                
                current_idx = current_idx[0]
                
                # Skip if not enough historical data for indicators
                if current_idx < 30:
                    continue
                
                current_data = stock_data.iloc[current_idx]
                
                # Generate ML features
                try:
                    ml_features_df = self.generate_ml_features(stock_data.iloc[:current_idx+1])
                    if len(ml_features_df) > 0:
                        current_ml_features = ml_features_df.iloc[-1]
                    else:
                        current_ml_features = None
                except Exception as e:
                    logger.error(f"Error generating ML features for {stock_code}: {e}")
                    current_ml_features = None
                
                # Check for exit signals first (existing positions)
                if stock_code in self.open_positions:
                    should_exit, exit_reason = self.should_exit_position(stock_code, current_data, self.open_positions[stock_code])
                    if should_exit:
                        self.execute_exit(stock_code, current_data, exit_reason)
                
                # Check for entry signals (if no position)
                elif current_ml_features is not None:
                    should_enter, entry_reason = self.should_enter_position(stock_code, current_data, current_ml_features)
                    if should_enter:
                        self.execute_entry(stock_code, current_data, entry_reason)
        
        # Close any remaining positions at the end
        logger.info("Closing remaining positions...")
        final_data = {}
        for stock_code in list(self.open_positions.keys()):
            stock_data = processed_stocks[stock_code]
            final_data[stock_code] = stock_data.iloc[-1]
        
        for stock_code in list(self.open_positions.keys()):
            self.execute_exit(stock_code, final_data[stock_code], "END_OF_SIMULATION")
        
        logger.info("Simulation completed!")
        return self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive trading report"""
        if not self.trade_ledger:
            return "No trades executed during simulation."
        
        df_trades = pd.DataFrame(self.trade_ledger)
        
        # Calculate statistics
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['pnl'] > 0])
        losing_trades = len(df_trades[df_trades['pnl'] <= 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        total_pnl_pct = ((self.capital - self.initial_capital) / self.initial_capital) * 100
        
        avg_win = df_trades[df_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[df_trades['pnl'] <= 0]['pnl'].mean() if losing_trades > 0 else 0
        
        avg_hold_time = df_trades['candles_held'].mean() * 5 / 60  # Convert to hours
        
        # Stock-wise performance
        stock_performance = df_trades.groupby('stock_code').agg({
            'pnl': ['sum', 'count'],
            'pnl_pct': 'mean'
        }).round(2)
        
        report = f"""
=== MULTI-STOCK TRADING SIMULATION REPORT ===

PORTFOLIO PERFORMANCE:
- Initial Capital: ₹{self.initial_capital:,.2f}
- Final Capital: ₹{self.capital:,.2f}
- Total P&L: ₹{total_pnl:,.2f}
- Total Return: {total_pnl_pct:.2f}%

TRADING STATISTICS:
- Total Trades: {total_trades}
- Winning Trades: {winning_trades}
- Losing Trades: {losing_trades}
- Win Rate: {win_rate:.1f}%
- Average Win: ₹{avg_win:,.2f}
- Average Loss: ₹{avg_loss:,.2f}
- Average Hold Time: {avg_hold_time:.1f} hours

STOCK-WISE PERFORMANCE:
{stock_performance}

RECENT TRADES (Last 10):
"""
        
        # Show last 10 trades
        recent_trades = df_trades.tail(10)
        for _, trade in recent_trades.iterrows():
            report += f"\n{trade['entry_datetime'].strftime('%Y-%m-%d %H:%M')} | "
            report += f"{trade['stock_code']} | "
            report += f"₹{trade['entry_price']:.2f} → ₹{trade['exit_price']:.2f} | "
            report += f"P&L: ₹{trade['pnl']:,.2f} ({trade['pnl_pct']:+.2f}%) | "
            report += f"Hold: {trade['candles_held']}x5min | "
            report += f"Exit: {trade['exit_reason']}"
        
        # Save detailed trade ledger
        df_trades.to_csv('multi_stock_trade_ledger.csv', index=False)
        report += f"\n\nDetailed trade ledger saved to 'multi_stock_trade_ledger.csv'"
        
        return report

def main():
    """Main simulation execution"""
    try:
        # Initialize simulator
        simulator = MultiStockTradingSimulator(
            ml_model_path='model/trading_model.pkl',
            initial_capital=1000000  # 10 Lakh initial capital
        )
        
        # Run simulation
        data_file = 'data/NSE_AllStocks_historical_data_5min.csv'
        report = simulator.run_simulation(data_file)
        
        print(report)
        
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        raise

if __name__ == "__main__":
    main()