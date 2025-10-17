import base64 
import socketio
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
from time import time, sleep
import pandas as pd
import threading
from typing import Dict, List, Optional

class ICICIStockPriceClient:
    def __init__(self, api_session_token=None, app_key=None):
        # Load credentials from environment if not provided
        if not api_session_token or not app_key:
            load_dotenv()
            api_session_token = os.getenv("API_SESSION_TOKEN")
            app_key = os.getenv("APP_KEY")
        
        if not api_session_token or not app_key:
            raise ValueError("API credentials not found. Set API_SESSION_TOKEN and APP_KEY in .env file or pass them as parameters.")
        
        self.api_session_token = api_session_token
        self.app_key = app_key
        self.session_token = None
        self.user_id = None
        self.sio = socketio.Client()
        
        # Data storage
        self.current_prices = {}  # Store latest prices
        self.stock_codes = self.load_stock_codes_from_csv()
        self.code_to_stock = {v: k for k, v in self.stock_codes.items()}
        self.is_connected = False
        self.connection_lock = threading.Lock()
        
        self.setup_events()
    
    def load_stock_codes_from_csv(self, csv_file_path="stock_names_symbol.csv"):
        """
        Load stock codes from CSV file and convert to WebSocket format
        
        Args:
            csv_file_path: Path to the CSV file containing stock data
        
        Returns:
            Dictionary mapping stock names to WebSocket codes
        """
        try:
            # Read the CSV file (assuming 3 columns: name, symbol, token)
            df = pd.read_csv(csv_file_path, header=None, names=['company_name', 'symbol', 'token'])
            
            stock_codes = {}
            special_cases = 0
            
            for _, row in df.iterrows():
                company_name = str(row['company_name']).strip()
                symbol = str(row['symbol']).strip()
                token = str(row['token']).strip()
                
                # Skip rows with missing data
                if not company_name or not symbol or not token or token == 'nan':
                    continue
                
                # Create a clean stock name for mapping
                # Extract key words from company name for shorter display
                name_parts = company_name.replace(' Limited', '').replace(' Ltd', '').replace(' LIMITED', '').split()
                stock_name = ' '.join(name_parts[:2] if len(name_parts) > 3 else name_parts)
                
                # Handle special cases like NIFTY (indices don't follow 4.1! format)
                if symbol.upper() in ['NIFTY', 'SENSEX', 'BANKNIFTY']:
                    websocket_code = symbol.upper()
                    special_cases += 1
                else:
                    # Standard format: 4.1!{token} for NSE equity
                    websocket_code = f"4.1!{token}"
                
                stock_codes[stock_name] = websocket_code
            
            print(f"   📈 Converted {len(stock_codes)} stocks to WebSocket format")
            if special_cases > 0:
                print(f"   🔍 Found {special_cases} special cases (indices)")
            
            return stock_codes
            
        except (FileNotFoundError, Exception) as e:
            error_msg = f"CSV file not found: {csv_file_path}" if isinstance(e, FileNotFoundError) else f"Error loading CSV: {e}"
            print(f"❌ {error_msg}")
            print("   Using fallback stock codes...")
            return {"NIFTY": "NIFTY", "NCC": "4.1!2319", "VOLTAS": "4.1!3718"}
    
    def get_websocket_session_token(self):
        """Get the session token from customer details API"""
        try:
            print("Fetching WebSocket session token...")
            
            url = "https://api.icicidirect.com/breezeapi/api/v1/customerdetails"
            payload = json.dumps({
                "SessionToken": self.api_session_token,
                "AppKey": self.app_key
            })
            headers = {
                'Content-Type': 'application/json',
            }
            
            response = requests.request("GET", url, headers=headers, data=payload)
            data = json.loads(response.text)
            
            if data.get("Success") and "session_token" in data["Success"]:
                websocket_session_key = data["Success"]["session_token"]
                print(f"Got WebSocket session key: {websocket_session_key}")
                
                # Decode the session key
                decoded = base64.b64decode(websocket_session_key.encode('ascii')).decode('ascii')
                self.user_id, self.session_token = decoded.split(":")
                print(f"User ID: {self.user_id}")
                print(f"Session Token: {self.session_token}")
                return True
            else:
                print(f"Failed to get session token: {data}")
                return False
                
        except Exception as e:
            print(f"Error getting session token: {e}")
            return False
    
    def setup_events(self):
        """Setup WebSocket event handlers"""
        
        @self.sio.event
        def connect():
            print("WebSocket connected successfully!")
        
        @self.sio.event
        def disconnect():
            print("WebSocket disconnected")
        
        @self.sio.event
        def connect_error(data):
            print(f"Connection error: {data}")
        
        @self.sio.on('stock')
        def on_stock_data(data):
            """Handle incoming stock data and store latest prices"""
            try:
                parsed_data = self.parse_data(data)
                symbol = parsed_data.get('symbol', 'Unknown')
                
                # Store the latest price data
                if symbol and 'last' in parsed_data:
                    with self.connection_lock:
                        self.current_prices[symbol] = {
                            'price': float(parsed_data.get('last', 0)),
                            'change': float(parsed_data.get('change', 0)),
                            'high': float(parsed_data.get('high', 0)),
                            'low': float(parsed_data.get('low', 0)),
                            'open': float(parsed_data.get('open', 0)),
                            'volume': parsed_data.get('ltq', 0),
                            'timestamp': datetime.now(),
                            'symbol': symbol
                        }
                
            except Exception as e:
                print(f"Error processing stock data: {e}")
    
    def get_stock_name(self, symbol_or_code):
        """Get readable stock name from symbol or code"""
        return self.code_to_stock.get(symbol_or_code, symbol_or_code)
    
    def parse_data(self, data):
        """Enhanced data parser for indices"""
        if not data or not isinstance(data, list) or len(data) < 12:
            return {"raw_data": data} if data else {}
        
        try:
            return {
                "symbol": data[0],
                "open": data[1],
                "last": data[2],
                "high": data[3],
                "low": data[4],
                "change": data[5],
                "bPrice": data[6],
                "bQty": data[7],
                "sPrice": data[8],
                "sQty": data[9],
                "ltq": data[10],
                "avgPrice": data[11],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Parse error: {e}")
            return {"raw_data": data}
    
    def _connect_websocket(self):
        """Internal method to establish WebSocket connection"""
        if self.is_connected:
            return True
            
        try:
            if not self.get_websocket_session_token():
                return False
            
            auth = {"user": self.user_id, "token": self.session_token}
            self.sio.connect(
                "https://livestream.icicidirect.com", 
                headers={"User-Agent": "python-socketio[client]/socket"}, 
                auth=auth, 
                transports="websocket", 
                wait_timeout=10
            )
            
            self.is_connected = self.sio.connected
            return self.is_connected
            
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            return False
    
    def _subscribe_to_stocks(self, stock_symbols: List[str]):
        """Subscribe to stock updates"""
        stock_codes = []
        for symbol in stock_symbols:
            if symbol in self.stock_codes:
                stock_codes.append(self.stock_codes[symbol])
            else:
                # Try to find partial match
                for name, code in self.stock_codes.items():
                    if symbol.upper() in name.upper():
                        stock_codes.append(code)
                        break
        
        for stock_code in stock_codes:
            self.sio.emit('join', stock_code)
        
        return stock_codes
    
    def get_current_prices(self, stock_symbols: List[str], wait_time: float = 5.0) -> Dict[str, Dict]:
        """
        Get current prices for specified stocks
        
        Args:
            stock_symbols: List of stock names to get prices for
            wait_time: Time to wait for data collection (seconds)
        
        Returns:
            Dictionary with stock names as keys and price data as values
        """
        try:
            # Connect if not already connected
            if not self._connect_websocket():
                raise Exception("Failed to connect to WebSocket")
            
            # Subscribe to requested stocks
            subscribed_codes = self._subscribe_to_stocks(stock_symbols)
            
            if not subscribed_codes:
                return {}
            
            # Wait for data to arrive
            sleep(wait_time)
            
            # Collect results
            results = {}
            with self.connection_lock:
                for symbol in stock_symbols:
                    # Find matching data
                    for stored_symbol, price_data in self.current_prices.items():
                        stock_name = self.get_stock_name(stored_symbol)
                        if (symbol.upper() == stock_name.upper() or 
                            symbol.upper() in stock_name.upper()):
                            results[symbol] = price_data.copy()
                            break
            
            return results
            
        except Exception as e:
            print(f"Error getting prices: {e}")
            return {}
    
    def disconnect(self):
        """Disconnect from WebSocket"""
        try:
            if self.sio.connected:
                self.sio.disconnect()
            self.is_connected = False
        except:
            pass
    
    def get_selected_stocks(self, stock_list=None, max_stocks=200):
        """Get selected stock codes (kept for backward compatibility)"""
        if stock_list is None:
            all_codes = list(self.stock_codes.values())
            return all_codes[:max_stocks]
        
        selected_codes = []
        for stock_name in stock_list:
            if stock_name in self.stock_codes:
                selected_codes.append(self.stock_codes[stock_name])
            else:
                for name, code in self.stock_codes.items():
                    if stock_name.upper() in name.upper():
                        selected_codes.append(code)
                        break
        return selected_codes
    
    def get_available_stocks(self) -> List[str]:
        """Get list of all available stock names"""
        return list(self.stock_codes.keys())


# Global client instance
_client = None

def get_stock_prices(stock_names: List[str], wait_time: float = 5.0) -> Dict[str, Dict]:
    """
    Simple function to get current stock prices
    
    Args:
        stock_names: List of stock names (e.g., ['Reliance', 'TCS', 'HDFC Bank'])
        wait_time: Time to wait for data collection (default: 5 seconds)
    
    Returns:
        Dict with stock names as keys and price info as values
        Example: {
            'Reliance': {
                'price': 2431.50,
                'change': 12.30,
                'high': 2445.00,
                'low': 2420.00,
                'open': 2425.00,
                'volume': 1500,
                'timestamp': datetime(2025, 10, 17, 10, 30, 45)
            }
        }
    """
    global _client
    
    try:
        # Initialize client if needed
        if _client is None:
            _client = ICICIStockPriceClient()
        
        # Get prices
        return _client.get_current_prices(stock_names, wait_time)
        
    except Exception as e:
        print(f"Error fetching stock prices: {e}")
        return {}

def get_available_stocks() -> List[str]:
    """
    Get list of all available stock names
    
    Returns:
        List of stock names that can be used with get_stock_prices()
    """
    global _client
    
    try:
        if _client is None:
            _client = ICICIStockPriceClient()
        
        return _client.get_available_stocks()
        
    except Exception as e:
        print(f"Error getting stock list: {e}")
        return []

def cleanup():
    """Clean up connections"""
    global _client
    if _client:
        _client.disconnect()
        _client = None

# Usage
if __name__ == "__main__":
    load_dotenv()
    API_SESSION_TOKEN = os.getenv("API_SESSION_TOKEN")
    APP_KEY = os.getenv("APP_KEY")

    if not API_SESSION_TOKEN or not APP_KEY:
        print("❌ Please set API_SESSION_TOKEN and APP_KEY in your .env file")
        exit(1)

# Example usage
if __name__ == "__main__":
    # Example 1: Get prices for specific stocks
    stocks = ['Reliance', 'TCS', 'HDFC Bank', 'Infosys']
    prices = get_stock_prices(stocks, wait_time=3.0)
    
    print("📊 Current Stock Prices:")
    print("=" * 50)
    
    for stock, data in prices.items():
        if data:
            change_symbol = "📈" if data['change'] >= 0 else "📉"
            print(f"{change_symbol} {stock:<20} | ₹{data['price']:>8,.2f} | Change: {data['change']:>+7.2f}")
        else:
            print(f"❌ {stock:<20} | No data available")
    
    print("=" * 50)
    
    # Example 2: Show available stocks
    print(f"\n📋 First 10 available stocks:")
    available = get_available_stocks()
    for i, stock in enumerate(available[:10]):
        print(f"   {i+1:2d}. {stock}")
    
    if len(available) > 10:
        print(f"   ... and {len(available) - 10} more stocks available")
    
    # Cleanup
    cleanup()
