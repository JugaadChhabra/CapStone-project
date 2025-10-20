#!/usr/bin/env python3
"""
Automated Trading Bot - Complete Trade Management System

PURPOSE: Simple automated trading system that handles complete trade lifecycle
FEATURES:
├── Market timing (9:15 AM - 3:30 PM)
├── Strategy execution (2% movers + momentum + OI filter)
├── Automated trade entry and exit
├── Risk management (stop loss, target profit)
├── Position monitoring until market close
└── Daily trade summary and cleanup

USAGE: Simply run this file and let it handle everything automatically
"""

import time, json, logging, signal, sys
from datetime import datetime, time as dt_time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Import our optimized modules
from icici_functions import get_env_config, create_api_headers
from websocket_connection import WebSocketManager
from Live_Data_Stream import run_trading_strategy, load_stock_data, cleanup
from data_loader import get_all_previous_day_closes

# Import configuration
try:
    import trading_config as config
except ImportError:
    # Default config if file doesn't exist
    class config:
        MAX_POSITIONS = 5
        POSITION_SIZE = 1000
        STOP_LOSS_PERCENT = 2.0
        TARGET_PROFIT_PERCENT = 4.0
        MARKET_OPEN_TIME = "09:15"
        MARKET_CLOSE_TIME = "15:30"
        STRATEGY_START_TIME = "09:20"
        POSITION_CHECK_INTERVAL = 10
        MOMENTUM_WAIT_TIME = 10.0

@dataclass
class Trade:
    """Trade data structure"""
    symbol: str
    entry_price: float
    entry_time: datetime
    quantity: int
    direction: str  # 'LONG' or 'SHORT'
    stop_loss: float
    target: float
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    status: str = 'OPEN'  # 'OPEN', 'CLOSED', 'STOPPED'
    pnl: float = 0.0

