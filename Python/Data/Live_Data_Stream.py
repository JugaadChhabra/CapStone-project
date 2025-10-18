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
_stock_codes = {}
_current_prices = {}
_connection_lock = threading.Lock()
_is_connected = False

def load_stock_codes(csv_file_path="stock_names_symbol.csv"):
    """Load stock codes from CSV file"""
    try:
        df = pd.read_csv(csv_file_path, header=None, names=['company_name', 'symbol', 'token'])
        
        stock_codes = {}
        for _, row in df.iterrows():
            company_name = str(row['company_name']).strip()
            symbol = str(row['symbol']).strip()
            token = str(row['token']).strip()
            
            if not company_name or not symbol or not token or token == 'nan':
                continue
            
            # Clean stock name
            name_parts = company_name.replace(' Limited', '').replace(' Ltd', '').replace(' LIMITED', '').split()
            stock_name = ' '.join(name_parts[:2] if len(name_parts) > 3 else name_parts)
            
            # Create WebSocket code
            if symbol.upper() in ['NIFTY', 'SENSEX', 'BANKNIFTY']:
                websocket_code = symbol.upper()
            else:
                websocket_code = f"4.1!{token}"
            
            stock_codes[stock_name] = websocket_code
        
        return stock_codes
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return {"NIFTY": "NIFTY", "NCC": "4.1!2319", "VOLTAS": "4.1!3718"}

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

def subscribe_to_stocks(stock_names: List[str]):
    """Subscribe to stock updates"""
    global _stock_codes, _sio
    
    stock_codes = []
    for name in stock_names:
        for stock_name, code in _stock_codes.items():
            if name.upper() in stock_name.upper():
                stock_codes.append(code)
                break
    
    for code in stock_codes:
        _sio.emit('join', code)
    
    return stock_codes

# Global storage for 9:20 data
_data_920 = {}

def determine_target_stocks(current_time, requested_stocks):
    """Determine which stocks to fetch based on time and strategy"""
    global _stock_codes
    
    hour = current_time.hour
    minute = current_time.minute
    
    # 9:20 AM - Get all stocks to find 2%+ movers
    if hour == 9 and 18 <= minute <= 22:
        return {
            'strategy': '9:20 AM - Find 2% Movers',
            'stocks': list(_stock_codes.keys())[:200]  # All available stocks
        }
    
    # 9:25 AM - Get only stocks that moved 2%+ at 9:20
    elif hour == 9 and 23 <= minute <= 27:
        if _data_920:
            movers = list(_data_920.keys())
            return {
                'strategy': '9:25 AM - Check Momentum',
                'stocks': movers
            }
        else:
            print("⚠️  No 9:20 data found. Getting all stocks instead.")
            return {
                'strategy': '9:25 AM - Fallback to All Stocks',
                'stocks': list(_stock_codes.keys())[:50]
            }
    
    # Other times - Use requested stocks or default selection
    else:
        if requested_stocks:
            return {
                'strategy': 'Manual Selection',
                'stocks': requested_stocks
            }
        else:
            return {
                'strategy': 'Default Selection',
                'stocks': list(_stock_codes.keys())[:20]  # Top 20 stocks
            }

def collect_stock_results(target_stocks):
    """Collect and format stock price results"""
    global _current_prices, _connection_lock, _stock_codes
    
    results = {}
    with _connection_lock:
        for requested_name in target_stocks:
            for symbol, price_data in _current_prices.items():
                # Find matching stock name
                for stock_name, code in _stock_codes.items():
                    if (code == symbol and 
                        requested_name.upper() in stock_name.upper()):
                        results[requested_name] = {
                            'price': price_data['price'],
                            'change': price_data['change'],
                            'high': price_data['high'],
                            'low': price_data['low'],
                            'open': price_data['open'],
                            'volume': price_data['volume'],
                            'timestamp': price_data['timestamp'],
                            'percentage_change': calculate_percentage_change(price_data['price'], price_data['change'])
                        }
                        break
    return results

def calculate_percentage_change(current_price, change):
    """Calculate percentage change"""
    if current_price > 0 and change != 0:
        return (change / (current_price - change)) * 100
    return 0

def filter_significant_movers(results, min_percentage=2.0):
    """Filter stocks with significant percentage movement"""
    movers = {}
    for stock, data in results.items():
        if abs(data['percentage_change']) >= min_percentage:
            movers[stock] = data
    
    print(f"🔍 Found {len(movers)} stocks with {min_percentage}%+ movement:")
    for stock, data in movers.items():
        direction = "📈" if data['change'] >= 0 else "📉"
        print(f"   {direction} {stock}: {data['percentage_change']:+.2f}% (₹{data['price']:.2f})")
    
    return movers

def save_920_data(results):
    """Save 9:20 data for later comparison at 9:25"""
    global _data_920
    _data_920 = results.copy()
    print(f"💾 Saved 9:20 data for {len(_data_920)} stocks")

