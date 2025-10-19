#!/usr/bin/env python3
"""
Test script to run the trading strategy backtest
"""

from Backtest_Trading_Strategy import TradingStrategyBacktest
import json
from datetime import datetime

def run_backtest_test():
    """Run a quick backtest test"""
    
    print("🧪 Running Trading Strategy Backtest Test")
    print("=" * 60)
    
    # File paths
    previous_closes_file = "test_folder/previous_day_closes_20251019_192152.json"
    ohlc_data_file = "test_folder/latest_ohlc_data.json"
    
    try:
        # Initialize and run backtest
        backtest = TradingStrategyBacktest(previous_closes_file, ohlc_data_file)
        
        # Run the strategy
        movers_920, maintained_925 = backtest.run_full_backtest()
        
        # Print final results
        if maintained_925:
            print(f"\n🎯 TRADING SIGNALS GENERATED:")
            print("-" * 60)
            
            for stock in maintained_925:
                signal_strength = "STRONG" if abs(stock['percentage_925']) >= 3.0 else "MODERATE"
                direction = "BUY" if stock['percentage_925'] > 0 else "SELL"
                
                print(f"📊 {stock['symbol']:8s} | {direction:4s} | "
                      f"{stock['percentage_925']:+6.2f}% | {signal_strength}")
            
            print("-" * 60)
            print(f"💡 Total signals: {len(maintained_925)}")
        else:
            print("\n❌ No trading signals generated for this day")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = run_backtest_test()
    
    if success:
        print("\n✅ Backtest test completed!")
    else:
        print("\n❌ Backtest test failed!")