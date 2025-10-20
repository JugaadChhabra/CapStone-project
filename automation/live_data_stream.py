"""
Live Data Stream - Clean Trading Strategy Version

PURPOSE: Real-time trading strategy execution using centralized WebSocket management
FOCUS: Pure trading logic without WebSocket infrastructure code

FUNCTIONS OVERVIEW:
├── find_2_percent_movers() -> Identify stocks with 2%+ movement
├── check_momentum_maintained() -> Verify momentum retention
├── calculate_percentage_change() -> Utility for percentage calculations
└── run_trading_strategy() -> Main strategy orchestrator

USAGE:
    from Live_Data_Stream import run_trading_strategy
    final_symbols = run_trading_strategy()
"""

from datetime import datetime
from time import sleep
from typing import Dict, List
from icici_functions import load_stock_data_from_csv
from websocket_connection import WebSocketManager, get_websocket_codes_for_tokens

# Global variables for trading strategy state
_stock_data = []
_websocket_codes = []
_ws_manager = None

# Global storage for 9:20 and 9:25 data
_movers_920 = []  # Stock symbols with 2%+ movement at 9:20
_final_stocks_925 = []  # Stock symbols that maintained momentum at 9:25

def load_stock_data():
    """Load stock data using centralized utility"""
    global _stock_data, _websocket_codes
    
    _stock_data, _websocket_codes = load_stock_data_from_csv('websocket_ready')
    return _stock_data, _websocket_codes

def find_2_percent_movers():
    """Find stocks with 2%+ movement at 9:20"""
    global _ws_manager, _stock_data, _movers_920
    
    movers = []
    all_movements = []  # Store all stock movements for logging
    
    # Get current prices from WebSocket manager
    current_prices = _ws_manager.get_current_prices()
    print(f"📊 Analyzing {len(current_prices)} stocks with live data...")
    
    for websocket_code, price_data in current_prices.items():
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
    global _ws_manager, _movers_920, _final_stocks_925
    
    maintained = []
    momentum_analysis = []  # Store analysis for all 9:20 movers
    
    # Get current prices from WebSocket manager
    current_prices = _ws_manager.get_current_prices()
    print(f"📊 Checking momentum for {len(_movers_920)} stocks from 9:20...")
    
    for mover in _movers_920:
        websocket_code = mover['websocket_code']
        
        if websocket_code in current_prices:
            current_data = current_prices[websocket_code]
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
    Main trading strategy function using centralized WebSocket manager
    
    Returns:
        List of stock symbols that passed both 9:20 and 9:25 filters
    
    Process:
        - 9:20 AM: Get ALL 200+ stocks, find 2%+ movers, save their symbols
        - 9:25 AM: Get only the 9:20 movers, find ones that maintained 50%+ momentum
        - Returns: Final list of stock symbols for trading
        
    Note: Time restrictions removed - relies on user to run at correct times
    """
    global _stock_data, _websocket_codes, _movers_920, _ws_manager
    
    try:
        # Step 1: Load stock data if needed
        if not _stock_data:
            _stock_data, _websocket_codes = load_stock_data()
            print(f"📊 Loaded {len(_stock_data)} stocks from CSV")
        
        # Step 2: Initialize WebSocket manager
        _ws_manager = WebSocketManager()
        
        # Step 3: Connect to WebSocket
        if not _ws_manager.connect():
            raise Exception("Failed to connect to WebSocket")
        
        current_time = datetime.now().time()
        print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
        
        # Determine strategy based on whether we have 9:20 data or not
        if not _movers_920:
            # No 9:20 data exists - this is the 9:20 AM run
            print("🎯 Strategy: Finding 2% Movers (9:20 AM mode)")
            print(f"📋 Fetching ALL {len(_websocket_codes)} stocks")
            
            # Subscribe to all stocks
            _ws_manager.subscribe_to_codes(_websocket_codes)
            
            # Wait for data
            print(f"⏳ Waiting {wait_time} seconds for data...")
            sleep(wait_time)
            
            # Check how much data we received
            price_count = _ws_manager.get_price_count()
            print(f"📊 Received live data for {price_count} out of {len(_websocket_codes)} stocks")
            
            if price_count == 0:
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
            mover_codes = get_websocket_codes_for_tokens(mover_tokens, _stock_data)
            
            print(f"📋 Checking momentum for {len(mover_codes)} stocks")
            
            # Subscribe to mover stocks only
            _ws_manager.subscribe_to_codes(mover_codes)
            
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
    finally:
        # Clean up WebSocket connection
        if _ws_manager:
            _ws_manager.disconnect()

def cleanup():
    """Clean up WebSocket connection"""
    global _ws_manager
    
    try:
        if _ws_manager:
            _ws_manager.disconnect()
            _ws_manager = None
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
