import base64 
import socketio
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
from time import sleep
import pandas as pd
import threading
from typing import Dict, List

# Global variables for connection state
_sio = None
_session_token = None
_user_id = None
_stock_data = []
_websocket_codes = []
_current_prices = {}
_connection_lock = threading.Lock()
_is_connected = False

# Global storage for 9:20 and 9:25 data
_movers_920 = []  # Stock symbols with 2%+ movement at 9:20
_final_stocks_925 = []  # Stock symbols that maintained momentum at 9:25

def load_stock_data(csv_file_path="stock_names_symbol.csv"):
    """Load stock data from CSV file"""
    try:
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, csv_file_path)
        
        df = pd.read_csv(csv_path, header=None, names=['company_name', 'symbol', 'token'])
        
        stock_data = []
        websocket_codes = []
        
        for _, row in df.iterrows():
            company_name = str(row['company_name']).strip()
            symbol = str(row['symbol']).strip()
            token = str(row['token']).strip()
            
            if not company_name or not symbol or not token or token == 'nan':
                continue
            
            # Create WebSocket code
            if symbol.upper() in ['NIFTY', 'SENSEX', 'BANKNIFTY']:
                websocket_code = symbol.upper()
            else:
                websocket_code = f"4.1!{token}"
            
            stock_data.append({
                'symbol': symbol,
                'token': token,
                'websocket_code': websocket_code
            })
            websocket_codes.append(websocket_code)
        
        return stock_data, websocket_codes
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return [], []

def get_websocket_session():
    """Get WebSocket session credentials"""
    global _session_token, _user_id
    
    load_dotenv()
    api_session_token = os.getenv("API_SESSION_TOKEN")
    app_key = os.getenv("APP_KEY")
    
    if not api_session_token or not app_key:
        raise ValueError("Set API_SESSION_TOKEN and APP_KEY in .env file")
    
    try:
        url = "https://api.icicidirect.com/breezeapi/api/v1/customerdetails"
        payload = json.dumps({
            "SessionToken": api_session_token,
            "AppKey": app_key
        })
        headers = {'Content-Type': 'application/json'}
        
        response = requests.get(url, headers=headers, data=payload)
        data = response.json()
        
        if data.get("Success") and "session_token" in data["Success"]:
            websocket_session_key = data["Success"]["session_token"]
            decoded = base64.b64decode(websocket_session_key.encode('ascii')).decode('ascii')
            _user_id, _session_token = decoded.split(":")
            return True
        else:
            print(f"Failed to get session token: {data}")
            return False
            
    except Exception as e:
        print(f"Error getting session token: {e}")
        return False

def parse_stock_data(data):
    """Parse incoming stock data"""
    if not data or not isinstance(data, list) or len(data) < 12:
        return None
    
    try:
        return {
            "symbol": data[0],
            "open": float(data[1]),
            "price": float(data[2]),
            "high": float(data[3]),
            "low": float(data[4]),
            "change": float(data[5]),
            "volume": data[10],
            "timestamp": datetime.now()
        }
    except:
        return None

def setup_websocket():
    """Setup WebSocket connection and event handlers"""
    global _sio, _current_prices, _connection_lock
    
    _sio = socketio.Client()
    
    @_sio.event
    def connect():
        print("WebSocket connected!")
    
    @_sio.event
    def disconnect():
        print("WebSocket disconnected")
    
    @_sio.on('stock')
    def on_stock_data(data):
        parsed = parse_stock_data(data)
        if parsed and parsed['symbol']:
            with _connection_lock:
                _current_prices[parsed['symbol']] = parsed

def connect_websocket():
    """Connect to WebSocket"""
    global _sio, _is_connected, _session_token, _user_id
    
    if _is_connected:
        return True
    
    if not get_websocket_session():
        return False
    
    setup_websocket()
    
    try:
        auth = {"user": _user_id, "token": _session_token}
        _sio.connect(
            "https://livestream.icicidirect.com",
            headers={"User-Agent": "python-socketio[client]/socket"},
            auth=auth,
            transports="websocket",
            wait_timeout=10
        )
        _is_connected = _sio.connected
        return _is_connected
    except Exception as e:
        print(f"Connection error: {e}")
        return False

def subscribe_to_websocket_codes(websocket_codes: List[str]):
    """Subscribe to WebSocket codes directly"""
    global _sio
    
    for code in websocket_codes:
        _sio.emit('join', code)
    
    print(f"🔗 Subscribed to {len(websocket_codes)} stocks")
    return websocket_codes

def get_websocket_codes_for_tokens(tokens: List[str]):
    """Get WebSocket codes for specific tokens"""
    global _stock_data
    
    codes = []
    for token in tokens:
        for stock in _stock_data:
            if stock['token'] == token:
                codes.append(stock['websocket_code'])
                break
    
    return codes

def find_2_percent_movers():
    """Find stocks with 2%+ movement at 9:20"""
    global _current_prices, _connection_lock, _stock_data, _movers_920
    
    movers = []
    with _connection_lock:
        for websocket_code, price_data in _current_prices.items():
            # Find the corresponding stock symbol
            for stock in _stock_data:
                if stock['websocket_code'] == websocket_code:
                    percentage_change = calculate_percentage_change(price_data['price'], price_data['change'])
                    
                    if abs(percentage_change) >= 2.0:
                        movers.append({
                            'symbol': stock['symbol'],
                            'token': stock['token'],
                            'websocket_code': websocket_code,
                            'price_920': price_data['price'],
                            'change_920': price_data['change'],
                            'percentage_920': percentage_change
                        })
                    break
    
    _movers_920 = movers
    print(f"🔍 Found {len(movers)} stocks with 2%+ movement at 9:20:")
    for mover in movers:
        direction = "📈" if mover['change_920'] >= 0 else "📉"
        print(f"   {direction} {mover['symbol']}: {mover['percentage_920']:+.2f}%")
    
    return [mover['symbol'] for mover in movers]

