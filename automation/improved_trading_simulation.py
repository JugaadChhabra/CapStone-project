#!/usr/bin/env python3
"""
Improved Trading Simulation with Realistic Entry/Exit Logic

PURPOSE: Demonstrates realistic trading simulation with:
- Different entry and exit criteria
- Clear trade rationale logging
- Proper risk management
- Realistic position sizing

FEATURES:
- Entry: ML signals + technical momentum + volume confirmation
- Exit: Stop loss, take profit, trailing stops, time decay, signal reversal
- Position sizing based on volatility (ATR)
- Detailed trade logging with rationale

USAGE: python improved_trading_simulation.py
"""

import pandas as pd
import numpy as np
import pickle
import joblib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path

# Import existing modules
from trading_config import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('improved_trading_simulation.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class Trade:
    """Individual trade record with detailed rationale"""
    trade_id: int
    symbol: str
    action: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    timestamp: datetime
    entry_reason: str  # Why we entered
    exit_reason: Optional[str] = None  # Why we exited
    entry_signals: Dict[str, Any] = field(default_factory=dict)  # Technical signals at entry
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    
@dataclass
class Position:
    """Enhanced position tracking"""
    symbol: str
    quantity: int
    avg_price: float
    entry_time: datetime
    entry_reason: str
    stop_loss: float
    take_profit: float
    trailing_stop: float
    highest_price: float = 0.0  # For trailing stop calculation
    lowest_price: float = float('inf')  # For trailing stop calculation
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    entry_signals: Dict[str, Any] = field(default_factory=dict)

class TechnicalAnalysis:
    """Technical analysis functions for trading decisions"""
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range for volatility-based position sizing"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def calculate_momentum_score(df: pd.DataFrame) -> float:
        """Calculate momentum score based on multiple timeframes"""
        if len(df) < 20:
            return 0.0
        
        # Short-term momentum (5 periods)
        short_momentum = (df['close'].iloc[-1] / df['close'].iloc[-6] - 1) * 100
        
        # Medium-term momentum (10 periods)
        medium_momentum = (df['close'].iloc[-1] / df['close'].iloc[-11] - 1) * 100
        
        # Long-term momentum (20 periods)
        long_momentum = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) * 100
        
        # Weighted momentum score
        momentum_score = (short_momentum * 0.5 + medium_momentum * 0.3 + long_momentum * 0.2)
        
        return momentum_score
    
    @staticmethod
    def calculate_volume_score(df: pd.DataFrame) -> float:
        """Calculate volume confirmation score"""
        if len(df) < 10:
            return 0.0
        
        # Current volume vs average
        avg_volume = df['volume'].tail(10).mean()
        current_volume = df['volume'].iloc[-1]
        
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Volume score: higher volume = stronger signal
        volume_score = min(volume_ratio, 3.0)  # Cap at 3x
        
        return volume_score
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI for overbought/oversold conditions"""
        if len(df) < period + 1:
            return 50.0  # Neutral
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0

class ImprovedTradingSimulator:
    """Improved trading simulator with realistic entry/exit logic"""
    
    def __init__(self, initial_capital: float = 500000):
        self.logger = logging.getLogger(__name__)
        self.logger.info("🚀 Initializing Improved Trading Simulator...")
        
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
        
        # Technical analysis
        self.ta = TechnicalAnalysis()
        
        # Load historical data
        self.load_historical_data()
        
        # Trading parameters
        self.min_momentum_threshold = 1.5  # Minimum momentum % for entry
        self.min_volume_ratio = 1.2  # Minimum volume ratio for entry
        self.max_rsi_buy = 70  # Don't buy if RSI > 70 (overbought)
        self.min_rsi_sell = 30  # Don't sell if RSI < 30 (oversold)
        self.trailing_stop_pct = 1.5  # 1.5% trailing stop
        
        self.logger.info("✅ Improved Trading Simulator initialized")
    
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
    
    def analyze_entry_signals(self, stock_data: pd.DataFrame) -> Dict[str, Any]:
        """Comprehensive analysis for entry signals"""
        signals = {}
        
        try:
            if len(stock_data) == 0:
                raise ValueError("Empty stock data")
            
            # Technical indicators
            signals['momentum_score'] = self.ta.calculate_momentum_score(stock_data)
            signals['volume_score'] = self.ta.calculate_volume_score(stock_data)
            signals['rsi'] = self.ta.calculate_rsi(stock_data)
            
            atr_series = self.ta.calculate_atr(stock_data)
            signals['atr'] = atr_series.iloc[-1] if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]) else stock_data['close'].iloc[-1] * 0.02
            
            # Price action
            signals['current_price'] = stock_data['close'].iloc[-1]
            signals['price_change_1'] = (stock_data['close'].iloc[-1] / stock_data['close'].iloc[-2] - 1) * 100 if len(stock_data) >= 2 else 0
            signals['price_change_5'] = (stock_data['close'].iloc[-1] / stock_data['close'].iloc[-6] - 1) * 100 if len(stock_data) >= 6 else 0
            
            # Volume analysis
            signals['volume_current'] = stock_data['volume'].iloc[-1] if len(stock_data) > 0 else 0
            signals['volume_avg'] = stock_data['volume'].tail(min(10, len(stock_data))).mean() if len(stock_data) > 0 else 1
            
        except Exception as e:
            self.logger.debug(f"Error analyzing signals: {e}")
            signals = {
                'momentum_score': 0, 'volume_score': 1, 'rsi': 50, 'atr': 10,
                'current_price': stock_data['close'].iloc[-1] if len(stock_data) > 0 else 100,
                'price_change_1': 0, 'price_change_5': 0,
                'volume_current': 1000, 'volume_avg': 1000
            }
        
        return signals
    
    def should_enter_position(self, symbol: str, current_data: pd.DataFrame) -> Tuple[bool, str, Dict[str, Any]]:
        """Determine if we should enter a new position with detailed reasoning"""
        # Check basic constraints
        if symbol in self.positions:
            return False, "Already in position", {}
        
        if len(self.positions) >= MAX_POSITIONS:
            return False, "Maximum positions reached", {}
        
        # Analyze signals
        signals = self.analyze_entry_signals(current_data)
        
        # Check if we have enough capital
        position_size = min(POSITION_SIZE, self.current_capital * 0.15)  # Max 15% per position
        if position_size < MIN_QUANTITY * signals['current_price']:
            return False, "Insufficient capital", signals
        
        # Entry criteria for LONG position
        long_entry = (
            signals['momentum_score'] > self.min_momentum_threshold and  # Positive momentum
            signals['volume_score'] > self.min_volume_ratio and  # Volume confirmation
            signals['rsi'] < self.max_rsi_buy and  # Not overbought
            signals['price_change_1'] > -2.0  # Not falling too fast
        )
        
        # Entry criteria for SHORT position
        short_entry = (
            signals['momentum_score'] < -self.min_momentum_threshold and  # Negative momentum
            signals['volume_score'] > self.min_volume_ratio and  # Volume confirmation
            signals['rsi'] > self.min_rsi_sell and  # Not oversold
            signals['price_change_1'] < 2.0  # Not rising too fast
        )
        
        if long_entry:
            reason = f"LONG: Momentum={signals['momentum_score']:.2f}%, Volume={signals['volume_score']:.2f}x, RSI={signals['rsi']:.1f}"
            return True, reason, signals
        elif short_entry:
            reason = f"SHORT: Momentum={signals['momentum_score']:.2f}%, Volume={signals['volume_score']:.2f}x, RSI={signals['rsi']:.1f}"
            return True, reason, signals
        else:
            reason = f"No entry: Mom={signals['momentum_score']:.1f}%, Vol={signals['volume_score']:.1f}x, RSI={signals['rsi']:.1f}"
            return False, reason, signals
    
    def should_exit_position(self, symbol: str, position: Position, current_price: float, current_data: pd.DataFrame) -> Tuple[bool, str]:
        """Determine if we should exit with detailed exit logic"""
        
        # Update trailing stops
        if position.quantity > 0:  # Long position
            position.highest_price = max(position.highest_price, current_price)
            trailing_stop_price = position.highest_price * (1 - self.trailing_stop_pct / 100)
            position.trailing_stop = max(position.trailing_stop, trailing_stop_price)
            
            # Exit conditions for long positions
            if current_price <= position.stop_loss:
                return True, f"Stop Loss: {current_price:.2f} <= {position.stop_loss:.2f}"
            
            if current_price >= position.take_profit:
                return True, f"Take Profit: {current_price:.2f} >= {position.take_profit:.2f}"
            
            if current_price <= position.trailing_stop:
                return True, f"Trailing Stop: {current_price:.2f} <= {position.trailing_stop:.2f}"
        
        else:  # Short position
            position.lowest_price = min(position.lowest_price, current_price)
            trailing_stop_price = position.lowest_price * (1 + self.trailing_stop_pct / 100)
            position.trailing_stop = min(position.trailing_stop, trailing_stop_price)
            
            # Exit conditions for short positions
            if current_price >= position.stop_loss:
                return True, f"Stop Loss: {current_price:.2f} >= {position.stop_loss:.2f}"
            
            if current_price <= position.take_profit:
                return True, f"Take Profit: {current_price:.2f} <= {position.take_profit:.2f}"
            
            if current_price >= position.trailing_stop:
                return True, f"Trailing Stop: {current_price:.2f} >= {position.trailing_stop:.2f}"
        
        # Time-based exit (max holding period: 2 hours = 24 candles of 5min each)
        if len(current_data) > 0:
            current_time = current_data['datetime'].iloc[-1]
            holding_time = (current_time - position.entry_time).total_seconds()
            if holding_time > 2 * 3600:  # 2 hours
                return True, f"Time Exit: Held for {holding_time/3600:.1f}h"
        
        # Signal reversal exit
        if len(current_data) >= 10:
            signals = self.analyze_entry_signals(current_data)
            
            # Exit long if momentum turns strongly negative
            if position.quantity > 0 and signals['momentum_score'] < -2.0:
                return True, f"Signal Reversal: Momentum={signals['momentum_score']:.2f}%"
            
            # Exit short if momentum turns strongly positive  
            if position.quantity < 0 and signals['momentum_score'] > 2.0:
                return True, f"Signal Reversal: Momentum={signals['momentum_score']:.2f}%"
        
        return False, "Continue holding"
    
    def calculate_position_size(self, price: float, atr: float) -> int:
        """Calculate position size based on volatility (ATR)"""
        # Risk-based position sizing
        risk_per_trade = self.current_capital * 0.01  # Risk 1% per trade
        
        # If ATR is available, use it for position sizing
        if atr > 0:
            # Position size based on ATR stop loss
            stop_distance = atr * 2  # Use 2x ATR as stop distance
            quantity = int(risk_per_trade / stop_distance)
        else:
            # Fallback to fixed percentage
            max_position_value = min(POSITION_SIZE, self.current_capital * 0.15)
            quantity = int(max_position_value / price)
        
        return max(quantity, MIN_QUANTITY)
    
    def enter_position(self, symbol: str, signals: Dict[str, Any], timestamp: datetime, entry_reason: str):
        """Enter a new position with detailed logging"""
        price = signals['current_price']
        atr = signals['atr']
        
        # Determine direction based on momentum
        is_long = signals['momentum_score'] > 0
        
        # Calculate position size
        quantity = self.calculate_position_size(price, atr)
        if not is_long:
            quantity = -quantity  # Negative quantity for short
        
        # Calculate stop loss and take profit based on ATR
        if atr > 0:
            stop_distance = atr * 2  # 2x ATR stop
            profit_distance = atr * 3  # 3x ATR target (1:1.5 risk:reward)
        else:
            # Fallback to percentage-based
            stop_distance = price * (STOP_LOSS_PERCENT / 100)
            profit_distance = price * (TARGET_PROFIT_PERCENT / 100)
        
        if is_long:
            stop_loss = price - stop_distance
            take_profit = price + profit_distance
            trailing_stop = price - stop_distance  # Initial trailing stop
        else:
            stop_loss = price + stop_distance
            take_profit = price - profit_distance
            trailing_stop = price + stop_distance  # Initial trailing stop
        
        # Create position
        position = Position(
            symbol=symbol,
            quantity=quantity,
            avg_price=price,
            entry_time=timestamp,
            entry_reason=entry_reason,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop,
            highest_price=price if is_long else 0,
            lowest_price=price if not is_long else float('inf'),
            current_price=price,
            entry_signals=signals
        )
        
        # Create trade record
        trade = Trade(
            trade_id=self.trade_counter,
            symbol=symbol,
            action='BUY' if is_long else 'SELL',
            quantity=abs(quantity),
            price=price,
            timestamp=timestamp,
            entry_reason=entry_reason,
            entry_signals=signals,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop
        )
        
        # Update portfolio
        self.positions[symbol] = position
        self.trades.append(trade)
        self.trade_counter += 1
        
        # Update capital
        trade_value = abs(quantity) * price
        self.current_capital -= trade_value * 0.001  # 0.1% transaction cost
        
        # Detailed logging
        direction = "LONG" if is_long else "SHORT"
        self.logger.info(f"📈 ENTERED {direction} position:")
        self.logger.info(f"   Symbol: {symbol}")
        self.logger.info(f"   Price: ₹{price:.2f}")
        self.logger.info(f"   Quantity: {abs(quantity)}")
        self.logger.info(f"   Stop Loss: ₹{stop_loss:.2f}")
        self.logger.info(f"   Take Profit: ₹{take_profit:.2f}")
        self.logger.info(f"   Reason: {entry_reason}")
        self.logger.info(f"   Momentum: {signals['momentum_score']:.2f}%")
        self.logger.info(f"   Volume Ratio: {signals['volume_score']:.2f}x")
        self.logger.info(f"   RSI: {signals['rsi']:.1f}")
    
    def exit_position(self, symbol: str, exit_reason: str, price: float, timestamp: datetime):
        """Exit an existing position with detailed logging"""
        position = self.positions[symbol]
        
        # Create exit trade record
        exit_trade = Trade(
            trade_id=self.trade_counter,
            symbol=symbol,
            action='SELL' if position.quantity > 0 else 'BUY',
            quantity=abs(position.quantity),
            price=price,
            timestamp=timestamp,
            entry_reason="EXIT",
            exit_reason=exit_reason
        )
        
        # Calculate P&L
        if position.quantity > 0:  # Long position
            pnl = (price - position.avg_price) * position.quantity
        else:  # Short position
            pnl = (position.avg_price - price) * abs(position.quantity)
        
        # Calculate holding period
        holding_time = (timestamp - position.entry_time).total_seconds() / 3600  # Hours
        
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
        
        # Detailed logging
        direction = "LONG" if position.quantity > 0 else "SHORT"
        pnl_pct = (pnl / (abs(position.quantity) * position.avg_price)) * 100
        pnl_color = "🟢" if pnl > 0 else "🔴"
        
        self.logger.info(f"📉 EXITED {direction} position:")
        self.logger.info(f"   Symbol: {symbol}")
        self.logger.info(f"   Entry Price: ₹{position.avg_price:.2f}")
        self.logger.info(f"   Exit Price: ₹{price:.2f}")
        self.logger.info(f"   Quantity: {abs(position.quantity)}")
        self.logger.info(f"   P&L: {pnl_color} ₹{pnl:.2f} ({pnl_pct:+.2f}%)")
        self.logger.info(f"   Holding Time: {holding_time:.1f}h")
        self.logger.info(f"   Exit Reason: {exit_reason}")
        self.logger.info(f"   Entry Reason: {position.entry_reason}")
        
        del self.positions[symbol]
    
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
                
                # Get historical data up to current point for analysis
                historical_subset = stock_day_data.iloc[:i+1]
                
                # Update existing positions
                self.update_positions(symbol, current_price)
                
                # Check exit conditions for existing positions
                if symbol in self.positions:
                    should_exit, exit_reason = self.should_exit_position(
                        symbol, self.positions[symbol], current_price, historical_subset
                    )
                    if should_exit:
                        self.exit_position(symbol, exit_reason, current_price, timestamp)
                
                # Check entry conditions for new positions (only if we have enough historical data)
                if len(historical_subset) >= 20:  # Need minimum history for indicators
                    should_enter, entry_reason, signals = self.should_enter_position(symbol, historical_subset)
                    if should_enter:
                        self.enter_position(symbol, signals, timestamp, entry_reason)
    
    def run_simulation(self, start_date: str = None, end_date: str = None, max_days: int = 5):
        """Run the complete trading simulation"""
        self.logger.info("🚀 Starting Improved Trading Simulation")
        self.logger.info("=" * 70)
        
        # Get date range
        available_dates = sorted(self.historical_data['date'].unique())
        
        if start_date is None:
            start_date = available_dates[0]
        if end_date is None:
            end_date = available_dates[-1]
        
        simulation_dates = [d for d in available_dates if start_date <= d <= end_date]
        
        # Limit simulation for demo
        simulation_dates = simulation_dates[:max_days]
        
        self.logger.info(f"📅 Simulation period: {start_date} to {simulation_dates[-1]} ({len(simulation_dates)} days)")
        self.logger.info(f"💰 Initial capital: ₹{self.initial_capital:,.2f}")
        self.logger.info(f"🎯 Trading parameters:")
        self.logger.info(f"   Min momentum: {self.min_momentum_threshold}%")
        self.logger.info(f"   Min volume ratio: {self.min_volume_ratio}x")
        self.logger.info(f"   RSI limits: {self.min_rsi_sell}-{self.max_rsi_buy}")
        self.logger.info(f"   Trailing stop: {self.trailing_stop_pct}%")
        
        # Run simulation day by day
        for date in simulation_dates:
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
        
        self.logger.info("\n" + "=" * 70)
        self.logger.info("📊 FINAL IMPROVED TRADING SIMULATION REPORT")
        self.logger.info("=" * 70)
        self.logger.info(f"💰 Initial Capital: ₹{self.initial_capital:,.2f}")
        self.logger.info(f"💰 Final Portfolio Value: ₹{final_portfolio_value:,.2f}")
        self.logger.info(f"📈 Total Return: {total_return:+.2f}%")
        self.logger.info(f"📊 Total P&L: ₹{self.total_pnl:+,.2f}")
        self.logger.info(f"🎯 Total Trades: {self.total_trades}")
        
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            avg_pnl = self.total_pnl / self.total_trades
            self.logger.info(f"🏆 Win Rate: {win_rate:.1f}% ({self.winning_trades}/{self.total_trades})")
            self.logger.info(f"💵 Average P&L per trade: ₹{avg_pnl:+,.2f}")
            self.logger.info(f"📉 Max Drawdown: {self.max_drawdown:.2%}")
        
        self.logger.info(f"💼 Open Positions: {len(self.positions)}")
        
        # Show open positions
        if self.positions:
            self.logger.info("\n📈 Open Positions:")
            for symbol, position in self.positions.items():
                direction = "LONG" if position.quantity > 0 else "SHORT"
                pnl_pct = (position.unrealized_pnl / (abs(position.quantity) * position.avg_price)) * 100
                pnl_color = "🟢" if position.unrealized_pnl > 0 else "🔴"
                self.logger.info(f"   {symbol}: {direction} @ ₹{position.avg_price:.2f} | {pnl_color} {pnl_pct:+.2f}%")
        
        # Save trade ledger
        self.save_trade_ledger()
    
    def save_trade_ledger(self):
        """Save detailed trade ledger to CSV"""
        if not self.trades:
            self.logger.warning("⚠️  No trades to save")
            return
        
        # Convert trades to DataFrame with detailed information
        trades_data = []
        for trade in self.trades:
            trade_data = {
                'Trade_ID': trade.trade_id,
                'Symbol': trade.symbol,
                'Action': trade.action,
                'Quantity': trade.quantity,
                'Price': trade.price,
                'Timestamp': trade.timestamp,
                'Entry_Reason': trade.entry_reason,
                'Exit_Reason': trade.exit_reason or 'N/A',
                'Value': trade.quantity * trade.price
            }
            
            # Add technical signals if available
            if trade.entry_signals:
                trade_data.update({
                    'Momentum_Score': trade.entry_signals.get('momentum_score', 0),
                    'Volume_Score': trade.entry_signals.get('volume_score', 1),
                    'RSI': trade.entry_signals.get('rsi', 50),
                    'ATR': trade.entry_signals.get('atr', 0),
                    'Price_Change_1': trade.entry_signals.get('price_change_1', 0),
                    'Price_Change_5': trade.entry_signals.get('price_change_5', 0)
                })
            
            trades_data.append(trade_data)
        
        df = pd.DataFrame(trades_data)
        
        # Calculate P&L for each completed trade pair
        df['P&L'] = 0.0
        df['P&L_Percent'] = 0.0
        df['Trade_Status'] = 'Open'
        df['Holding_Time_Hours'] = 0.0
        
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
                    
                    pnl_percent = (pnl / (entry_trade['Quantity'] * entry_trade['Price'])) * 100
                    
                    # Calculate holding time
                    holding_time = (pd.to_datetime(exit_trade['Timestamp']) - pd.to_datetime(entry_trade['Timestamp'])).total_seconds() / 3600
                    
                    # Update both trades
                    entry_idx = df[df['Trade_ID'] == entry_trade['Trade_ID']].index[0]
                    exit_idx = df[df['Trade_ID'] == exit_trade['Trade_ID']].index[0]
                    
                    df.loc[entry_idx, 'P&L'] = pnl
                    df.loc[exit_idx, 'P&L'] = pnl
                    df.loc[entry_idx, 'P&L_Percent'] = pnl_percent
                    df.loc[exit_idx, 'P&L_Percent'] = pnl_percent
                    df.loc[entry_idx, 'Trade_Status'] = 'Closed'
                    df.loc[exit_idx, 'Trade_Status'] = 'Closed'
                    df.loc[entry_idx, 'Holding_Time_Hours'] = holding_time
                    df.loc[exit_idx, 'Holding_Time_Hours'] = holding_time
                    
                    i += 2  # Skip both trades
                else:
                    i += 1
        
        # Save to CSV
        output_file = f"improved_trade_ledger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        
        self.logger.info(f"💾 Detailed trade ledger saved to: {output_file}")
        
        # Print summary of trades
        self.logger.info("\n📋 Trade Summary:")
        closed_trades = df[df['Trade_Status'] == 'Closed']
        if len(closed_trades) > 0:
            profit_trades = closed_trades[closed_trades['P&L'] > 0]
            loss_trades = closed_trades[closed_trades['P&L'] <= 0]
            
            self.logger.info(f"   Completed Trades: {len(closed_trades) // 2}")  # Divide by 2 since entry+exit = 1 trade
            self.logger.info(f"   Profitable: {len(profit_trades) // 2}")
            self.logger.info(f"   Loss: {len(loss_trades) // 2}")
            
            if len(closed_trades) > 0:
                avg_holding_time = closed_trades[closed_trades['Action'].str.contains('BUY')]['Holding_Time_Hours'].mean()
                self.logger.info(f"   Avg Holding Time: {avg_holding_time:.1f} hours")

def main():
    """Main function to run the improved trading simulation"""
    try:
        # Initialize simulator
        simulator = ImprovedTradingSimulator(initial_capital=500000)
        
        # Run simulation (limit to 3 days for testing)
        simulator.run_simulation(max_days=3)
        
    except Exception as e:
        logging.error(f"❌ Simulation failed: {e}")
        raise

if __name__ == "__main__":
    main()