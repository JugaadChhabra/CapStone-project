#!/usr/bin/env python3
"""
Main Trading Strategy Orchestrator
Implements the complete 3-step trading strategy:
1. Get previous day closes
2. Find 2% movers at 9:20 AM
3. Check momentum at 9:25 AM  
4. Filter by OI change >= 7%
"""

import json, os, subprocess, pandas as pd, helper_functions as hf
from datetime import datetime, timedelta, time
from typing import List, Dict, Optional


# Import our modules
from automation.data_loader import get_all_previous_day_closes
from Live_Data_Stream import (
    run_trading_strategy,
    load_stock_data,
    _movers_920,
    _final_stocks_925,
    _stock_data,
    _websocket_codes,
    cleanup
)
from mock_live_data import inject_mock_data_into_live_stream

class TradingStrategyOrchestrator:
    """Main orchestrator for the trading strategy"""
    
    def __init__(self):
        self.previous_day_closes = {}
        self.movers_920 = []
        self.momentum_925 = []
        self.oi_data = {}
        self.final_candidates = []
        
    
    def step1_get_previous_day_closes(self) -> bool:
        """Step 1: Get previous day closing prices for all stocks"""
        print("\n🎯 STEP 1: Getting Previous Day Closing Prices")
        print("=" * 60)
        
        target_date = hf.get_previous_day_close_date()
        print(f"📅 Target date: {target_date}")
        
        # Check if previous day closes file already exists for this date
        import glob
        existing_files = glob.glob("previous_day_closes_*.json")
        
        for file_path in existing_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    if data.get('collection_info', {}).get('target_date') == target_date:
                        print(f"✅ Previous day closes already exist for {target_date}")
                        print(f"📁 Using existing file: {file_path}")
                        
                        # Load the existing data
                        self.previous_day_closes = data.get('previous_closes', {})
                        print(f"📊 Loaded {len(self.previous_day_closes)} stocks from existing file")
                        return True
            except (json.JSONDecodeError, KeyError) as e:
                # Skip corrupted or malformed files
                print(f"⚠️  Skipping corrupted file {file_path}: {e}")
                continue
        
        print(f"📊 No existing file found for {target_date}. Fetching new data...")
        
        try:
            print("📊 Fetching previous day closes...")
            previous_closes = get_all_previous_day_closes()
            
            if previous_closes:
                self.previous_day_closes = previous_closes
                print(f"✅ Retrieved closes for {len(previous_closes)} stocks")
                
                # Save to file for reference
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"previous_day_closes_{timestamp}.json"
                
                save_data = {
                    "collection_info": {
                        "timestamp": datetime.now().isoformat(),
                        "target_date": target_date,
                        "total_stocks": len(previous_closes)
                    },
                    "previous_closes": previous_closes
                }
                
                with open(filename, 'w') as f:
                    json.dump(save_data, f, indent=2)
                
                print(f"💾 Saved to: {filename}")
                return True
            else:
                print("❌ Failed to get previous day closes")
                return False
                
        except Exception as e:
            print(f"❌ Error in Step 1: {e}")
            return False
    
    def step2_find_2_percent_movers_at_920(self) -> bool:
        """Step 2: Find 2% movers at 9:20 AM using Live_Data_Stream"""
        print("\n🎯 STEP 2: Finding 2% Movers at 9:20 AM")
        print("=" * 60)
        
        current_time = datetime.now().time()
        print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
        
        try:
            # Initialize global variables properly
            print("📊 Initializing stock data...")
            stock_data, websocket_codes = load_stock_data()
            _stock_data.clear()
            _stock_data.extend(stock_data)
            _websocket_codes.clear()
            _websocket_codes.extend(websocket_codes)
            print(f"✅ Loaded {len(_stock_data)} stocks for analysis")
            
            print("🔗 Connecting to live data stream...")
            movers = run_trading_strategy(wait_time=5.0)
            
            if movers:
                self.movers_920 = movers
                print(f"\n🎯 STEP 2 SUMMARY:")
                print("-" * 40)
                print(f"✅ Found {len(movers)} stocks with 2%+ movement")
                print(f"📋 2% Movers List:")
                for i, symbol in enumerate(movers, 1):
                    print(f"   {i:2d}. 📈 {symbol}")
                
                return True
            else:
                print("❌ No 2% movers found at 9:20")
                return False
                
        except Exception as e:
            print(f"❌ Error in Step 2: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def step3_check_momentum_at_925(self) -> bool:
        """Step 3: Check momentum maintenance at 9:25 AM"""
        print("\n🎯 STEP 3: Checking Momentum at 9:25 AM")
        print("=" * 60)
        
        if not self.movers_920:
            print("⚠️  No 9:20 movers found. Cannot proceed.")
            return False
        
        current_time = datetime.now().time()
        print(f"⏰ Current time: {current_time.strftime('%H:%M:%S')}")
        
        try:
            print(f"📊 Checking momentum for {len(self.movers_920)} stocks from 9:20...")
            
            # Generate new mock data for 9:25 simulation
            print("🔄 Generating new market data for momentum check...")
            try:
                new_data_count = inject_mock_data_into_live_stream()
                print(f"✅ Updated with {new_data_count} fresh data points")
            except Exception as e:
                print(f"⚠️  Using existing data: {e}")
            
            momentum_stocks = run_trading_strategy(wait_time=5.0)
            
            if momentum_stocks:
                self.momentum_925 = momentum_stocks
                print(f"\n🎯 STEP 3 SUMMARY:")
                print("-" * 40)
                print(f"✅ {len(momentum_stocks)} stocks maintained momentum")
                print(f"📋 Momentum Stocks List:")
                for i, symbol in enumerate(momentum_stocks, 1):
                    print(f"   {i:2d}. ⚡ {symbol}")
                
                return True
            else:
                print("❌ No stocks maintained momentum from 9:20 to 9:25")
                return False
                
        except Exception as e:
            print(f"❌ Error in Step 3: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def step4_get_oi_data(self) -> bool:
        """Step 4: Scrape OI data and filter by >= 7% change"""
        print("\n🎯 STEP 4: Getting OI Data and Filtering")
        print("=" * 60)
        
        if not self.momentum_925:
            print("⚠️  No momentum stocks found. Cannot proceed.")
            return False
        
        try:
            print("🔍 Scraping OI data from NSE...")
            
            # Run the scraping script
            result = subprocess.run(['python3', 'scraping.py'], 
                                  capture_output=True, text=True, cwd='.')
            
            if result.returncode == 0:
                print("✅ OI scraping completed")
                print(result.stdout)
                
                # Load the scraped OI data
                if os.path.exists("oi_spurts_nse_clean.csv"):
                    oi_df = pd.read_csv("oi_spurts_nse_clean.csv")
                    print(f"📊 Loaded OI data for {len(oi_df)} stocks")
                    
                    # Filter momentum stocks by OI >= 7%
                    qualified_stocks = []
                    
                    print(f"\n🎯 Filtering {len(self.momentum_925)} momentum stocks by OI >= 7%:")
                    print("-" * 60)
                    
                    for symbol in self.momentum_925:
                        # Find OI data for this symbol
                        oi_row = oi_df[oi_df['Symbol'].str.upper() == symbol.upper()]
                        
                        if not oi_row.empty:
                            try:
                                oi_change = oi_row.iloc[0]['OI_Change_Percent']
                                
                                if pd.notna(oi_change) and float(oi_change) >= 7.0:
                                    qualified_stocks.append({
                                        'symbol': symbol,
                                        'oi_change': float(oi_change)
                                    })
                                    print(f"   ✅ {symbol:8s}: OI +{oi_change:6.2f}%")
                                else:
                                    print(f"   ❌ {symbol:8s}: OI +{oi_change:6.2f}% (< 7%)")
                            except (ValueError, TypeError):
                                print(f"   ⚠️  {symbol:8s}: Invalid OI data")
                        else:
                            print(f"   ❌ {symbol:8s}: Not found in OI data")
                    
                    self.final_candidates = qualified_stocks
                    
                    if qualified_stocks:
                        print(f"\n🏆 FINAL CANDIDATES ({len(qualified_stocks)} stocks):")
                        print("=" * 60)
                        for stock in qualified_stocks:
                            print(f"   📊 {stock['symbol']:8s} | OI: +{stock['oi_change']:6.2f}%")
                        return True
                    else:
                        print("\n❌ No stocks qualified with OI >= 7%")
                        return False
                        
                else:
                    print("❌ OI data file not found")
                    return False
                    
            else:
                print("❌ OI scraping failed")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Error in Step 4: {e}")
            return False
    
    def save_final_results(self):
        """Save final trading results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trading_strategy_results_{timestamp}.json"
        
        results = {
            "execution_info": {
                "timestamp": datetime.now().isoformat(),
                "strategy_date": datetime.now().strftime("%Y-%m-%d"),
                "previous_day_target": hf.get_previous_day_close_date()
            },
            "step_results": {
                "step1_previous_closes": len(self.previous_day_closes),
                "step2_movers_920": len(self.movers_920),
                "step3_momentum_925": len(self.momentum_925),
                "step4_final_candidates": len(self.final_candidates)
            },
            "final_trading_candidates": self.final_candidates,
            "conversion_rates": {
                "step1_to_step2": (len(self.movers_920) / len(self.previous_day_closes) * 100) if self.previous_day_closes else 0,
                "step2_to_step3": (len(self.momentum_925) / len(self.movers_920) * 100) if self.movers_920 else 0,
                "step3_to_step4": (len(self.final_candidates) / len(self.momentum_925) * 100) if self.momentum_925 else 0,
                "overall_success": (len(self.final_candidates) / len(self.previous_day_closes) * 100) if self.previous_day_closes else 0
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Final results saved to: {filename}")
        return filename
    
    def run_complete_strategy(self) -> bool:
        """Run the complete trading strategy"""
        print("🚀 TRADING STRATEGY ORCHESTRATOR")
        print("=" * 80)
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
        print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 80)
        
        try:
            # Step 1: Get previous day closes
            if not self.step1_get_previous_day_closes():
                print("❌ Strategy failed at Step 1")
                return False
            
            # Step 2: Find 2% movers at 9:20
            if not self.step2_find_2_percent_movers_at_920():
                print("❌ Strategy failed at Step 2")
                return False
            
            # Step 3: Check momentum at 9:25
            if not self.step3_check_momentum_at_925():
                print("❌ Strategy failed at Step 3")
                return False
            
            # Step 4: Filter by OI
            if not self.step4_get_oi_data():
                print("❌ Strategy failed at Step 4")
                return False
            
            # Save final results
            self.save_final_results()
            
            print("\n🎉 STRATEGY EXECUTION COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            
            # Display comprehensive results
            print(f"\n📊 COMPLETE STRATEGY RESULTS:")
            print("-" * 50)
            print(f"📈 Total stocks analyzed:     {len(self.previous_day_closes)}")
            print(f"🎯 2% movers (9:20 AM):       {len(self.movers_920)}")
            print(f"⚡ Momentum maintained (9:25): {len(self.momentum_925)}")
            print(f"💎 Final OI qualified:        {len(self.final_candidates)}")
            
            if len(self.previous_day_closes) > 0:
                success_rate = (len(self.final_candidates) / len(self.previous_day_closes)) * 100
                momentum_rate = (len(self.momentum_925) / len(self.movers_920)) * 100 if self.movers_920 else 0
                print(f"📈 Overall success rate:      {success_rate:.2f}%")
                print(f"⚡ Momentum retention rate:   {momentum_rate:.2f}%")
            
            if self.final_candidates:
                print(f"\n🎯 FINAL TRADING CANDIDATES ({len(self.final_candidates)} stocks):")
                print("=" * 60)
                for i, stock in enumerate(self.final_candidates, 1):
                    symbol = stock['symbol'] if isinstance(stock, dict) else stock
                    oi_change = f" | OI: +{stock['oi_change']:.2f}%" if isinstance(stock, dict) else ""
                    print(f"   {i:2d}. 💎 {symbol:8s}{oi_change}")
                
                print("\n📋 NEXT STEPS:")
                print("-" * 30)
                print("   1. 📊 Monitor these stocks for breakout/breakdown signals")
                print("   2. 🎯 Execute options trades based on direction")
                print("   3. 🛡️  Set appropriate stop losses and targets")
                print("   4. ⏰ Watch for volume and price action confirmation")
            else:
                print("\n⚠️  NO FINAL CANDIDATES FOUND")
                print("   Consider adjusting strategy parameters or waiting for different market conditions")
            
            return True
            
        except Exception as e:
            print(f"❌ Strategy execution failed: {e}")
            return False
        
        finally:
            # Cleanup WebSocket connections
            cleanup()
            print("\n🧹 Cleaned up connections")

def main():
    """Main entry point"""
    orchestrator = TradingStrategyOrchestrator()
    success = orchestrator.run_complete_strategy()
    
    if success:
        print("\n✅ Trading strategy execution completed!")
    else:
        print("\n❌ Trading strategy execution failed!")

if __name__ == "__main__":
    main()