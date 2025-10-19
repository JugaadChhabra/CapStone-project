#!/usr/bin/env python3
"""
Debug script to investigate the backtest data and find issues
"""

import json
from datetime import datetime
import pandas as pd

def debug_backtest_data():
    """Debug the backtest data to understand why no movers were found"""
    
    print("🔍 DEBUGGING BACKTEST DATA")
    print("=" * 80)
    
    # Load the data files
    try:
        # Load previous closes
        with open("test_folder/previous_day_closes_20251019_192152.json", 'r') as f:
            prev_data = json.load(f)
            previous_closes = prev_data.get('previous_closes', {})
        
        # Load OHLC data
        with open("test_folder/latest_ohlc_data.json", 'r') as f:
            ohlc_data = json.load(f)
            stocks_data = ohlc_data.get('stocks', {})
            collection_info = ohlc_data.get('collection_info', {})
        
        print(f"📊 Previous closes: {len(previous_closes)} stocks")
        print(f"📈 OHLC data: {len(stocks_data)} stocks")
        
        # Check a few sample stocks
        sample_stocks = list(previous_closes.keys())[:5]
        
        print(f"\n🔍 ANALYZING SAMPLE STOCKS:")
        print("=" * 80)
        
        for symbol in sample_stocks:
            print(f"\n📊 Stock: {symbol}")
            print(f"   Previous Close: ₹{previous_closes[symbol]}")
            
            if symbol in stocks_data:
                stock_ohlc = stocks_data[symbol]
                print(f"   OHLC entries: {len(stock_ohlc)}")
                
                if stock_ohlc:
                    # Show first few entries with timestamps
                    print("   Sample entries:")
                    for i, entry in enumerate(stock_ohlc[:3]):
                        timestamp = entry.get('timestamp', 'N/A')
                        close_price = entry.get('close', 'N/A')
                        volume = entry.get('volume', 'N/A')
                        
                        # Try to parse timestamp
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            time_str = dt.strftime('%H:%M:%S')
                        except:
                            time_str = timestamp
                        
                        # Calculate percentage if possible
                        if close_price != 'N/A':
                            pct_change = ((close_price - previous_closes[symbol]) / previous_closes[symbol]) * 100
                            print(f"     {i+1}. {time_str} | Close: ₹{close_price} | Change: {pct_change:+.2f}% | Vol: {volume}")
                        else:
                            print(f"     {i+1}. {time_str} | Close: {close_price} | Vol: {volume}")
                    
                    # Look specifically for 9:20 data
                    found_920 = False
                    for entry in stock_ohlc:
                        timestamp = entry.get('timestamp', '')
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            if dt.hour == 9 and 18 <= dt.minute <= 22:
                                close_price = entry.get('close')
                                pct_change = ((close_price - previous_closes[symbol]) / previous_closes[symbol]) * 100
                                print(f"   ✅ 9:20 data found: ₹{close_price} | Change: {pct_change:+.2f}%")
                                found_920 = True
                                break
                        except:
                            continue
                    
                    if not found_920:
                        print("   ❌ No 9:20 data found")
                else:
                    print("   ❌ No OHLC data available")
            else:
                print("   ❌ Symbol not found in OHLC data")
        
        # Check timestamp patterns
        print(f"\n⏰ TIMESTAMP ANALYSIS:")
        print("=" * 80)
        
        all_timestamps = []
        for symbol, data in stocks_data.items():
            if data:
                for entry in data[:2]:  # Just check first 2 entries per stock
                    timestamp = entry.get('timestamp', '')
                    if timestamp:
                        all_timestamps.append(timestamp)
        
        print(f"Sample timestamps:")
        for i, ts in enumerate(all_timestamps[:10]):
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M:%S')
                print(f"   {i+1}. {ts} → {time_str}")
            except Exception as e:
                print(f"   {i+1}. {ts} → Error: {e}")
        
        # Find stocks with significant movement
        print(f"\n🚀 CHECKING FOR ANY SIGNIFICANT MOVEMENTS:")
        print("=" * 80)
        
        movements_found = 0
        for symbol in list(previous_closes.keys())[:20]:  # Check first 20 stocks
            if symbol in stocks_data and stocks_data[symbol]:
                prev_close = previous_closes[symbol]
                
                for entry in stocks_data[symbol]:
                    close_price = entry.get('close')
                    if close_price:
                        pct_change = ((close_price - prev_close) / prev_close) * 100
                        if abs(pct_change) >= 1.0:  # Lower threshold for debugging
                            timestamp = entry.get('timestamp', 'N/A')
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                time_str = dt.strftime('%H:%M:%S')
                            except:
                                time_str = timestamp
                            
                            print(f"   📈 {symbol}: {pct_change:+.2f}% at {time_str} | ₹{prev_close} → ₹{close_price}")
                            movements_found += 1
                            break
        
        print(f"\n📊 Found {movements_found} stocks with 1%+ movement")
        
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_backtest_data()