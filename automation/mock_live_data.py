#!/usr/bin/env python3
"""
Mock Live Data Generator
Simulates live market data for testing the trading strategy when WebSocket isn't receiving data
"""

import random, json, pandas as pd
from datetime import datetime
from typing import Dict, List

def generate_mock_movements(stock_data: List[Dict], previous_day_closes: Dict = None) -> Dict:
    """
    Generate realistic mock price movements for stocks
    
    Args:
        stock_data: List of stock information with symbols
        previous_day_closes: Previous day closing prices (optional)
    
    Returns:
        Dict with websocket_code as key and price data as value
    """
    mock_prices = {}
    
    print("🎲 Generating mock live data for testing...")
    
    for stock in stock_data:
        symbol = stock['symbol']
        websocket_code = stock['websocket_code']
        
        # Get previous close or generate a random base price
        if previous_day_closes and symbol in previous_day_closes:
            prev_close = previous_day_closes[symbol]
        else:
            prev_close = random.uniform(100, 2000)  # Random base price
        
        # Generate realistic price movement
        # 80% of stocks move less than 2%, 15% move 2-5%, 5% move more than 5%
        movement_type = random.choices(
            ['small', 'medium', 'large'], 
            weights=[80, 15, 5]
        )[0]
        
        if movement_type == 'small':
            change_percent = random.uniform(-1.5, 1.5)
        elif movement_type == 'medium':
            change_percent = random.uniform(-4.0, 4.0)
        else:  # large
            change_percent = random.uniform(-8.0, 8.0)
        
        # Calculate actual prices
        change_amount = prev_close * (change_percent / 100)
        current_price = prev_close + change_amount
        
        # Generate other OHLC data
        if change_amount > 0:  # Stock is up
            open_price = random.uniform(prev_close * 0.995, prev_close * 1.005)
            high_price = max(current_price, random.uniform(current_price * 0.999, current_price * 1.002))
            low_price = min(open_price, random.uniform(open_price * 0.995, open_price * 1.001))
        else:  # Stock is down
            open_price = random.uniform(prev_close * 0.995, prev_close * 1.005)
            low_price = min(current_price, random.uniform(current_price * 0.998, current_price * 1.001))
            high_price = max(open_price, random.uniform(open_price * 0.999, open_price * 1.005))
        
        # Create mock data in the same format as WebSocket
        mock_prices[websocket_code] = {
            "symbol": symbol,
            "open": round(open_price, 2),
            "price": round(current_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "change": round(change_amount, 2),
            "volume": random.randint(1000, 100000),
            "timestamp": datetime.now()
        }
    
    # Report statistics
    movements = [data['change'] / (data['price'] - data['change']) * 100 for data in mock_prices.values()]
    large_movers = [m for m in movements if abs(m) >= 2.0]
    
    print(f"📊 Generated data for {len(mock_prices)} stocks")
    print(f"📈 {len(large_movers)} stocks have 2%+ movement")
    print(f"🎯 Top movers: {sorted(movements, key=abs, reverse=True)[:5]}")
    
    return mock_prices

def inject_mock_data_into_live_stream():
    """
    Inject mock data into Live_Data_Stream for testing
    """
    from Live_Data_Stream import _stock_data, _current_prices, _connection_lock, load_stock_data
    import json
    import os
    
    # Load stock data if not already loaded
    if not _stock_data:
        stock_data, _ = load_stock_data()
    else:
        stock_data = _stock_data
    
    # Try to load previous day closes
    previous_closes = {}
    for file in os.listdir('.'):
        if file.startswith('previous_day_closes_') and file.endswith('.json'):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    previous_closes = data.get('previous_closes', {})
                    print(f"📁 Loaded previous closes from {file}")
                    break
            except:
                continue
    
    # Generate mock data
    mock_data = generate_mock_movements(stock_data, previous_closes)
    
    # Inject into Live_Data_Stream
    with _connection_lock:
        _current_prices.clear()
        _current_prices.update(mock_data)
    
    print(f"✅ Injected {len(mock_data)} mock price points into Live_Data_Stream")
    return len(mock_data)

if __name__ == "__main__":
    # Test the mock data generator
    from Live_Data_Stream import load_stock_data
    
    stock_data, _ = load_stock_data()
    mock_data = generate_mock_movements(stock_data[:10])  # Test with 10 stocks
    
    print("\n📋 Sample mock data:")
    for i, (code, data) in enumerate(list(mock_data.items())[:5]):
        change_percent = (data['change'] / (data['price'] - data['change'])) * 100
        print(f"   {data['symbol']:8s}: {change_percent:+6.2f}% (₹{data['price']:.2f})")