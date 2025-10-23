#!/usr/bin/env python3
"""
Simple Options Buy Function - ICICI Direct Integration

PURPOSE: Clean, simple function to buy options with ICICI Direct API
USAGE:
    from simple_options_trader import OptionsBuyer
    buyer = OptionsBuyer()
    
    # Buy call option
    success = buyer.buy_option("RELIANCE", "CE")
    
    # Buy put option  
    success = buyer.buy_option("TCS", "PE")
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Literal
from icici_functions import get_env_config, get_session_token

# Configure logging
logging.basicConfig(level=logging.INFO)

class OptionsBuyer:
    """
    Simple options buyer with ICICI Direct API integration
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
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

    def calculate_itm_strike(self, underlying_price: float, option_type: str) -> int:
        """Calculate in-the-money strike price"""
        buffer = 100  # Strike buffer from current price
        
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
            days_ahead += 7
            
        expiry = today + timedelta(days=days_ahead)
        return expiry.strftime('%d-%b-%Y')  # Format: "31-Oct-2024"

    def buy_option(self, stock_symbol: str, option_type: str, 
                   underlying_price: Optional[float] = None) -> bool:
        """
        Buy options using ICICI Direct API
        
        Args:
            stock_symbol: Stock symbol (e.g., "RELIANCE", "TCS") 
            option_type: "CE" for call or "PE" for put
            underlying_price: Current stock price (if None, will fetch)
            
        Returns:
            bool: True if order placed successfully
        """
        try:
            self.logger.info(f"🚀 Buying {option_type} option for {stock_symbol}")
            
            # Get current stock price if not provided
            if underlying_price is None:
                # TODO: Add price fetching logic here
                # For now, using dummy price - replace with real API call
                underlying_price = 3000.0
                self.logger.warning(f"Using dummy price {underlying_price} for {stock_symbol}")
            
            # Calculate ITM strike price
            strike_price = self.calculate_itm_strike(underlying_price, option_type)
            expiry_date = self.get_next_expiry_date()
            
            self.logger.info(f"📊 Option Details:")
            self.logger.info(f"   Underlying: {stock_symbol}")
            self.logger.info(f"   Current Price: ₹{underlying_price:.2f}")
            self.logger.info(f"   Strike Price: {strike_price}")
            self.logger.info(f"   Option Type: {option_type}")
            self.logger.info(f"   Expiry: {expiry_date}")
            
            # Prepare ICICI Direct API call
            order_payload = {
                "stock_code": stock_symbol,
                "action": "buy",
                "quantity": "25",  # NIFTY lot size
                "price": "0",  # Market order
                "order_type": "market",
                "validity": "day",
                "product": "options",
                "exchange_code": "NSE",
                "settlement_id": "",
                "user_remark": "AutoOptionsTrader",
                
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
            
            # Add authentication headers
            headers = {
                "Content-Type": "application/json",
                "X-SessionToken": self.session_token,
                "X-AppKey": self.app_key,
                "X-Checksum": checksum
            }
            
            self.logger.info("📤 Placing options order with ICICI Direct...")
            
            # Make the API call
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
                    self.logger.info(f"   Symbol: {stock_symbol}")
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

# Quick test function
def test_options_buying():
    """Test the options buying functionality"""
    try:
        buyer = OptionsBuyer()
        
        print("🧪 Testing Options Buying System")
        print("=" * 50)
        
        # Test buying call option
        print("Testing Call Option...")
        success_ce = buyer.buy_option("RELIANCE", "CE", 3000.0)
        print(f"Call option result: {'✅ Success' if success_ce else '❌ Failed'}")
        
        print()
        
        # Test buying put option
        print("Testing Put Option...")
        success_pe = buyer.buy_option("TCS", "PE", 4200.0)
        print(f"Put option result: {'✅ Success' if success_pe else '❌ Failed'}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_options_buying()