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
                # Log first few data points
                if len(_current_prices) <= 5:
                    print(f"📊 Received data for {parsed['symbol']}: Price={parsed.get('price', 'N/A')}, Change={parsed.get('change', 'N/A')}")
                elif len(_current_prices) % 50 == 0:  # Log every 50th stock
                    print(f"📊 Received data for {len(_current_prices)} stocks so far...")

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
    
    print(f"📡 Subscribing to {len(websocket_codes)} stocks...")
    print(f"📋 Sample codes: {websocket_codes[:5]}...")  # Show first 5 codes
    
    for code in websocket_codes:
        _sio.emit('join', code)
    
    print(f"✅ Subscription requests sent for {len(websocket_codes)} stocks")
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
    all_movements = []  # Store all stock movements for logging
    
    with _connection_lock:
        print(f"📊 Analyzing {len(_current_prices)} stocks with live data...")
        
        for websocket_code, price_data in _current_prices.items():
            # Find the corresponding stock symbol
            for stock in _stock_data:
                if stock['websocket_code'] == websocket_code:
                    percentage_change = calculate_percentage_change(price_data['price'], price_data['change'])
                    
                    # Store all movements for logging
                    all_movements.append({
                        'symbol': stock['symbol'],
                        'percentage': percentage_change,
                        'price': price_data['price'],
                        'change': price_data['change']
                    })
                    
                    # Debug logging for first few stocks
                    if len(all_movements) <= 3:
                        print(f"   DEBUG: {stock['symbol']} -> {percentage_change:.2f}% (price: {price_data['price']}, change: {price_data['change']})")
                    
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
    
    # Sort all movements by absolute percentage change (highest first)
    all_movements.sort(key=lambda x: abs(x['percentage']), reverse=True)
    
    # Log the top 10 movers (regardless of 2% threshold)
    print(f"\n� TOP 10 STOCKS BY MOVEMENT:")
    print("-" * 50)
    for i, stock in enumerate(all_movements[:10], 1):
        direction = "📈" if stock['change'] >= 0 else "📉"
        threshold_status = "✅" if abs(stock['percentage']) >= 2.0 else "❌"
        print(f"{i:2d}. {direction} {stock['symbol']:8s}: {stock['percentage']:+6.2f}% {threshold_status}")
    
    # Log stocks that qualified
    _movers_920 = movers
    print(f"\n🎯 QUALIFIED STOCKS (2%+ movement): {len(movers)}")
    if movers:
        print("-" * 50)
        for mover in movers:
            direction = "📈" if mover['change_920'] >= 0 else "📉"
            print(f"   {direction} {mover['symbol']:8s}: {mover['percentage_920']:+6.2f}%")
    else:
        print("   No stocks reached 2% threshold")
    
    # Log summary statistics
    if all_movements:
        max_move = max(all_movements, key=lambda x: abs(x['percentage']))
        avg_move = sum(abs(x['percentage']) for x in all_movements) / len(all_movements)
        print(f"\n📊 MOVEMENT SUMMARY:")
        print(f"   Biggest mover: {max_move['symbol']} ({max_move['percentage']:+.2f}%)")
        print(f"   Average movement: {avg_move:.2f}%")
        print(f"   Stocks with data: {len(all_movements)}")
    
    return [mover['symbol'] for mover in movers]

