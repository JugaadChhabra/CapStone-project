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
from live_data_stream import run_trading_strategy, load_stock_data, cleanup
from data_loader import get_all_previous_day_closes
from order_management import OrderManager, OrderResponse

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
    order_id: Optional[str] = None  # ICICI Direct order ID
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_order_id: Optional[str] = None  # Exit order ID
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
        momentum_check_str = getattr(config, 'MOMENTUM_CHECK_TIME', '09:25').split(":")
        
        self.market_open = dt_time(int(market_open_str[0]), int(market_open_str[1]))
        self.market_close = dt_time(int(market_close_str[0]), int(market_close_str[1]))
        self.strategy_time = dt_time(int(strategy_start_str[0]), int(strategy_start_str[1]))  # 9:20 AM
        self.momentum_time = dt_time(int(momentum_check_str[0]), int(momentum_check_str[1]))  # 9:25 AM
        
        # State management
        self.trades: List[Trade] = []
        self.candidates = []
        self.previous_closes = {}
        self.ws_manager = None
        self.order_manager = None  # Will be initialized when needed
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
    
    def get_2_percent_movers_at_920(self) -> List[str]:
        """Step 1: Find 2% movers at 9:20 AM"""
        self.logger.info("🎯 STEP 1: Finding 2% Movers at 9:20 AM")
        self.logger.info("=" * 60)
        
        try:
            # Get previous day closes
            self.logger.info("📊 Getting previous day closing prices...")
            self.previous_closes = get_all_previous_day_closes()
            self.logger.info(f"✅ Got {len(self.previous_closes)} previous closes")
            
            # Initialize stock data
            self.logger.info("📈 Loading stock data for analysis...")
            stock_data, websocket_codes = load_stock_data()
            self.logger.info(f"✅ Loaded {len(stock_data)} stocks")
            
            # Find 2% movers only
            self.logger.info("🔍 Scanning for 2% movers...")
            movers = run_trading_strategy(wait_time=config.MOMENTUM_WAIT_TIME)
            
            if movers:
                self.logger.info(f"🎯 Found {len(movers)} stocks with 2%+ movement at 9:20 AM")
                for i, symbol in enumerate(movers, 1):
                    self.logger.info(f"   {i:2d}. � {symbol}")
                return movers
            else:
                self.logger.warning("⚠️ No 2% movers found at 9:20 AM")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error finding 2% movers: {e}")
            return []
    
    def get_final_trading_candidates(self, movers_920: List[str]) -> List[str]:
        """Step 2: Check momentum at 9:25 AM and filter by OI"""
        self.logger.info("🎯 STEP 2: Checking Momentum & OI at 9:25 AM")
        self.logger.info("=" * 60)
        
        if not movers_920:
            self.logger.warning("⚠️ No 9:20 movers to check momentum for")
            return []
        
        try:
            # Check momentum for 9:20 movers
            self.logger.info(f"⚡ Checking momentum for {len(movers_920)} stocks from 9:20...")
            momentum_candidates = run_trading_strategy(wait_time=config.MOMENTUM_WAIT_TIME)
            
            if not momentum_candidates:
                self.logger.warning("⚠️ No stocks maintained momentum from 9:20 to 9:25")
                return []
            
            self.logger.info(f"✅ {len(momentum_candidates)} stocks maintained momentum")
            for i, symbol in enumerate(momentum_candidates, 1):
                self.logger.info(f"   {i:2d}. ⚡ {symbol}")
            
            # Filter by OI data
            self.logger.info("🔍 Filtering by OI data (>= 7%)...")
            final_candidates = self.filter_by_oi(momentum_candidates)
            
            if final_candidates:
                self.logger.info(f"💎 FINAL TRADING CANDIDATES: {len(final_candidates)} stocks")
                for i, candidate in enumerate(final_candidates, 1):
                    symbol = candidate if isinstance(candidate, str) else candidate['symbol']
                    self.logger.info(f"   {i:2d}. 💎 {symbol}")
                return [c if isinstance(c, str) else c['symbol'] for c in final_candidates]
            else:
                self.logger.warning("⚠️ No candidates passed OI filter")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error checking momentum and OI: {e}")
            return []

    def get_trading_candidates(self) -> List[str]:
        """Execute complete trading strategy with proper timing - DEPRECATED"""
        # This method is kept for backward compatibility 
        # The new run() method handles timing properly with separate 9:20 and 9:25 steps
        self.logger.warning("⚠️ get_trading_candidates() is deprecated. Use timed strategy steps.")
        return []
    
    def filter_by_oi(self, candidates: List[str]) -> List[str]:
        """Filter candidates by OI change >= 7%"""
        try:
            import subprocess
            import pandas as pd
            
            # Run OI scraping
            self.logger.info("🕷️ Scraping OI data from NSE...")
            result = subprocess.run(['python3', 'scraping.py'], 
                                  capture_output=True, text=True, cwd='.')
            
            if result.returncode != 0:
                self.logger.error(f"❌ OI scraping failed: {result.stderr}")
                # Return original candidates if scraping fails
                self.logger.warning("⚠️ Proceeding without OI filter")
                return candidates
            
            self.logger.info("✅ OI scraping completed")
            
            # Load and process OI data
            import os
            if not os.path.exists("oi_spurts_nse_clean.csv"):
                self.logger.error("❌ OI data file not found")
                return candidates
            
            oi_df = pd.read_csv("oi_spurts_nse_clean.csv")
            self.logger.info(f"📊 Loaded OI data for {len(oi_df)} stocks")
            
            # Filter candidates by OI >= 7%
            qualified_stocks = []
            oi_threshold = getattr(config, 'OI_THRESHOLD_PERCENT', 7.0)
            
            self.logger.info(f"🎯 Filtering {len(candidates)} candidates by OI >= {oi_threshold}%:")
            self.logger.info("-" * 60)
            
            for symbol in candidates:
                # Find OI data for this symbol
                oi_row = oi_df[oi_df['Symbol'].str.upper() == symbol.upper()]
                
                if not oi_row.empty:
                    try:
                        # Try different possible column names for OI change
                        oi_change = None
                        possible_columns = ['OI_Change_Percent', 'OI Change %', 'OI Change', 'Change in OI %']
                        
                        for col in possible_columns:
                            if col in oi_df.columns:
                                oi_change = oi_row.iloc[0][col]
                                break
                        
                        if oi_change is not None and pd.notna(oi_change):
                            # Clean the value (remove % symbol if present)
                            oi_change_clean = str(oi_change).replace('%', '').replace(',', '')
                            oi_change_num = float(oi_change_clean)
                            
                            if oi_change_num >= oi_threshold:
                                qualified_stocks.append(symbol)
                                self.logger.info(f"   ✅ {symbol:8s}: OI +{oi_change_num:6.2f}%")
                            else:
                                self.logger.info(f"   ❌ {symbol:8s}: OI +{oi_change_num:6.2f}% (< {oi_threshold}%)")
                        else:
                            self.logger.info(f"   ⚠️  {symbol:8s}: Invalid OI data")
                    except (ValueError, TypeError) as e:
                        self.logger.info(f"   ⚠️  {symbol:8s}: Error parsing OI data - {e}")
                else:
                    self.logger.info(f"   ❌ {symbol:8s}: Not found in OI data")
            
            self.logger.info("-" * 60)
            self.logger.info(f"💎 {len(qualified_stocks)} stocks qualified with OI >= {oi_threshold}%")
            
            return qualified_stocks
            
        except Exception as e:
            self.logger.error(f"❌ Error in OI filtering: {e}")
            # Return original candidates if filtering fails
            return candidates
    
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
        Place a real trade using ICICI Direct API
        """
        try:
            # Initialize order manager if not done
            if not self.order_manager:
                self.order_manager = OrderManager()
                self.logger.info("✅ Order manager initialized")
            
            trade_params = self.calculate_trade_params(symbol, current_price)
            
            # Determine order type and price
            if trade_params['direction'] == 'LONG':
                action = "buy"
                # Use limit order slightly above current price for better fills
                order_price = current_price * 1.001  # 0.1% above market
            else:
                action = "sell"
                order_price = current_price * 0.999  # 0.1% below market
            
            # Place the order
            self.logger.info(f"📤 Placing {action.upper()} order: {trade_params['quantity']} shares of {symbol} at ₹{order_price:.2f}")
            
            order_response = self.order_manager.place_equity_order(
                symbol=symbol,
                action=action,
                quantity=trade_params['quantity'],
                price=order_price,
                order_type="limit"
            )
            
            if order_response.status == "placed" and order_response.order_id:
                # Create trade record with real order ID
                trade = Trade(
                    symbol=symbol,
                    entry_price=order_price,  # Use order price, not current price
                    entry_time=datetime.now(),
                    quantity=trade_params['quantity'],
                    direction=trade_params['direction'],
                    stop_loss=trade_params['stop_loss'],
                    target=trade_params['target'],
                    order_id=order_response.order_id
                )
                
                self.trades.append(trade)
                self.logger.info(f"✅ Order placed successfully!")
                self.logger.info(f"   Order ID: {order_response.order_id}")
                self.logger.info(f"   Symbol: {symbol}")
                self.logger.info(f"   Price: ₹{order_price:.2f}")
                self.logger.info(f"   Quantity: {trade_params['quantity']}")
                self.logger.info(f"   Stop Loss: ₹{trade.stop_loss:.2f}")
                self.logger.info(f"   Target: ₹{trade.target:.2f}")
                
                return trade
            else:
                self.logger.error(f"❌ Order placement failed: {order_response.message}")
                return None
            
        except Exception as e:
            self.logger.error(f"❌ Error placing trade for {symbol}: {e}")
            return None
    
    def close_trade(self, trade: Trade, exit_price: float, reason: str) -> bool:
        """
        Close a trade using ICICI Direct API
        """
        try:
            if not self.order_manager:
                self.logger.error("❌ Order manager not initialized")
                return False
            
            # Determine exit action (opposite of entry)
            exit_action = "sell" if trade.direction == "LONG" else "buy"
            
            # Place exit order
            self.logger.info(f"📤 Placing {exit_action.upper()} order to close position: {trade.quantity} shares of {trade.symbol} at ₹{exit_price:.2f}")
            
            exit_order_response = self.order_manager.place_equity_order(
                symbol=trade.symbol,
                action=exit_action,
                quantity=trade.quantity,
                price=exit_price,
                order_type="limit"
            )
            
            if exit_order_response.status == "placed" and exit_order_response.order_id:
                # Update trade record
                trade.exit_price = exit_price
                trade.exit_time = datetime.now()
                trade.exit_order_id = exit_order_response.order_id
                trade.status = 'CLOSED' if reason != 'STOP_LOSS' else 'STOPPED'
                
                # Calculate P&L
                if trade.direction == 'LONG':
                    trade.pnl = (exit_price - trade.entry_price) * trade.quantity
                else:
                    trade.pnl = (trade.entry_price - exit_price) * trade.quantity
                
                self.logger.info(f"✅ Exit order placed successfully!")
                self.logger.info(f"   Exit Order ID: {exit_order_response.order_id}")
                self.logger.info(f"   Symbol: {trade.symbol}")
                self.logger.info(f"   Exit Price: ₹{exit_price:.2f}")
                self.logger.info(f"   P&L: ₹{trade.pnl:.2f}")
                self.logger.info(f"   Reason: {reason}")
                
                return True
            else:
                self.logger.error(f"❌ Exit order placement failed: {exit_order_response.message}")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Error closing trade for {trade.symbol}: {e}")
            return False
    
    def monitor_positions(self):
        """Monitor open positions for stop loss/target hit and order status"""
        if not self.ws_manager:
            return
            
        current_prices = self.ws_manager.get_current_prices()
        
        for trade in self.trades:
            if trade.status != 'OPEN':
                continue
            
            # Check order status if we have an order ID
            if trade.order_id and self.order_manager:
                order_status = self.order_manager.get_order_status(trade.order_id)
                if order_status:
                    status = order_status.get('order_status', '').lower()
                    if status in ['rejected', 'cancelled']:
                        self.logger.warning(f"⚠️ Order {trade.order_id} for {trade.symbol} was {status}")
                        trade.status = 'CANCELLED'
                        continue
                    elif status == 'complete':
                        # Order filled - update entry price if different
                        filled_price = float(order_status.get('average_price', trade.entry_price))
                        if abs(filled_price - trade.entry_price) > 0.01:
                            self.logger.info(f"📊 Order filled at ₹{filled_price:.2f} (vs expected ₹{trade.entry_price:.2f})")
                            trade.entry_price = filled_price
                            # Recalculate stop loss and target based on actual fill price
                            trade.stop_loss = filled_price * (1 - self.stop_loss_pct / 100)
                            trade.target = filled_price * (1 + self.target_profit_pct / 100)
                
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
            
            # PHASE 1: Wait until 9:20 AM and find 2% movers
            while datetime.now().time() < self.strategy_time:
                self.logger.info(f"⏰ Waiting for 9:20 AM strategy time...")
                time.sleep(30)
            
            # Step 1: Find 2% movers at 9:20 AM
            movers_920 = self.get_2_percent_movers_at_920()
            
            if not movers_920:
                self.logger.warning("⚠️ No 2% movers found at 9:20 AM. Exiting.")
                return
            
            # PHASE 2: Wait until 9:25 AM for momentum check
            self.logger.info(f"⏰ Waiting until 9:25 AM for momentum verification...")
            while datetime.now().time() < self.momentum_time:
                time_left = datetime.combine(datetime.today(), self.momentum_time) - \
                           datetime.combine(datetime.today(), datetime.now().time())
                self.logger.info(f"⏰ {time_left} until momentum check...")
                time.sleep(30)
            
            # Step 2: Check momentum and filter by OI at 9:25 AM
            self.candidates = self.get_final_trading_candidates(movers_920)
            
            if not self.candidates:
                self.logger.warning("⚠️ No final trading candidates after momentum & OI filter.")
                return
            
            # Initialize persistent WebSocket connection for long-term monitoring
            from websocket_connection import WebSocketManager
            from live_data_stream import _websocket_codes
            
            self.logger.info("🔗 Establishing persistent WebSocket connection...")
            self.ws_manager = WebSocketManager()
            
            if not self.ws_manager.start_persistent_connection():
                self.logger.error("❌ Failed to establish WebSocket connection")
                return
            
            if _websocket_codes:
                self.ws_manager.subscribe_to_codes(_websocket_codes)
                time.sleep(5)  # Wait for subscription
                self.logger.info(f"✅ Subscribed to {len(_websocket_codes)} stock codes for monitoring")
            
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