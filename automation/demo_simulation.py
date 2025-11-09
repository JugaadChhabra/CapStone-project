#!/usr/bin/env python3
"""
Demo Trading Simulation with Sample Trades

PURPOSE: Demonstrates the trading simulation with actual trades generated
FEATURES:
- Uses simple momentum strategy to ensure trades are generated
- Creates a proper trade ledger with entry/exit records
- Shows P&L calculation and portfolio tracking
- Generates sample reports

USAGE: python demo_simulation.py
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DemoTradingSimulator:
    """Simple trading simulator that guarantees some trades for demonstration"""
    
    def __init__(self, initial_capital: float = 500000):
        self.logger = logging.getLogger(__name__)
        self.logger.info("🚀 Initializing Demo Trading Simulator...")
        
        # Portfolio state
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.trades = []
        self.trade_counter = 1
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        
        self.logger.info("✅ Demo Trading Simulator initialized")
    
    def simple_momentum_signal(self, data: pd.DataFrame) -> Tuple[int, float, str]:
        """Generate simple momentum-based signals"""
        if len(data) < 10:
            return 0, 0.5, "Insufficient data"
        
        # Calculate short-term momentum
        recent_data = data.tail(5)
        price_change = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
        
        # Calculate volume surge
        volume_avg = data['volume'].tail(10).mean()
        current_volume = recent_data['volume'].iloc[-1]
        volume_ratio = current_volume / volume_avg if volume_avg > 0 else 1
        
        # Generate signals based on momentum and volume
        if price_change > 0.02 and volume_ratio > 1.2:  # 2% price rise + volume surge
            return 1, 0.8, f"Strong upward momentum: {price_change:.1%} with volume surge"
        elif price_change < -0.02 and volume_ratio > 1.2:  # 2% price drop + volume surge
            return -1, 0.8, f"Strong downward momentum: {price_change:.1%} with volume surge"
        elif price_change > 0.01:  # 1% price rise
            return 1, 0.6, f"Moderate upward momentum: {price_change:.1%}"
        elif price_change < -0.01:  # 1% price drop
            return -1, 0.6, f"Moderate downward momentum: {price_change:.1%}"
        else:
            return 0, 0.5, f"No clear momentum: {price_change:.1%}"
    
    def enter_position(self, symbol: str, signal: int, price: float, timestamp: datetime, reason: str):
        """Enter a new position"""
        # Calculate position size (10% of capital or ₹50,000 max)
        max_position = min(50000, self.current_capital * 0.1)
        quantity = int(max_position / price)
        
        if quantity < 1:
            return False
        
        # Adjust for signal direction
        if signal == -1:
            quantity = -quantity  # Short position
        
        # Calculate stop loss and take profit
        if signal == 1:  # Long position
            stop_loss = price * 0.98  # 2% stop loss
            take_profit = price * 1.04  # 4% take profit
        else:  # Short position
            stop_loss = price * 1.02  # 2% stop loss
            take_profit = price * 0.96  # 4% take profit
        
        # Create position
        position = {
            'symbol': symbol,
            'quantity': quantity,
            'entry_price': price,
            'current_price': price,
            'entry_time': timestamp,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'unrealized_pnl': 0.0
        }
        
        # Create trade record
        trade = {
            'trade_id': self.trade_counter,
            'symbol': symbol,
            'action': 'BUY' if signal == 1 else 'SELL',
            'quantity': abs(quantity),
            'price': price,
            'timestamp': timestamp,
            'signal': reason,
            'value': abs(quantity) * price
        }
        
        # Update portfolio
        self.positions[symbol] = position
        self.trades.append(trade)
        self.trade_counter += 1
        
        # Update capital (subtract transaction costs)
        trade_value = abs(quantity) * price
        self.current_capital -= trade_value * 0.001  # 0.1% transaction cost
        
        self.logger.info(f"📈 ENTERED {trade['action']} position: {symbol} @ ₹{price:.2f} qty:{abs(quantity)} | {reason}")
        return True
    
    def exit_position(self, symbol: str, reason: str, price: float, timestamp: datetime):
        """Exit an existing position"""
        position = self.positions[symbol]
        
        # Create exit trade record
        exit_trade = {
            'trade_id': self.trade_counter,
            'symbol': symbol,
            'action': 'SELL' if position['quantity'] > 0 else 'BUY',
            'quantity': abs(position['quantity']),
            'price': price,
            'timestamp': timestamp,
            'signal': reason,
            'value': abs(position['quantity']) * price
        }
        
        # Calculate P&L
        if position['quantity'] > 0:  # Long position
            pnl = (price - position['entry_price']) * position['quantity']
        else:  # Short position
            pnl = (position['entry_price'] - price) * abs(position['quantity'])
        
        # Update portfolio
        trade_value = abs(position['quantity']) * price
        self.current_capital += trade_value - (trade_value * 0.001)  # Subtract transaction cost
        self.current_capital += pnl
        
        # Update statistics
        self.total_trades += 1
        self.total_pnl += pnl
        if pnl > 0:
            self.winning_trades += 1
        
        self.trades.append(exit_trade)
        self.trade_counter += 1
        del self.positions[symbol]
        
        pnl_color = "🟢" if pnl > 0 else "🔴"
        self.logger.info(f"📉 EXITED position: {symbol} @ ₹{price:.2f} | P&L: {pnl_color} ₹{pnl:.2f} | {reason}")
    
    def update_position(self, symbol: str, current_price: float):
        """Update position with current price and check exit conditions"""
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        position['current_price'] = current_price
        
        # Calculate unrealized P&L
        if position['quantity'] > 0:  # Long position
            position['unrealized_pnl'] = (current_price - position['entry_price']) * position['quantity']
        else:  # Short position
            position['unrealized_pnl'] = (position['entry_price'] - current_price) * abs(position['quantity'])
    
    def should_exit_position(self, symbol: str, current_price: float) -> Tuple[bool, str]:
        """Check if we should exit a position"""
        position = self.positions[symbol]
        
        # Check stop loss
        if position['quantity'] > 0:  # Long position
            if current_price <= position['stop_loss']:
                return True, "Stop loss triggered"
            if current_price >= position['take_profit']:
                return True, "Take profit triggered"
        else:  # Short position
            if current_price >= position['stop_loss']:
                return True, "Stop loss triggered"
            if current_price <= position['take_profit']:
                return True, "Take profit triggered"
        
        # Check time-based exit (hold for max 2 hours = 24 candles of 5min each)
        current_time = datetime.now()
        time_diff = current_time - position['entry_time']
        if time_diff.total_seconds() > 2 * 3600:  # 2 hours
            return True, "Time-based exit (2 hours)"
        
        return False, "Hold position"
    
    def simulate_trading_day(self, date: str, stock_data: pd.DataFrame):
        """Simulate trading for a specific day and stock"""
        self.logger.info(f"\n🗓️  Simulating {date} for {stock_data['stock_code'].iloc[0] if len(stock_data) > 0 else 'Unknown'}")
        
        if len(stock_data) < 10:
            return
        
        symbol = stock_data['stock_code'].iloc[0]
        
        # Process each 5-minute interval
        for i in range(10, len(stock_data)):  # Start from 10th candle to have history
            current_row = stock_data.iloc[i]
            current_price = current_row['close']
            timestamp = pd.to_datetime(f"{current_row['date']} {current_row['time']}")
            
            # Get historical data up to current point
            historical_data = stock_data.iloc[:i+1]
            
            # Update existing position
            if symbol in self.positions:
                self.update_position(symbol, current_price)
                
                # Check exit conditions
                should_exit, exit_reason = self.should_exit_position(symbol, current_price)
                if should_exit:
                    self.exit_position(symbol, exit_reason, current_price, timestamp)
            
            # Check entry conditions (only if not in position and have enough history)
            elif len(self.positions) < 3:  # Max 3 positions
                signal, confidence, reason = self.simple_momentum_signal(historical_data)
                
                # Enter position if signal is strong enough
                if abs(signal) == 1 and confidence > 0.6:
                    self.enter_position(symbol, signal, current_price, timestamp, reason)
    
    def run_simulation(self):
        """Run the complete demo simulation"""
        self.logger.info("🚀 Starting Demo Trading Simulation")
        self.logger.info("=" * 60)
        
        # Load data
        data_path = Path("data/NSE_AllStocks_historical_data_5min.csv")
        
        if not data_path.exists():
            self.logger.error(f"❌ Data file not found: {data_path}")
            return
        
        df = pd.read_csv(data_path)
        
        # Filter to first stock and first few days for demo
        available_stocks = df['stock_code'].unique()
        demo_stock = available_stocks[0]
        available_dates = sorted(df['date'].unique())
        demo_dates = available_dates[:5]  # First 5 days
        
        self.logger.info(f"📊 Demo stock: {demo_stock}")
        self.logger.info(f"📅 Demo dates: {demo_dates[0]} to {demo_dates[-1]}")
        self.logger.info(f"💰 Initial capital: ₹{self.initial_capital:,.2f}")
        
        # Run simulation
        for date in demo_dates:
            day_data = df[(df['stock_code'] == demo_stock) & (df['date'] == date)].copy()
            if len(day_data) > 0:
                self.simulate_trading_day(date, day_data)
        
        # Close any remaining positions
        for symbol in list(self.positions.keys()):
            last_price = df[df['stock_code'] == symbol]['close'].iloc[-1]
            self.exit_position(symbol, "End of simulation", last_price, datetime.now())
        
        # Generate final report
        self.generate_report()
    
    def generate_report(self):
        """Generate final trading report"""
        final_portfolio_value = self.current_capital
        total_return = (final_portfolio_value - self.initial_capital) / self.initial_capital * 100
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 DEMO TRADING SIMULATION REPORT")
        self.logger.info("=" * 60)
        self.logger.info(f"💰 Initial Capital: ₹{self.initial_capital:,.2f}")
        self.logger.info(f"💰 Final Portfolio Value: ₹{final_portfolio_value:,.2f}")
        self.logger.info(f"📈 Total Return: {total_return:+.2f}%")
        self.logger.info(f"📊 Total P&L: ₹{self.total_pnl:+,.2f}")
        self.logger.info(f"🎯 Total Trades: {self.total_trades}")
        
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            self.logger.info(f"🏆 Win Rate: {win_rate:.1f}% ({self.winning_trades}/{self.total_trades})")
        
        # Save trade ledger
        self.save_trade_ledger()
    
    def save_trade_ledger(self):
        """Save trade ledger to CSV file"""
        if not self.trades:
            self.logger.warning("⚠️  No trades to save")
            return
        
        # Convert trades to DataFrame
        df = pd.DataFrame(self.trades)
        
        # Calculate P&L for trade pairs
        df['P&L'] = 0.0
        df['Trade_Status'] = 'Open'
        
        # Group trades by symbol and calculate P&L
        symbols = df['symbol'].unique()
        for symbol in symbols:
            symbol_trades = df[df['symbol'] == symbol]
            
            # Match entry and exit pairs
            for i in range(0, len(symbol_trades) - 1, 2):
                if i + 1 < len(symbol_trades):
                    entry_idx = symbol_trades.index[i]
                    exit_idx = symbol_trades.index[i + 1]
                    
                    entry_trade = symbol_trades.iloc[i]
                    exit_trade = symbol_trades.iloc[i + 1]
                    
                    # Calculate P&L
                    if entry_trade['action'] == 'BUY':
                        pnl = (exit_trade['price'] - entry_trade['price']) * entry_trade['quantity']
                    else:
                        pnl = (entry_trade['price'] - exit_trade['price']) * entry_trade['quantity']
                    
                    # Update both trades
                    df.loc[entry_idx, 'P&L'] = pnl
                    df.loc[exit_idx, 'P&L'] = pnl
                    df.loc[entry_idx, 'Trade_Status'] = 'Closed'
                    df.loc[exit_idx, 'Trade_Status'] = 'Closed'
        
        # Add percentage returns
        df['P&L_Percentage'] = (df['P&L'] / df['value']) * 100
        
        # Save to CSV
        output_file = f"demo_trade_ledger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        
        self.logger.info(f"💾 Demo trade ledger saved to: {output_file}")
        
        # Display sample trades
        self.logger.info("\n📋 Demo Trade Ledger:")
        print("\nTrade Details:")
        print(df[['trade_id', 'symbol', 'action', 'quantity', 'price', 'P&L', 'P&L_Percentage', 'signal']].to_string(index=False))

def main():
    """Main function to run the demo simulation"""
    try:
        simulator = DemoTradingSimulator(initial_capital=500000)
        simulator.run_simulation()
        
    except Exception as e:
        logging.error(f"❌ Demo simulation failed: {e}")
        raise

if __name__ == "__main__":
    main()