def check_momentum_maintained():
    """Check which stocks maintained momentum from 9:20 to 9:25"""
    global _current_prices, _connection_lock, _movers_920, _final_stocks_925
    
    maintained = []
    with _connection_lock:
        for mover in _movers_920:
            websocket_code = mover['websocket_code']
            
            if websocket_code in _current_prices:
                current_data = _current_prices[websocket_code]
                current_percentage = calculate_percentage_change(current_data['price'], current_data['change'])
                original_percentage = mover['percentage_920']
                
                # Check if momentum is maintained (not retraced more than 50%)
                if original_percentage > 0:  # Was positive at 9:20
                    if current_percentage >= (original_percentage * 0.5):
                        maintained.append(mover['symbol'])
                else:  # Was negative at 9:20
                    if current_percentage <= (original_percentage * 0.5):
                        maintained.append(mover['symbol'])
    
    _final_stocks_925 = maintained
    print(f"⚡ {len(maintained)} stocks maintained momentum from 9:20 to 9:25:")
    for symbol in maintained:
        print(f"   📊 {symbol}")
    
    return maintained

def calculate_percentage_change(current_price, change):
    """Calculate percentage change"""
    if current_price > 0 and change != 0:
        return (change / (current_price - change)) * 100
    return 0

def run_trading_strategy(wait_time: float = 5.0) -> List[str]:
    """
    Main trading strategy function
    
    Returns:
        List of stock symbols that passed both 9:20 and 9:25 filters
    
    Process:
        - 9:20 AM: Get ALL 200 stocks, find 2%+ movers, save their symbols
        - 9:25 AM: Get only the 9:20 movers, find ones that maintained 50%+ momentum
        - Returns: Final list of stock symbols for trading
    """
    global _stock_data, _websocket_codes, _current_prices
    
    try:
        # Step 1: Load stock data if needed
        if not _stock_data:
            _stock_data, _websocket_codes = load_stock_data()
            print(f"📊 Loaded {len(_stock_data)} stocks from CSV")
        
        # Step 2: Check current time and determine action
        current_time = datetime.now().time()
        hour, minute = current_time.hour, current_time.minute
        
        # Step 3: Connect to WebSocket
        if not connect_websocket():
            raise Exception("Failed to connect to WebSocket")
        
        # 9:20 AM - Get all stocks and find 2%+ movers
        if hour == 9 and 18 <= minute <= 22:
            print("🎯 Strategy: 9:20 AM - Find 2% Movers")
            print(f"📋 Fetching ALL {len(_websocket_codes)} stocks")
            
            # Subscribe to all stocks
            subscribe_to_websocket_codes(_websocket_codes)
            
            # Wait for data
            print(f"⏳ Waiting {wait_time} seconds for data...")
            sleep(wait_time)
            
            # Find 2% movers and save their symbols
            movers_symbols = find_2_percent_movers()
            print(f"� Saved {len(movers_symbols)} stocks with 2%+ movement")
            return movers_symbols
        
        # 9:25 AM - Check momentum for 9:20 movers
        elif hour == 9 and 23 <= minute <= 27:
            print("🎯 Strategy: 9:25 AM - Check Momentum")
            
            if not _movers_920:
                print("⚠️  No 9:20 data found. Run at 9:20 first.")
                return []
            
            # Get WebSocket codes for 9:20 movers
            mover_tokens = [mover['token'] for mover in _movers_920]
            mover_codes = get_websocket_codes_for_tokens(mover_tokens)
            
            print(f"📋 Checking momentum for {len(mover_codes)} stocks")
            
            # Subscribe to mover stocks only
            subscribe_to_websocket_codes(mover_codes)
            
            # Wait for data
            print(f"⏳ Waiting {wait_time} seconds for data...")
            sleep(wait_time)
            
            # Check which ones maintained momentum
            final_symbols = check_momentum_maintained()
            print(f"🎯 Final result: {len(final_symbols)} stocks ready for trading")
            return final_symbols
        
        # Other times
        else:
            print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
            print("❌ Strategy only runs at 9:20 AM and 9:25 AM")
            return []
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def cleanup():
    """Clean up WebSocket connection"""
    global _sio, _is_connected, _current_prices
    
    try:
        if _sio and _sio.connected:
            _sio.disconnect()
        _is_connected = False
        _current_prices.clear()
    except:
        pass

# Example usage
if __name__ == "__main__":
    print("🚀 Smart Trading Strategy - Stock Symbol Detection")
    print(f"⏰ Current time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    # Run the trading strategy
    final_symbols = run_trading_strategy(wait_time=3.0)
    
    if final_symbols:
        print(f"\n🎯 Final Trading Symbols ({len(final_symbols)}):")
        print("=" * 60)
        
        for i, symbol in enumerate(final_symbols, 1):
            print(f"   {i:2d}. {symbol}")
        
        print("=" * 60)
        print("\n💡 Use these symbols in ICICI Direct app for trading")
    else:
        print("❌ No symbols found for trading")
    
    # Cleanup
    cleanup()
    print("\n✅ Done!")