def filter_momentum_maintained(results):
    """Filter stocks that maintained momentum from 9:20 to 9:25"""
    global _data_920
    
    maintained = {}
    for stock, current_data in results.items():
        if stock in _data_920:
            data_920 = _data_920[stock]
            current_change = current_data['percentage_change']
            change_920 = data_920['percentage_change']
            
            # Check if momentum is maintained (not retraced more than 50%)
            if change_920 > 0:  # Was positive at 9:20
                if current_change >= (change_920 * 0.5):  # Still at least 50% of original gain
                    maintained[stock] = current_data
            else:  # Was negative at 9:20
                if current_change <= (change_920 * 0.5):  # Still at least 50% of original loss
                    maintained[stock] = current_data
    
    print(f"⚡ {len(maintained)} stocks maintained momentum from 9:20:")
    for stock, data in maintained.items():
        direction = "📈" if data['change'] >= 0 else "📉"
        change_920 = _data_920[stock]['percentage_change'] if stock in _data_920 else 0
        print(f"   {direction} {stock}: {change_920:+.2f}% → {data['percentage_change']:+.2f}%")
    
    return maintained

def get_stock_prices(stock_names: List[str] = None, wait_time: float = 5.0) -> Dict[str, Dict]:
    """
    Smart function to get current stock prices based on time and trading strategy
    
    Args:
        stock_names: List of stock names (if None, auto-selects based on time)
        wait_time: Time to wait for data collection (default: 5 seconds)
    
    Returns:
        Dict with stock names as keys and price info as values
    
    Auto-Strategy:
        - 9:20 AM: Fetches ALL stocks to find 2%+ movers
        - 9:25 AM: Fetches only stocks that moved 2%+ at 9:20 and maintained momentum
        - Other times: Fetches specified stocks or top 20 if none specified
    """
    global _stock_codes, _current_prices, _connection_lock
    
    try:
        # Step 1: Load stock codes if needed
        if not _stock_codes:
            _stock_codes = load_stock_codes()
            print(f"📊 Loaded {len(_stock_codes)} stocks from CSV")
        
        # Step 2: Determine which stocks to fetch based on time and strategy
        current_time = datetime.now().time()
        target_stocks = determine_target_stocks(current_time, stock_names)
        
        if not target_stocks:
            print("❌ No stocks to fetch")
            return {}
        
        print(f"🎯 Strategy: {target_stocks['strategy']}")
        print(f"📋 Fetching {len(target_stocks['stocks'])} stocks")
        
        # Step 3: Connect to WebSocket
        if not connect_websocket():
            raise Exception("Failed to connect to WebSocket")
        
        # Step 4: Subscribe to target stocks
        subscribed_codes = subscribe_to_stocks(target_stocks['stocks'])
        print(f"🔗 Subscribed to {len(subscribed_codes)} stocks")
        
        # Step 5: Wait for data to arrive
        print(f"⏳ Waiting {wait_time} seconds for data...")
        sleep(wait_time)
        
        # Step 6: Collect and format results
        results = collect_stock_results(target_stocks['stocks'])
        
        # Step 7: Apply strategy-specific filtering
        if target_stocks['strategy'] == '9:20 AM - Find 2% Movers':
            results = filter_significant_movers(results, min_percentage=2.0)
            save_920_data(results)  # Save for 9:25 comparison
        elif target_stocks['strategy'] == '9:25 AM - Check Momentum':
            results = filter_momentum_maintained(results)
        
        print(f"✅ Retrieved data for {len(results)} stocks")
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {}

def get_available_stocks() -> List[str]:
    """Get list of all available stock names"""
    global _stock_codes
    
    if not _stock_codes:
        _stock_codes = load_stock_codes()
    
    return list(_stock_codes.keys())

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
    print("🚀 Smart Trading Strategy - Time-Based Stock Selection")
    print(f"⏰ Current time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    # Smart auto-selection based on time
    prices = get_stock_prices(wait_time=3.0)  # No stock names = auto-select based on time
    
    if prices:
        print("\n📊 Results:")
        print("=" * 60)
        
        for stock, data in prices.items():
            change_symbol = "📈" if data['change'] >= 0 else "📉"
            print(f"{change_symbol} {stock:<20} | ₹{data['price']:>8,.2f} | {data['percentage_change']:>+6.2f}%")
        
        print("=" * 60)
    else:
        print("❌ No data retrieved")
    
    # Manual selection example
    print("\n🔧 Manual Selection Example:")
    manual_stocks = ['Reliance', 'TCS', 'HDFC Bank']
    manual_prices = get_stock_prices(manual_stocks, wait_time=2.0)
    
    for stock, data in manual_prices.items():
        if data:
            print(f"   {stock}: ₹{data['price']:.2f} ({data['percentage_change']:+.2f}%)")
    
    # Cleanup
    cleanup()
    print("\n✅ Done!")
