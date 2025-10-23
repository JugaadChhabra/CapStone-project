#!/usr/bin/env python3
"""
Working ICICI Direct Price Fetcher
This version works with verified stock symbols and exchanges
"""

import requests
import json
import hashlib
import os
from datetime import datetime, timezone
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ICICIPriceFetcher:
    def __init__(self):
        """Initialize the ICICI price fetcher with credentials"""
        self.app_key = os.getenv('ICICI_APP_KEY')
        self.secret_key = os.getenv('ICICI_SECRET_KEY')
        self.session_key = os.getenv('ICICI_SESSION_KEY')
        self.session_token = None
        
        if not all([self.app_key, self.secret_key, self.session_key]):
            raise ValueError("Missing ICICI credentials in .env file")
    
    def get_session_token(self):
        """Get session token from ICICI API"""
        try:
            print("🔑 Getting session token...")
            
            url = "https://api.icicidirect.com/breezeapi/api/v1/customerdetails"
            
            payload = json.dumps({
                "SessionToken": self.session_key,
                "AppKey": self.app_key
            })
            
            headers = {
                'Content-Type': 'application/json',
            }
            
            response = requests.get(url, headers=headers, data=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("Success") and data["Success"].get("session_token"):
                    self.session_token = data["Success"]["session_token"]
                    print("✅ Session token obtained successfully")
                    return True
                else:
                    print(f"❌ Failed to get session token: {data}")
                    return False
            else:
                print(f"❌ Failed to get session token: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error getting session token: {e}")
            return False
    
    def get_stock_price(self, stock_code, exchange_code="NSE"):
        """
        Get current price for a stock
        
        Args:
            stock_code: Stock symbol (e.g., "NIFTY", "TCS")
            exchange_code: Exchange code (NSE, BSE, etc.)
            
        Returns:
            dict: Contains price data and success status
        """
        if not self.session_token:
            if not self.get_session_token():
                return {"success": False, "error": "Failed to get session token"}
        
        try:
            print(f"📊 Fetching price for {stock_code} on {exchange_code}...")
            
            # Generate timestamp
            time_stamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
            
            # Prepare API call
            url = "https://api.icicidirect.com/breezeapi/api/v1/quotes"
            
            payload = json.dumps({
                "stock_code": stock_code,
                "exchange_code": exchange_code,
            }, separators=(',', ':'))
            
            # Generate checksum
            checksum = hashlib.sha256((time_stamp + payload + self.secret_key).encode("utf-8")).hexdigest()
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
                'X-Checksum': 'token ' + checksum,
                'X-Timestamp': time_stamp,
                'X-AppKey': self.app_key,
                'X-SessionToken': self.session_token
            }
            
            # Make API call
            response = requests.get(url, headers=headers, data=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("Success") and data.get("Status") == 200:
                    stock_data = data["Success"]
                    
                    # Handle array response
                    if isinstance(stock_data, list) and len(stock_data) > 0:
                        stock_data = stock_data[0]
                    
                    result = {
                        "stock_code": stock_code,
                        "exchange": exchange_code,
                        "ltp": float(stock_data.get("ltp", 0)),
                        "change_percent": float(stock_data.get("change_percentage", 0)),
                        "high": float(stock_data.get("high", 0)),
                        "low": float(stock_data.get("low", 0)),
                        "open": float(stock_data.get("open", 0)),
                        "volume": int(stock_data.get("volume", 0)),
                        "timestamp": datetime.now().isoformat(),
                        "success": True
                    }
                    
                    print(f"✅ {stock_code}: ₹{result['ltp']} ({result['change_percent']:+.2f}%)")
                    return result
                else:
                    error_msg = data.get("Error", "No data found")
                    print(f"❌ API error for {stock_code}: {error_msg}")
                    return {"success": False, "error": error_msg, "stock_code": stock_code}
            else:
                print(f"❌ HTTP error {response.status_code} for {stock_code}")
                return {"success": False, "error": f"HTTP {response.status_code}", "stock_code": stock_code}
                
        except Exception as e:
            print(f"❌ Exception fetching {stock_code}: {e}")
            return {"success": False, "error": str(e), "stock_code": stock_code}

# Simple function for easy integration
def get_live_price(stock_symbol: str, exchange: str = "NSE") -> float:
    """
    Simple function to get current price for a stock
    
    Args:
        stock_symbol: Stock symbol (e.g., "NIFTY", "TCS")
        exchange: Exchange code (default: NSE)
        
    Returns:
        float: Current price of the stock, or 0 if failed
    """
    try:
        fetcher = ICICIPriceFetcher()
        result = fetcher.get_stock_price(stock_symbol, exchange)
        
        if result and result.get("success"):
            return float(result.get("ltp", 0))
        else:
            print(f"❌ Failed to get price for {stock_symbol}")
            return 0.0
            
    except Exception as e:
        print(f"❌ Error getting live price for {stock_symbol}: {e}")
        return 0.0

def main():
    """Test the price fetcher with working stock codes"""
    print("🚀 ICICI Direct Working Price Fetcher")
    print("=" * 50)
    
    try:
        fetcher = ICICIPriceFetcher()
        
        # Test with stocks that we know work
        working_stocks = [
            ("NIFTY", "NSE"),
            ("TCS", "NSE"),
            # Add more as we find working symbols
        ]
        
        results = []
        
        for stock, exchange in working_stocks:
            result = fetcher.get_stock_price(stock, exchange)
            results.append(result)
            time.sleep(0.5)  # Small delay between requests
        
        # Summary
        print(f"\n📈 Summary:")
        print("-" * 30)
        working_count = sum(1 for r in results if r.get("success"))
        print(f"✅ Working: {working_count}/{len(results)} stocks")
        
        for result in results:
            if result.get("success"):
                print(f"  {result['stock_code']}: ₹{result['ltp']}")
        
        # Test the simple function
        print(f"\n🧪 Testing simple function:")
        price = get_live_price("NIFTY")
        print(f"get_live_price('NIFTY') = ₹{price}")
        
    except Exception as e:
        print(f"❌ Main function failed: {e}")

if __name__ == "__main__":
    main()