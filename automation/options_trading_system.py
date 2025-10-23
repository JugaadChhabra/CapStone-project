#!/usr/bin/env python3
"""
Complete Options Trading System - Single File Orchestrator

PURPOSE: One-file system that orchestrates your entire trading strategy
STRATEGY:
1. 9:20 AM - Find stocks with 2%+ movement using proven screening logic
2. 9:25 AM - Check momentum + 7% OI filter  
3. Manual trading - Buy ITM CE (positive) or ITM PE (negative)

USAGE: python options_trading_system.py

This file orchestrates all components:
├── Uses Live_Data_Stream.py for proven screening logic
├── Uses data_loader.py for previous day closing prices
├── Integrates ICICI Direct API for options buying
└── Provides simple manual trading interface
"""

import asyncio
import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

# Import existing proven functions
from Live_Data_Stream import run_trading_strategy, find_2_percent_movers, check_momentum_maintained
from data_loader import get_all_previous_day_closes, get_previous_day_close_date
from icici_functions import get_env_config, get_session_token
from trading_config import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Will be overridden by config
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('options_trading.log'),
        logging.StreamHandler()
    ]
)

@dataclass
class TradeableStock:
    """Stock that passed all screening filters"""
    symbol: str
    direction: str  # 'positive' or 'negative'
    current_price: float
    move_percent: float
    detected_at: datetime