def check_momentum_maintained():
    """Check which stocks maintained momentum from 9:20 to 9:25"""
    global _current_prices, _connection_lock, _movers_920, _final_stocks_925
    
    maintained = []
    momentum_analysis = []  # Store analysis for all 9:20 movers
    
    with _connection_lock:
        print(f"📊 Checking momentum for {len(_movers_920)} stocks from 9:20...")
        
        for mover in _movers_920:
            websocket_code = mover['websocket_code']
            
            if websocket_code in _current_prices:
                current_data = _current_prices[websocket_code]
                current_percentage = calculate_percentage_change(current_data['price'], current_data['change'])
                original_percentage = mover['percentage_920']
                
                # Calculate momentum retention
                if original_percentage > 0:  # Was positive at 9:20
                    momentum_retained = (current_percentage / original_percentage) * 100 if original_percentage != 0 else 0
                    momentum_ok = current_percentage >= (original_percentage * 0.5)
                else:  # Was negative at 9:20
                    momentum_retained = (current_percentage / original_percentage) * 100 if original_percentage != 0 else 0
                    momentum_ok = current_percentage <= (original_percentage * 0.5)
                
                momentum_analysis.append({
                    'symbol': mover['symbol'],
                    'percentage_920': original_percentage,
                    'percentage_925': current_percentage,
                    'momentum_retained': momentum_retained,
                    'qualified': momentum_ok
                })
                
                # Check if momentum is maintained (not retraced more than 50%)
                if momentum_ok:
                    maintained.append(mover['symbol'])
            else:
                # No current data for this stock
                momentum_analysis.append({
                    'symbol': mover['symbol'],
                    'percentage_920': mover['percentage_920'],
                    'percentage_925': 0,
                    'momentum_retained': 0,
                    'qualified': False,
                    'note': 'No live data'
                })
    
    # Log detailed momentum analysis
    print(f"\n📊 MOMENTUM ANALYSIS (9:20 → 9:25):")
    print("-" * 70)
    print(f"{'Stock':<8} {'9:20%':<8} {'9:25%':<8} {'Retained':<10} {'Status'}")
    print("-" * 70)
    
    for analysis in momentum_analysis:
        status = "✅ PASS" if analysis['qualified'] else "❌ FAIL"
        note = f" ({analysis.get('note', '')})" if 'note' in analysis else ""
        print(f"{analysis['symbol']:<8} {analysis['percentage_920']:+6.2f}% {analysis['percentage_925']:+6.2f}% "
              f"{analysis['momentum_retained']:6.1f}%   {status}{note}")
    
    _final_stocks_925 = maintained
    print(f"\n🎯 MOMENTUM MAINTAINED: {len(maintained)} stocks")
    if maintained:
        print("-" * 30)
        for symbol in maintained:
            print(f"   ⚡ {symbol}")
    else:
        print("   No stocks maintained sufficient momentum")
    
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
        
    Note: Time restrictions removed - relies on user to run at correct times
    """
    global _stock_data, _websocket_codes, _current_prices, _movers_920
    
    try:
        # Step 1: Load stock data if needed
        if not _stock_data:
            _stock_data, _websocket_codes = load_stock_data()
            print(f"📊 Loaded {len(_stock_data)} stocks from CSV")
        
        # Step 2: Connect to WebSocket
        if not connect_websocket():
            raise Exception("Failed to connect to WebSocket")
        
        current_time = datetime.now().time()
        print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
        
        # Determine strategy based on whether we have 9:20 data or not
        if not _movers_920:
            # No 9:20 data exists - this is the 9:20 AM run
            print("🎯 Strategy: Finding 2% Movers (9:20 AM mode)")
            print(f"📋 Fetching ALL {len(_websocket_codes)} stocks")
            
            # Subscribe to all stocks
            subscribe_to_websocket_codes(_websocket_codes)
            
            # Wait for data
            print(f"⏳ Waiting {wait_time} seconds for data...")
            sleep(wait_time)
            
            # Check how much data we received
            print(f"📊 Received live data for {len(_current_prices)} out of {len(_websocket_codes)} stocks")
            
            if len(_current_prices) == 0:
                print("❌ No live data received! Check:")
                print("   - Market timing (9:15 AM - 3:30 PM)")
                print("   - Session token validity") 
                print("   - Network connection")
                print("\n🎲 Using mock data for testing...")
                
                # Import and use mock data
                try:
                    from mock_live_data import inject_mock_data_into_live_stream
                    mock_count = inject_mock_data_into_live_stream()
                    print(f"✅ Generated {mock_count} mock data points")
                except ImportError:
                    print("❌ Mock data generator not available")
                    return []
                except Exception as e:
                    print(f"❌ Error generating mock data: {e}")
                    return []
            
            # Find 2% movers and save their symbols
            movers_symbols = find_2_percent_movers()
            print(f"✅ Saved {len(movers_symbols)} stocks with 2%+ movement")
            return movers_symbols
            
        else:
            # 9:20 data exists - this is the 9:25 AM run  
            print("🎯 Strategy: Checking Momentum (9:25 AM mode)")
            print(f"📋 Found {len(_movers_920)} stocks from 9:20 AM run")
            
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
        
    except Exception as e:
        print(f"❌ Error in run_trading_strategy: {e}")
        import traceback
        traceback.print_exc()
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
