#!/usr/bin/env python3
"""
Mock Live Data Generator
Provides realistic mock data when WebSocket connection fails
"""

import random
from datetime import datetime
from typing import Dict, List

def generate_mock_stock_data(stock_symbols: List[str], base_prices: Dict[str, float] = None) -> Dict[str, Dict]:
    """
    Generate realistic mock stock data for testing
    
    Args:
        stock_symbols: List of stock symbols to generate data for
        base_prices: Optional base prices (from previous day closes)
    
    Returns:
        Dict of stock_symbol -> price_data
    """
    mock_data = {}
    
    # Default base prices if not provided
    default_prices = {
        "RELIANCE": 3000.0, "TCS": 4000.0, "INFY": 1800.0, 
        "HDFCBANK": 1700.0, "ICICIBANK": 1200.0, "KOTAKBANK": 1800.0,
        "SBIN": 800.0, "ITC": 450.0, "HINDUNILVR": 2400.0,
        "BAJFINANCE": 7000.0, "ASIANPAINT": 3200.0, "MARUTI": 11000.0,
        "NTPC": 350.0, "POWERGRID": 250.0, "COALINDIA": 400.0,
        "ULTRACEMCO": 11000.0, "NESTLEIND": 2200.0, "TITAN": 3400.0,
        "WIPRO": 550.0, "TECHM": 1700.0
    }
    
    prices_to_use = base_prices if base_prices else default_prices
    
    # Generate data for each stock
    for symbol in stock_symbols:
        # Get base price
        if symbol in prices_to_use:
            base_price = prices_to_use[symbol]
        else:
            base_price = random.uniform(100, 5000)  # Random price for unknown stocks
        
        # Generate realistic movement (-5% to +5%)
        movement_percent = random.uniform(-5.0, 5.0)
        change = base_price * (movement_percent / 100)
        current_price = base_price + change
        
        # Create realistic opening price
        opening_price = base_price + random.uniform(-1, 1)
        
        # Generate high/low based on current price
        high_price = max(current_price, opening_price) + random.uniform(0, current_price * 0.02)
        low_price = min(current_price, opening_price) - random.uniform(0, current_price * 0.02)
        
        mock_data[symbol] = {
            "symbol": symbol,
            "open": opening_price,
            "price": current_price,
            "high": high_price,
            "low": low_price,
            "change": change,
            "volume": random.randint(10000, 1000000),
            "timestamp": datetime.now()
        }
    
    return mock_data

def inject_mock_data_into_live_stream() -> int:
    """
    Inject mock data into the live stream manager
    
    Returns:
        Number of mock data points created
    """
    try:
        # Import the live stream globals
        from live_data_stream import _ws_manager, _stock_data
        
        if not _ws_manager or not _stock_data:
            print("❌ WebSocket manager or stock data not available")
            return 0
        
        # Get stock symbols from loaded data
        stock_symbols = [stock['symbol'] for stock in _stock_data[:50]]  # Limit to 50 for testing
        
        # Generate mock data
        mock_data = generate_mock_stock_data(stock_symbols)
        
        # Inject into WebSocket manager's current prices
        with _ws_manager._connection_lock:
            _ws_manager._current_prices.update(mock_data)
        
        print(f"✅ Injected {len(mock_data)} mock data points")
        
        # Show sample of injected data
        sample_symbols = list(mock_data.keys())[:5]
        for symbol in sample_symbols:
            data = mock_data[symbol]
            print(f"   📊 {symbol}: ₹{data['price']:.2f} ({data['change']:+.2f})")
        
        return len(mock_data)
        
    except Exception as e:
        print(f"❌ Error injecting mock data: {e}")
        return 0

def create_2_percent_movers_mock_data() -> Dict[str, Dict]:
    """
    Create mock data with guaranteed 2%+ movers for testing
    
    Returns:
        Dict of stock_symbol -> price_data with some stocks having 2%+ moves
    """
    # Define stocks with guaranteed movements
    guaranteed_movers = {
        "RELIANCE": {"base": 3000.0, "movement": 2.5},      # +2.5%
        "TCS": {"base": 4000.0, "movement": -2.8},          # -2.8%
        "INFY": {"base": 1800.0, "movement": 3.2},          # +3.2%
        "HDFCBANK": {"base": 1700.0, "movement": -2.1},     # -2.1%
        "BAJFINANCE": {"base": 7000.0, "movement": 4.5},    # +4.5%
    }
    
    # Create normal stocks (under 2% movement)
    normal_stocks = {
        "ICICIBANK": {"base": 1200.0, "movement": 1.2},
        "KOTAKBANK": {"base": 1800.0, "movement": -0.8},
        "SBIN": {"base": 800.0, "movement": 1.5},
        "ITC": {"base": 450.0, "movement": -1.1},
        "HINDUNILVR": {"base": 2400.0, "movement": 0.9},
    }
    
    all_stocks = {**guaranteed_movers, **normal_stocks}
    mock_data = {}
    
    for symbol, config in all_stocks.items():
        base_price = config["base"]
        movement_percent = config["movement"]
        change = base_price * (movement_percent / 100)
        current_price = base_price + change
        
        mock_data[symbol] = {
            "symbol": symbol,
            "open": base_price,
            "price": current_price,
            "high": max(current_price, base_price) + random.uniform(0, 10),
            "low": min(current_price, base_price) - random.uniform(0, 10),
            "change": change,
            "volume": random.randint(50000, 500000),
            "timestamp": datetime.now()
        }
    
    print(f"✅ Created mock data with {len(guaranteed_movers)} guaranteed 2%+ movers")
    for symbol, config in guaranteed_movers.items():
        print(f"   📈 {symbol}: {config['movement']:+.1f}% movement")
    
    return mock_data

if __name__ == "__main__":
    print("🧪 Testing Mock Data Generator")
    
    # Test basic mock data generation
    test_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
    mock_data = generate_mock_stock_data(test_symbols)
    
    print(f"\n📊 Generated {len(mock_data)} mock data points:")
    for symbol, data in mock_data.items():
        print(f"   {symbol}: ₹{data['price']:.2f} ({data['change']:+.2f})")
    
    # Test 2% movers
    print("\n🎯 Testing 2% Movers Mock Data:")
    movers_data = create_2_percent_movers_mock_data()
    
    print("\n✅ Mock data generator working correctly!")