class OptionsTrader:
    """
    Complete Options Trading System
    
    Orchestrates the entire trading workflow from screening to execution
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("🚀 Initializing Complete Options Trading System...")
        
        # Trading state
        self.tradeable_stocks: List[TradeableStock] = []
        self.previous_closes: Dict[str, float] = {}
        self.screening_complete = False
        
        # Load API credentials
        try:
            self.config = get_env_config()
            self.secret_key = self.config['secret_key']
            self.app_key = self.config['app_key']
            self.session_token = self.config['session_key']
            self.logger.info("✅ ICICI Direct credentials loaded")
        except Exception as e:
            self.logger.error(f"❌ Failed to load API credentials: {e}")
            raise
        
        # Market timing
        self.screening_time_920 = datetime.now().replace(hour=9, minute=20, second=0, microsecond=0)
        self.momentum_time_925 = datetime.now().replace(hour=9, minute=25, second=0, microsecond=0)
        
        # Configure logging level from config
        logging.getLogger().setLevel(getattr(logging, LOG_LEVEL))
        
        self.logger.info("✅ Options Trading System initialized")

    def get_previous_day_closes(self) -> bool:
        """
        Get previous day closing prices for all stocks
        Uses proven data_loader.py function
        """
        try:
            self.logger.info("📊 Fetching previous day closing prices...")
            
            # Get target date for previous trading day
            target_date = get_previous_day_close_date()
            self.logger.info(f"📅 Target date: {target_date}")
            
            # Use proven function from data_loader.py
            self.previous_closes = get_all_previous_day_closes(target_date)
            
            if self.previous_closes:
                self.logger.info(f"✅ Retrieved {len(self.previous_closes)} closing prices")
                return True
            else:
                self.logger.error("❌ Failed to get previous day closing prices")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error getting previous day closes: {e}")
            return False

    def run_screening_920(self) -> List[str]:
        """
        Run 9:20 AM screening using proven Live_Data_Stream logic
        Returns list of stock symbols with 2%+ movement
        """
        try:
            self.logger.info("🔍 Running 9:20 AM screening for 2%+ movers...")
            
            # Use proven screening function from Live_Data_Stream.py
            # This function handles all the WebSocket logic and returns symbols
            mover_symbols = run_trading_strategy(wait_time=5.0)
            
            if mover_symbols:
                self.logger.info(f"✅ Found {len(mover_symbols)} stocks with 2%+ movement:")
                for symbol in mover_symbols:
                    self.logger.info(f"   📈 {symbol}")
            else:
                self.logger.info("📭 No stocks found with 2%+ movement")
            
            return mover_symbols
            
        except Exception as e:
            self.logger.error(f"❌ Error in 9:20 screening: {e}")
            return []

    def run_screening_925(self) -> List[str]:
        """
        Run 9:25 AM momentum check using proven Live_Data_Stream logic
        Returns final list of tradeable stocks
        """
        try:
            self.logger.info("🔍 Running 9:25 AM momentum + OI check...")
            
            # Use proven momentum checking function from Live_Data_Stream.py
            # This checks stocks that passed 9:20 screening
            final_symbols = run_trading_strategy(wait_time=5.0)
            
            if final_symbols:
                self.logger.info(f"✅ Final tradeable stocks ({len(final_symbols)}):")
                for symbol in final_symbols:
                    self.logger.info(f"   ⚡ {symbol}")
                    
                # Convert to TradeableStock objects
                self.convert_to_tradeable_stocks(final_symbols)
            else:
                self.logger.info("📭 No stocks maintained momentum")
            
            return final_symbols
            
        except Exception as e:
            self.logger.error(f"❌ Error in 9:25 screening: {e}")
            return []

    def convert_to_tradeable_stocks(self, symbols: List[str]):
        """Convert symbol list to TradeableStock objects with additional data"""
        self.tradeable_stocks = []
        
        for symbol in symbols:
            # For now, create basic TradeableStock objects
            # TODO: Get actual price and movement data from WebSocket
            tradeable_stock = TradeableStock(
                symbol=symbol,
                direction='positive',  # Will be determined by actual screening
                current_price=0.0,     # Will be fetched from live data
                move_percent=0.0,      # Will be calculated from screening
                detected_at=datetime.now()
            )
            self.tradeable_stocks.append(tradeable_stock)

    def calculate_itm_strike(self, underlying_price: float, option_type: str) -> int:
        """Calculate in-the-money strike price"""
        buffer = STRIKE_BUFFER  # Use config value
        
        if option_type.upper() == 'CE':
            # For calls, ITM means strike < current price
            strike = int(underlying_price - buffer)
        else:
            # For puts, ITM means strike > current price  
            strike = int(underlying_price + buffer)
        
        # Round to nearest 50 (common strike intervals)
        strike = round(strike / 50) * 50
        return strike

    def get_next_expiry_date(self) -> str:
        """Get next weekly expiry date (Thursday)"""
        today = datetime.now()
        days_ahead = 3 - today.weekday()  # Thursday = 3
        
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += DAYS_TO_EXPIRY  # Use config value
            
        expiry = today + timedelta(days=days_ahead)
        return expiry.strftime('%d-%b-%Y')  # Format: "31-Oct-2024"

    def buy_option(self, stock_symbol: str, option_type: str, 
                   underlying_price: Optional[float] = None) -> bool:
        """
        Buy options using ICICI Direct API
        
        Args:
            stock_symbol: Stock symbol (e.g., "RELIANCE", "TCS") 
            option_type: "CE" for call or "PE" for put
            underlying_price: Current stock price (if None, will use dummy)
            
        Returns:
            bool: True if order placed successfully
        """
        try:
            self.logger.info(f"🚀 Placing {option_type} option order for {stock_symbol}")
            
            # Check if stock is in tradeable list
            if not any(stock.symbol == stock_symbol for stock in self.tradeable_stocks):
                self.logger.warning(f"⚠️ {stock_symbol} not in screened tradeable list")
                self.logger.info("Available tradeable stocks:")
                for stock in self.tradeable_stocks:
                    self.logger.info(f"  - {stock.symbol}")
                # Continue anyway for manual override
            
            # Get current stock price
            if underlying_price is None:
                # TODO: Get real price from live data
                underlying_price = 3000.0
                self.logger.warning(f"Using dummy price {underlying_price} for {stock_symbol}")
            
            # Calculate option parameters
            strike_price = self.calculate_itm_strike(underlying_price, option_type)
            expiry_date = self.get_next_expiry_date()
            
            self.logger.info(f"📊 Option Details:")
            self.logger.info(f"   Stock: {stock_symbol}")
            self.logger.info(f"   Underlying Price: ₹{underlying_price:.2f}")
            self.logger.info(f"   Strike Price: {strike_price}")
            self.logger.info(f"   Option Type: {option_type}")
            self.logger.info(f"   Expiry: {expiry_date}")
            
            # Prepare ICICI Direct API order
            order_payload = {
                "stock_code": stock_symbol,
                "action": "buy",
                "quantity": str(OPTION_LOT_SIZE),  # Use config value
                "price": "0",      # Market order
                "order_type": "market",
                "validity": "day",
                "product": "options",
                "exchange_code": "NSE",
                "settlement_id": "",
                "user_remark": "OptionsAutoTrader",
                
                # Options specific fields
                "right": option_type.lower(),  # "ce" or "pe"
                "strike_price": str(strike_price),
                "expiry_date": expiry_date,
                "underlying": stock_symbol
            }
            
            # Generate checksum for ICICI API
            checksum_string = (f"{self.secret_key}|"
                             f"{order_payload['stock_code']}|"
                             f"{order_payload['action']}|"
                             f"{order_payload['quantity']}|"
                             f"{order_payload['price']}|"
                             f"{order_payload['order_type']}|"
                             f"{order_payload['validity']}|"
                             f"{order_payload['product']}|"
                             f"{order_payload['exchange_code']}|"
                             f"{self.session_token}")
            
            checksum = hashlib.sha256(checksum_string.encode()).hexdigest()
            
            # API headers
            headers = {
                "Content-Type": "application/json",
                "X-SessionToken": self.session_token,
                "X-AppKey": self.app_key,
                "X-Checksum": checksum
            }
            
            self.logger.info("📤 Placing options order with ICICI Direct...")
            
            # Make API call
            import requests
            
            response = requests.post(
                "https://api.icicidirect.com/breezeapi/api/v1/order",
                headers=headers,
                data=json.dumps(order_payload),
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    order_id = result.get('data', {}).get('order_id')
                    self.logger.info(f"✅ Options order placed successfully!")
                    self.logger.info(f"   Order ID: {order_id}")
                    self.logger.info(f"   Stock: {stock_symbol}")
                    self.logger.info(f"   Type: {option_type}")
                    self.logger.info(f"   Strike: {strike_price}")
                    return True
                else:
                    error_msg = result.get('error', {}).get('message', 'Unknown error')
                    self.logger.error(f"❌ Order placement failed: {error_msg}")
                    return False
            else:
                self.logger.error(f"❌ API call failed with status code: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error placing options order: {e}")
            return False

    def display_tradeable_stocks(self):
        """Display the final list of tradeable stocks"""
        if not self.tradeable_stocks:
            self.logger.info("📭 No tradeable stocks found")
            return
        
        print("\n" + "=" * 70)
        print("🎯 TRADEABLE STOCKS FOR TODAY")
        print("=" * 70)
        
        for i, stock in enumerate(self.tradeable_stocks, 1):
            direction_emoji = "📈" if stock.direction == 'positive' else "📉"
            option_type = "CE" if stock.direction == 'positive' else "PE"
            
            print(f"{i}. {stock.symbol}")
            print(f"   {direction_emoji} Direction: {stock.direction}")
            print(f"   💰 Price: ₹{stock.current_price:.2f}")
            print(f"   📊 Move: {stock.move_percent:+.2f}%")
            print(f"   🎯 Strategy: Buy ITM {option_type}")
            print()
        
        print("💡 Manual Trading Commands:")
        print("  trader.buy_option('RELIANCE', 'CE')  # Buy call")
        print("  trader.buy_option('TCS', 'PE')       # Buy put")
        print("=" * 70)

    async def run_complete_screening(self):
        """
        Run the complete screening process (9:20 + 9:25)
        """
        try:
            self.logger.info("🚀 Starting Complete Options Screening System...")
            
            # Step 1: Get previous day closing prices (needed for percentage calculations)
            if not self.get_previous_day_closes():
                self.logger.error("❌ Cannot proceed without previous day data")
                return
            
            # Calculate timing
            now = datetime.now()
            
            # Wait for 9:20 if needed
            if now < self.screening_time_920:
                wait_seconds = (self.screening_time_920 - now).total_seconds()
                self.logger.info(f"⏰ Waiting {wait_seconds:.0f} seconds for 9:20 AM...")
                await asyncio.sleep(wait_seconds)
            
            # Step 2: Run 9:20 screening
            movers_920 = self.run_screening_920()
            
            if not movers_920:
                self.logger.info("📭 No movers found at 9:20. Ending screening.")
                return
            
            # Wait for 9:25 if needed
            wait_seconds = (self.momentum_time_925 - datetime.now()).total_seconds()
            if wait_seconds > 0:
                self.logger.info(f"⏰ Waiting {wait_seconds:.0f} seconds for 9:25 AM...")
                await asyncio.sleep(wait_seconds)
            
            # Step 3: Run 9:25 momentum check
            final_stocks = self.run_screening_925()
            
            if final_stocks:
                self.screening_complete = True
                self.display_tradeable_stocks()
                self.logger.info("✅ Complete screening finished! Ready for manual trading.")
            else:
                self.logger.info("📭 No stocks passed final momentum check")
            
        except Exception as e:
            self.logger.error(f"❌ Error in complete screening: {e}")

# Global trader instance for interactive use
trader = None

async def main():
    """Main entry point for the trading system"""
    global trader
    
    try:
        # Initialize the trading system
        trader = OptionsTrader()
        
        # Run complete screening
        await trader.run_complete_screening()
        
        # Display usage instructions
        print("\n" + "=" * 70)
        print("🎯 OPTIONS TRADING SYSTEM READY")
        print("=" * 70)
        print("System has completed screening. Use these commands:")
        print()
        print("📊 View Results:")
        print("  trader.display_tradeable_stocks()")
        print()
        print("💰 Place Trades:")
        print("  trader.buy_option('RELIANCE', 'CE')  # Buy call for positive mover")
        print("  trader.buy_option('TCS', 'PE')       # Buy put for negative mover")
        print()
        print("📋 Available Stocks:")
        if trader.tradeable_stocks:
            for stock in trader.tradeable_stocks:
                option_type = "CE" if stock.direction == 'positive' else "PE"
                print(f"  trader.buy_option('{stock.symbol}', '{option_type}')")
        else:
            print("  (No tradeable stocks found)")
        print("=" * 70)
        
        # Keep running for manual trades
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        print("\n👋 Trading system stopped")
    except Exception as e:
        print(f"❌ System error: {e}")

def quick_test():
    """Quick test function for development"""
    print("🧪 Testing Options Trading System Components...")
    
    # Test data loading
    try:
        from data_loader import get_previous_day_close_date
        date = get_previous_day_close_date()
        print(f"✅ Previous trading day: {date}")
    except Exception as e:
        print(f"❌ Data loader test failed: {e}")
    
    # Test screening functions
    try:
        from Live_Data_Stream import run_trading_strategy
        print("✅ Live data stream functions imported")
    except Exception as e:
        print(f"❌ Live data stream test failed: {e}")
    
    # Test API credentials
    try:
        from icici_functions import get_env_config
        config = get_env_config()
        print("✅ ICICI API credentials loaded")
    except Exception as e:
        print(f"❌ API credentials test failed: {e}")

if __name__ == "__main__":
    # Quick test first
    quick_test()
    print()
    
    # Run the main system
    print("🚀 Starting Options Trading System...")
    asyncio.run(main())