class AutomatedTrader:
    """Complete automated trading system"""
    
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Trading configuration from config file
        self.max_positions = config.MAX_POSITIONS
        self.position_size = config.POSITION_SIZE
        self.stop_loss_pct = config.STOP_LOSS_PERCENT
        self.target_profit_pct = config.TARGET_PROFIT_PERCENT
        
        # Market timing from config
        market_open_str = config.MARKET_OPEN_TIME.split(":")
        market_close_str = config.MARKET_CLOSE_TIME.split(":")
        strategy_start_str = config.STRATEGY_START_TIME.split(":")
        
        self.market_open = dt_time(int(market_open_str[0]), int(market_open_str[1]))
        self.market_close = dt_time(int(market_close_str[0]), int(market_close_str[1]))
        self.strategy_time = dt_time(int(strategy_start_str[0]), int(strategy_start_str[1]))
        
        # State management
        self.trades: List[Trade] = []
        self.candidates = []
        self.previous_closes = {}
        self.ws_manager = None
        self.running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def setup_logging(self):
        """Setup comprehensive logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)s | %(message)s',
            handlers=[
                logging.FileHandler(f'trading_log_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info("🛑 Shutdown signal received. Closing positions...")
        self.running = False
        self.close_all_positions()
        self.cleanup_and_exit()
    
    def is_market_hours(self) -> bool:
        """Check if market is open"""
        current_time = datetime.now().time()
        return self.market_open <= current_time <= self.market_close
    
    def wait_for_market_open(self):
        """Wait until market opens"""
        while True:
            current_time = datetime.now().time()
            if current_time >= self.market_open:
                break
                
            time_to_open = datetime.combine(datetime.today(), self.market_open) - \
                          datetime.combine(datetime.today(), current_time)
            
            self.logger.info(f"⏰ Market opens in {time_to_open}. Waiting...")
            time.sleep(60)  # Check every minute
    
    def get_trading_candidates(self) -> List[str]:
        """Execute trading strategy to get final candidates"""
        self.logger.info("🎯 Executing trading strategy to find candidates...")
        
        try:
            # Step 1: Get previous day closes
            self.logger.info("📊 Getting previous day closing prices...")
            self.previous_closes = get_all_previous_day_closes()
            self.logger.info(f"✅ Got {len(self.previous_closes)} previous closes")
            
            # Step 2: Initialize stock data
            self.logger.info("📈 Loading stock data for analysis...")
            stock_data, websocket_codes = load_stock_data()
            self.logger.info(f"✅ Loaded {len(stock_data)} stocks")
            
            # Step 3: Run strategy to find movers
            self.logger.info("🔍 Running strategy to find 2% movers...")
            candidates = run_trading_strategy(wait_time=config.MOMENTUM_WAIT_TIME)
            
            if candidates:
                self.logger.info(f"🎯 Found {len(candidates)} trading candidates: {candidates}")
                return candidates[:self.max_positions]  # Limit to max positions
            else:
                self.logger.warning("⚠️ No trading candidates found")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error getting candidates: {e}")
            return []
    
    def calculate_trade_params(self, symbol: str, current_price: float) -> Dict:
        """Calculate trade parameters (quantity, stop loss, target)"""
        quantity = max(1, int(self.position_size / current_price))
        
        # Calculate stop loss and target based on direction
        # For now, assuming LONG trades (can be enhanced for SHORT)
        stop_loss = current_price * (1 - self.stop_loss_pct / 100)
        target = current_price * (1 + self.target_profit_pct / 100)
        
        return {
            'quantity': quantity,
            'stop_loss': stop_loss,
            'target': target,
            'direction': 'LONG'
        }
    
    def place_trade(self, symbol: str, current_price: float) -> Optional[Trade]:
        """
        Place a trade (mock implementation - replace with actual order API)
        
        NOTE: This is a mock implementation. In production, you would:
        1. Use ICICI Direct's order placement API
        2. Handle order confirmation
        3. Deal with partial fills, rejections, etc.
        """
        try:
            trade_params = self.calculate_trade_params(symbol, current_price)
            
            # Mock order placement - replace with actual API call
            self.logger.info(f"📤 MOCK ORDER: BUY {trade_params['quantity']} shares of {symbol} at ₹{current_price:.2f}")
            
            # Create trade record
            trade = Trade(
                symbol=symbol,
                entry_price=current_price,
                entry_time=datetime.now(),
                quantity=trade_params['quantity'],
                direction=trade_params['direction'],
                stop_loss=trade_params['stop_loss'],
                target=trade_params['target']
            )
            
            self.trades.append(trade)
            self.logger.info(f"✅ Trade placed: {symbol} | Entry: ₹{current_price:.2f} | SL: ₹{trade.stop_loss:.2f} | Target: ₹{trade.target:.2f}")
            
            return trade
            
        except Exception as e:
            self.logger.error(f"❌ Error placing trade for {symbol}: {e}")
            return None
    
    def close_trade(self, trade: Trade, exit_price: float, reason: str) -> bool:
        """
        Close a trade (mock implementation)
        
        NOTE: Replace with actual order API in production
        """
        try:
            # Mock order closure - replace with actual API call
            self.logger.info(f"📤 MOCK ORDER: SELL {trade.quantity} shares of {trade.symbol} at ₹{exit_price:.2f}")
            
            # Update trade record
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            trade.status = 'CLOSED' if reason != 'STOP_LOSS' else 'STOPPED'
            
            # Calculate P&L
            if trade.direction == 'LONG':
                trade.pnl = (exit_price - trade.entry_price) * trade.quantity
            else:
                trade.pnl = (trade.entry_price - exit_price) * trade.quantity
            
            self.logger.info(f"✅ Trade closed: {trade.symbol} | Exit: ₹{exit_price:.2f} | P&L: ₹{trade.pnl:.2f} | Reason: {reason}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error closing trade for {trade.symbol}: {e}")
            return False
    
    def monitor_positions(self):
        """Monitor open positions for stop loss/target hit"""
        if not self.ws_manager:
            return
            
        current_prices = self.ws_manager.get_current_prices()
        
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
                
            # Find current price for this trade
            current_price = None
            for code, price_data in current_prices.items():
                if price_data.get('symbol') == trade.symbol:
                    current_price = price_data.get('ltp', 0)
                    break
            
            if not current_price:
                continue
                
            # Check stop loss
            if (trade.direction == 'LONG' and current_price <= trade.stop_loss) or \
               (trade.direction == 'SHORT' and current_price >= trade.stop_loss):
                self.logger.warning(f"🛑 Stop loss hit for {trade.symbol} at ₹{current_price:.2f}")
                self.close_trade(trade, current_price, 'STOP_LOSS')
                
            # Check target
            elif (trade.direction == 'LONG' and current_price >= trade.target) or \
                 (trade.direction == 'SHORT' and current_price <= trade.target):
                self.logger.info(f"🎯 Target hit for {trade.symbol} at ₹{current_price:.2f}")
                self.close_trade(trade, current_price, 'TARGET')
    
    def close_all_positions(self):
        """Close all open positions at market close"""
        if not self.ws_manager:
            return
            
        self.logger.info("🔄 Closing all open positions at market close...")
        current_prices = self.ws_manager.get_current_prices()
        
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
                
            # Find current price
            current_price = None
            for code, price_data in current_prices.items():
                if price_data.get('symbol') == trade.symbol:
                    current_price = price_data.get('ltp', trade.entry_price)  # Fallback to entry price
                    break
            
            if current_price:
                self.close_trade(trade, current_price, 'MARKET_CLOSE')
    
    def generate_daily_summary(self):
        """Generate and save daily trading summary"""
        total_trades = len(self.trades)
        closed_trades = [t for t in self.trades if t.status in ['CLOSED', 'STOPPED']]
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
        
        summary = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_trades": total_trades,
            "closed_trades": len(closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "trades": [asdict(trade) for trade in self.trades]
        }
        
        # Save summary
        filename = f"trading_summary_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        # Log summary
        self.logger.info("📊 DAILY TRADING SUMMARY")
        self.logger.info("=" * 50)
        self.logger.info(f"📈 Total Trades: {total_trades}")
        self.logger.info(f"✅ Closed Trades: {len(closed_trades)}")
        self.logger.info(f"🎯 Win Rate: {win_rate:.1f}%")
        self.logger.info(f"💰 Total P&L: ₹{total_pnl:.2f}")
        self.logger.info(f"💾 Summary saved: {filename}")
        
        return summary
    
    def cleanup_and_exit(self):
        """Clean up resources and exit"""
        self.logger.info("🧹 Cleaning up resources...")
        
        try:
            if self.ws_manager:
                self.ws_manager.disconnect()
            cleanup()  # Call cleanup from Live_Data_Stream
            
            self.generate_daily_summary()
            self.logger.info("✅ Cleanup completed. Goodbye!")
            
        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")
        
        sys.exit(0)
    
    def run(self):
        """Main trading loop"""
        self.logger.info("🚀 AUTOMATED TRADER STARTING")
        self.logger.info("=" * 60)
        self.logger.info(f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
        self.logger.info(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
        self.logger.info("=" * 60)
        
        try:
            # Wait for market to open
            if not self.is_market_hours():
                self.wait_for_market_open()
            
            self.logger.info("🟢 Market is open. Starting trading operations...")
            
            # Wait until strategy time (9:20 AM)
            while datetime.now().time() < self.strategy_time:
                self.logger.info(f"⏰ Waiting for strategy time ({self.strategy_time})")
                time.sleep(30)
            
            # Get trading candidates
            self.candidates = self.get_trading_candidates()
            
            if not self.candidates:
                self.logger.warning("⚠️ No trading candidates found. Monitoring mode only.")
            
            # Initialize WebSocket for live monitoring
            from websocket_connection import WebSocketManager
            from Live_Data_Stream import _websocket_codes
            
            self.ws_manager = WebSocketManager()
            self.ws_manager.connect()
            
            if _websocket_codes:
                self.ws_manager.subscribe_to_codes(_websocket_codes)
                time.sleep(5)  # Wait for subscription
            
            # Place initial trades
            if self.candidates and self.ws_manager:
                current_prices = self.ws_manager.get_current_prices()
                
                for symbol in self.candidates:
                    # Find current price for this symbol
                    current_price = None
                    for code, price_data in current_prices.items():
                        if price_data.get('symbol') == symbol:
                            current_price = price_data.get('ltp', 0)
                            break
                    
                    if current_price and current_price > 0:
                        trade = self.place_trade(symbol, current_price)
                        if trade:
                            time.sleep(1)  # Spacing between orders
            
            # Main monitoring loop
            self.logger.info("🔄 Starting position monitoring loop...")
            
            while self.running and self.is_market_hours():
                try:
                    self.monitor_positions()
                    time.sleep(config.POSITION_CHECK_INTERVAL)  # Check interval from config
                    
                except Exception as e:
                    self.logger.error(f"❌ Error in monitoring loop: {e}")
                    time.sleep(30)  # Wait longer on error
            
            # Market close - cleanup
            if not self.is_market_hours():
                self.logger.info("🔔 Market closed. Closing all positions...")
                self.close_all_positions()
            
        except Exception as e:
            self.logger.error(f"❌ Critical error in trading system: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.cleanup_and_exit()

def main():
    """Entry point for automated trader"""
    try:
        # Check environment setup
        env_config = get_env_config()
        print("✅ Environment configuration loaded")
        
        # Start automated trader
        trader = AutomatedTrader()
        trader.run()
        
    except Exception as e:
        print(f"❌ Failed to start automated trader: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()