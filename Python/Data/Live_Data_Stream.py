import base64 
import socketio
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
from time import time

class ICICISimpleWebSocket:
    def __init__(self, api_session_token, app_key):
        self.api_session_token = api_session_token
        self.app_key = app_key
        self.session_token = None
        self.user_id = None
        self.sio = socketio.Client()
        
        # Time-based throttling for logging
        self.last_log_time = {}  # Track last log time per symbol
        self.log_interval = 3    # Log every 3 seconds maximum per symbol
        self.total_updates = 0   # Track total updates received
        self.logged_updates = 0  # Track how many we actually logged
        
        # Major Indian Stock Symbols (NSE)
        self.stock_codes = {
            "NCC": "4.1!2319",              # NCC Limited
            "VOLTAS": "4.1!3718",           # Voltas Ltd
            "PTC": "4.1!11355",             # PTC India Limited
            "IOC": "4.1!1624",              # Indian Oil Corporation
            "IDEA": "4.1!14366",            # Vodafone Idea Limited
            "AARTIIND": "4.1!7"             # Aarti Industries Ltd
        }
        
        # Reverse mapping for display
        self.code_to_stock = {v: k for k, v in self.stock_codes.items()}
        
        self.setup_events()
    
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
            """Handle incoming index data with time-based throttling"""
            try:
                self.total_updates += 1
                parsed_data = self.parse_data(data)
                symbol = parsed_data.get('symbol', 'Unknown')
                stock_name = self.get_stock_name(symbol)
                
                current_time = time()
                last_time = self.last_log_time.get(symbol, 0)
                
                # Check if enough time has passed since last log for this symbol
                if current_time - last_time >= self.log_interval:
                    self.last_log_time[symbol] = current_time
                    self.logged_updates += 1
                    
                    # Calculate percentage change
                    last_price = float(parsed_data.get('last', 0))
                    change = float(parsed_data.get('change', 0))
                    
                    if last_price > 0:
                        percentage_change = (change / (last_price - change)) * 100
                    else:
                        percentage_change = 0
                    
                    # Determine color indicator
                    trend = "📈" if change >= 0 else "📉"
                    change_str = f"+{change:.2f}" if change >= 0 else f"{change:.2f}"
                    perc_str = f"+{percentage_change:.2f}%" if percentage_change >= 0 else f"{percentage_change:.2f}%"
                    
                    print(f"\n{trend} {stock_name}")
                    print(f"   Price: ₹{last_price:,.2f}")
                    print(f"   Change: {change_str} ({perc_str})")
                    print(f"   High: ₹{parsed_data.get('high', 'N/A')}")
                    print(f"   Low: ₹{parsed_data.get('low', 'N/A')}")
                    print(f"   Volume: {parsed_data.get('ltq', 'N/A')}")
                    print(f"   Timestamp: {datetime.now().strftime('%H:%M:%S')}")
                    print(f"   Updates: {self.logged_updates}/{self.total_updates} logged")
                    print("=" * 50)
                else:
                    # Show brief update for throttled messages
                    time_left = self.log_interval - (current_time - last_time)
                    print(f"⏱️  {stock_name}: ₹{parsed_data.get('last', 'N/A')} (throttled, {time_left:.1f}s left)")
                
            except Exception as e:
                print(f"Error parsing data: {e}")
                print(f"Raw data: {data}")
    
    def get_stock_name(self, symbol_or_code):
        """Get readable stock name from symbol or code"""
        # Check if it's in our reverse mapping
        for code, name in self.code_to_stock.items():
            if code in [symbol_or_code] or symbol_or_code in code:
                return name
        return symbol_or_code
    
    def parse_data(self, data):
        """Enhanced data parser for indices"""
        if not data or not isinstance(data, list) or len(data) == 0:
            return {}
        
        try:
            if len(data) >= 12:
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
            else:
                return {"raw_data": data}
        except Exception as e:
            print(f"Parse error: {e}")
            return {"raw_data": data}
    
    def connect_and_stream(self, stock_codes, duration=30):
        """Connect to WebSocket and start streaming"""
        try:
            if not self.get_websocket_session_token():
                print("Failed to get session token")
                return False
            
            print("Connecting to WebSocket...")
            auth = {"user": self.user_id, "token": self.session_token}
            
            self.sio.connect(
                "https://livestream.icicidirect.com", 
                headers={"User-Agent": "python-socketio[client]/socket"}, 
                auth=auth, 
                transports="websocket", 
                wait_timeout=10
            )
            
            if not self.sio.connected:
                print("Failed to connect to WebSocket")
                return False
            
            for stock_code in stock_codes:
                print(f"Subscribing to {stock_code}")
                self.sio.emit('join', stock_code)
            
            print(f"Streaming for {duration} seconds...")
            self.sio.sleep(duration)
            
            return True
            
        except KeyboardInterrupt:
            print("\nStopping stream...")
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            try:
                for stock_code in stock_codes:
                    self.sio.emit("leave", stock_code)
                self.sio.emit("disconnect", "transport close")
                self.sio.disconnect()
                print("Disconnected successfully")
            except:
                pass
    
    def get_all_stocks(self):
        """Get list of all stock codes"""
        return list(self.stock_codes.values())
    
    def get_selected_stocks(self, stock_list=None):
        """Get selected stock codes"""
        if stock_list is None:
            # Default stocks to track
            stock_list = ["NCC", "VOLTAS", "PTC", "IOC"]
        
        return [self.stock_codes[stock] for stock in stock_list if stock in self.stock_codes]
    
    def get_throttling_stats(self):
        """Get throttling statistics"""
        if self.total_updates > 0:
            efficiency = (self.logged_updates / self.total_updates) * 100
            return {
                "total_updates": self.total_updates,
                "logged_updates": self.logged_updates,
                "throttled_updates": self.total_updates - self.logged_updates,
                "efficiency_percent": efficiency,
                "log_interval_seconds": self.log_interval
            }
        return None

# Usage
if __name__ == "__main__":
    load_dotenv()
    API_SESSION_TOKEN = os.getenv("API_SESSION_TOKEN")
    APP_KEY = os.getenv("APP_KEY")

    if not API_SESSION_TOKEN or not APP_KEY:
        print("❌ Please set API_SESSION_TOKEN and APP_KEY in your .env file")
        exit(1)

    client = ICICISimpleWebSocket(API_SESSION_TOKEN, APP_KEY)
    
    print("📊 Available Stocks:")
    for name, code in client.stock_codes.items():
        print(f"   {name}: {code}")
    
    # Get selected stocks to stream
    stock_codes = client.get_selected_stocks(["NCC", "VOLTAS", "PTC", "IOC", "IDEA", "AARTIIND"])
    
    print(f"\n� Starting live stream for {len(stock_codes)} stocks...")
    print(f"⏱️  Throttling: Max 1 log per {client.log_interval} seconds per stock")
    print("Press Ctrl+C to stop\n")
    
    try:
        client.connect_and_stream(stock_codes, duration=300)  # Stream for 5 minutes
    except KeyboardInterrupt:
        print("\n🛑 Stream stopped by user")
    finally:
        # Show final statistics
        stats = client.get_throttling_stats()
        if stats:
            print("\n📈 Final Statistics:")
            print(f"   Total Updates Received: {stats['total_updates']}")
            print(f"   Updates Logged: {stats['logged_updates']}")
            print(f"   Updates Throttled: {stats['throttled_updates']}")
            print(f"   Logging Efficiency: {stats['efficiency_percent']:.1f}%")
            print(f"   Throttle Interval: {stats['log_interval_seconds']} seconds\n")
