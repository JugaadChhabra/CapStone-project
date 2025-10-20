import json
import pandas as pd
from datetime import datetime, time
from typing import Dict, List, Tuple, Optional
import os
import subprocess
import time as time_module
from scraping import scrape_for_oi

class EnhancedTradingStrategyBacktest:
    """
    Enhanced backtesting version with OI filtering and breakout/breakdown detection
    """
    
    def __init__(self, previous_closes_file: str, ohlc_data_file: str):
        """
        Initialize enhanced backtest with historical data files
        
        Args:
            previous_closes_file: Path to previous day closes JSON file
            ohlc_data_file: Path to OHLC data JSON file with 5-minute intervals
        """
        self.previous_closes_file = previous_closes_file
        self.ohlc_data_file = ohlc_data_file
        self.previous_closes = {}
        self.ohlc_data = {}
        self.stock_data = []
        
        # Strategy results storage
        self.movers_920 = []
        self.momentum_925 = []
        self.oi_qualified = []
        self.final_signals = []
        
        # 9:25 candle data for breakout detection
        self.candle_925_data = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load all required data files"""
        try:
            # Load previous day closes
            with open(self.previous_closes_file, 'r') as f:
                prev_data = json.load(f)
                self.previous_closes = prev_data.get('previous_closes', {})
                print(f"📊 Loaded previous closes for {len(self.previous_closes)} stocks")
            
            # Load OHLC data
            with open(self.ohlc_data_file, 'r') as f:
                ohlc_data = json.load(f)
                self.ohlc_data = ohlc_data.get('stocks', {})
                self.collection_info = ohlc_data.get('collection_info', {})
                print(f"📊 Loaded OHLC data for {len(self.ohlc_data)} stocks")
            
            # Load stock CSV data
            self._load_stock_symbols()
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            raise
    
    def _load_stock_symbols(self):
        """Load stock symbols from CSV file"""
        try:
            csv_file = "stock_names_symbol.csv"
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file, header=None, names=['company_name', 'symbol', 'token'])
                
                for _, row in df.iterrows():
                    symbol = str(row['symbol']).strip()
                    token = str(row['token']).strip()
                    
                    if symbol and token and token != 'nan':
                        self.stock_data.append({
                            'symbol': symbol,
                            'token': token
                        })
                        
                print(f"📋 Loaded {len(self.stock_data)} stock symbols from CSV")
            
        except Exception as e:
            print(f"⚠️  Error loading CSV: {e}")
    
    def get_price_at_time(self, symbol: str, target_time: str) -> Optional[Dict]:
        """Get stock price data at a specific time"""
        if symbol not in self.ohlc_data:
            return None
        
        stock_data = self.ohlc_data[symbol]
        if not stock_data:
            return None
        
        target_hour, target_minute = map(int, target_time.split(':'))
        closest_entry = None
        min_time_diff = float('inf')
        
        for entry in stock_data:
            try:
                datetime_str = entry['datetime']
                entry_datetime = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                entry_time = entry_datetime.time()
                
                entry_minutes = entry_time.hour * 60 + entry_time.minute
                target_minutes = target_hour * 60 + target_minute
                time_diff = abs(entry_minutes - target_minutes)
                
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_entry = entry
                    
            except Exception:
                continue
        
        return closest_entry
    
    def get_candles_after_time(self, symbol: str, after_time: str) -> List[Dict]:
        """Get all 5-minute candles after a specific time"""
        if symbol not in self.ohlc_data:
            return []
        
        stock_data = self.ohlc_data[symbol]
        after_hour, after_minute = map(int, after_time.split(':'))
        after_minutes = after_hour * 60 + after_minute
        
        later_candles = []
        
        for entry in stock_data:
            try:
                datetime_str = entry['datetime']
                entry_datetime = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                entry_time = entry_datetime.time()
                
                entry_minutes = entry_time.hour * 60 + entry_time.minute
                
                if entry_minutes > after_minutes:
                    later_candles.append(entry)
                    
            except Exception:
                continue
        
        return sorted(later_candles, key=lambda x: x['datetime'])
    
    def calculate_percentage_change(self, current_price: float, previous_close: float) -> float:
        """Calculate percentage change from previous day close"""
        if previous_close > 0:
            return ((current_price - previous_close) / previous_close) * 100
        return 0
    
    def find_2_percent_movers_at_920(self) -> List[Dict]:
        """Step 1: Find stocks with 2%+ movement at 9:20 AM"""
        movers = []
        
        print("\n🎯 STEP 1: Finding 2%+ movers at 9:20 AM")
        print("=" * 80)
        
        for symbol in self.previous_closes:
            price_data_920 = self.get_price_at_time(symbol, "09:20")
            
            if price_data_920:
                previous_close = self.previous_closes[symbol]
                current_price = price_data_920['close']
                
                percentage_change = self.calculate_percentage_change(current_price, previous_close)
                
                if abs(percentage_change) >= 2.0:
                    mover_data = {
                        'symbol': symbol,
                        'previous_close': previous_close,
                        'price_920': current_price,
                        'percentage_920': percentage_change,
                        'direction': 'positive' if percentage_change > 0 else 'negative'
                    }
                    movers.append(mover_data)
                    
                    direction = "📈" if percentage_change >= 0 else "📉"
                    print(f"   {direction} {symbol:8s}: {percentage_change:+6.2f}% | ₹{previous_close:8.2f} → ₹{current_price:8.2f}")
        
        self.movers_920 = movers
        print(f"\n✅ Step 1 Complete: {len(movers)} stocks with 2%+ movement")
        return movers
    
    def check_momentum_at_925(self) -> List[Dict]:
        """Step 2: Check momentum maintenance at 9:25 AM"""
        maintained = []
        
        if not self.movers_920:
            print("⚠️  No 9:20 movers found. Run step 1 first.")
            return maintained
        
        print("\n🎯 STEP 2: Checking momentum at 9:25 AM")
        print("=" * 80)
        
        for mover in self.movers_920:
            symbol = mover['symbol']
            price_data_925 = self.get_price_at_time(symbol, "09:25")
            
            if price_data_925:
                previous_close = mover['previous_close']
                price_925 = price_data_925['close']
                percentage_925 = self.calculate_percentage_change(price_925, previous_close)
                
                original_percentage = mover['percentage_920']
                
                # Check momentum maintenance (50%+ retained)
                momentum_maintained = False
                if original_percentage > 0:  # Positive at 9:20
                    if percentage_925 >= (original_percentage * 0.5):
                        momentum_maintained = True
                else:  # Negative at 9:20
                    if percentage_925 <= (original_percentage * 0.5):
                        momentum_maintained = True
                
                if momentum_maintained:
                    maintained_data = {
                        **mover,
                        'price_925': price_925,
                        'percentage_925': percentage_925,
                        'candle_925_high': price_data_925['high'],
                        'candle_925_low': price_data_925['low'],
                        'momentum_retention': (percentage_925 / original_percentage) * 100 if original_percentage != 0 else 0
                    }
                    maintained.append(maintained_data)
                    
                    # Store 9:25 candle data for breakout detection
                    self.candle_925_data[symbol] = {
                        'high': price_data_925['high'],
                        'low': price_data_925['low'],
                        'close': price_925
                    }
                    
                    retention = (percentage_925 / original_percentage) * 100 if original_percentage != 0 else 0
                    print(f"   ✅ {symbol:8s}: {original_percentage:+6.2f}% → {percentage_925:+6.2f}% | Retention: {retention:5.1f}%")
        
        self.momentum_925 = maintained
        print(f"\n✅ Step 2 Complete: {len(maintained)} stocks maintained momentum")
        return maintained
    
    def scrape_oi_data(self) -> pd.DataFrame:
        """Scrape OI data from Trendlyne (simulated for backtest)"""
        print("\n🔍 STEP 3A: Checking OI data...")
        
        # For backtesting, we'll use the existing CSV file
        # In live trading, this would call scrape_for_oi() multiple times
        try:
            if os.path.exists("oi_gainers_trendlyne.csv"):
                df = pd.read_csv("oi_gainers_trendlyne.csv")
                print(f"📊 Loaded OI data for {len(df)} stocks")
                return df
            else:
                print("⚠️  OI CSV file not found. Creating empty dataframe.")
                return pd.DataFrame(columns=['Symbol', 'OI Chg%'])
                
        except Exception as e:
            print(f"❌ Error loading OI data: {e}")
            return pd.DataFrame(columns=['Symbol', 'OI Chg%'])
    
    def filter_by_oi_change(self, min_oi_change: float = 7.0) -> List[Dict]:
        """Step 3A: Filter stocks by OI change >= 7%"""
        
        if not self.momentum_925:
            print("⚠️  No momentum stocks found. Run step 2 first.")
            return []
        
        # Get OI data
        oi_df = self.scrape_oi_data()
        
        qualified = []
        
        print(f"\n🎯 STEP 3A: Filtering by OI Change >= {min_oi_change}%")
        print("=" * 80)
        
        for stock in self.momentum_925:
            symbol = stock['symbol']
            
            # Check if stock is in OI data
            oi_row = oi_df[oi_df['Symbol'].str.upper() == symbol.upper()]
            
            if not oi_row.empty:
                try:
                    # Extract OI change percentage
                    oi_change_str = oi_row.iloc[0]['OI Chg%']
                    oi_change = float(oi_change_str.replace('%', ''))
                    
                    if oi_change >= min_oi_change:
                        qualified_stock = {
                            **stock,
                            'oi_change': oi_change
                        }
                        qualified.append(qualified_stock)
                        
                        direction = "📈" if stock['direction'] == 'positive' else "📉"
                        print(f"   ✅ {symbol:8s}: OI +{oi_change:5.2f}% | {stock['percentage_925']:+6.2f}% {direction}")
                    else:
                        print(f"   ❌ {symbol:8s}: OI +{oi_change:5.2f}% | Below {min_oi_change}% threshold")
                        
                except Exception as e:
                    print(f"   ⚠️  {symbol:8s}: Error parsing OI data - {e}")
            else:
                print(f"   ❌ {symbol:8s}: Not found in OI data")
        
        self.oi_qualified = qualified
        print(f"\n✅ Step 3A Complete: {len(qualified)} stocks qualified with OI >= {min_oi_change}%")
        return qualified
    
    def detect_breakouts_breakdowns(self) -> List[Dict]:
        """Step 3B: Detect breakouts (above 9:25 high) and breakdowns (below 9:25 low)"""
        
        if not self.oi_qualified:
            print("⚠️  No OI qualified stocks found. Run step 3A first.")
            return []
        
        signals = []
        
        print(f"\n🎯 STEP 3B: Detecting Breakouts/Breakdowns")
        print("=" * 80)
        
        for stock in self.oi_qualified:
            symbol = stock['symbol']
            direction = stock['direction']
            
            # Get all 5-minute candles after 9:25
            candles_after_925 = self.get_candles_after_time(symbol, "09:25")
            
            if not candles_after_925:
                print(f"   ⚠️  {symbol:8s}: No candles found after 9:25")
                continue
            
            # Get 9:25 candle reference levels
            candle_925_high = stock['candle_925_high']
            candle_925_low = stock['candle_925_low']
            
            # Check each subsequent candle for breakout/breakdown
            signal_generated = False
            
            for candle in candles_after_925:
                candle_time = datetime.fromisoformat(candle['datetime'].replace('Z', '+00:00')).time()
                candle_close = candle['close']
                candle_high = candle['high']
                candle_low = candle['low']
                
                # For positive movers: Look for breakout above 9:25 high
                if direction == 'positive' and candle_close > candle_925_high:
                    signal = {
                        **stock,
                        'signal_type': 'CALL',
                        'signal_time': candle_time.strftime('%H:%M:%S'),
                        'signal_price': candle_close,
                        'trigger_level': candle_925_high,
                        'reference_candle': '9:25 High',
                        'breakout_strength': ((candle_close - candle_925_high) / candle_925_high) * 100
                    }
                    signals.append(signal)
                    
                    print(f"   🟢 {symbol:8s} CALL | {candle_time.strftime('%H:%M')} | ₹{candle_close:.2f} > ₹{candle_925_high:.2f} (9:25H)")
                    signal_generated = True
                    break
                
                # For negative movers: Look for breakdown below 9:25 low
                elif direction == 'negative' and candle_close < candle_925_low:
                    signal = {
                        **stock,
                        'signal_type': 'PUT',
                        'signal_time': candle_time.strftime('%H:%M:%S'),
                        'signal_price': candle_close,
                        'trigger_level': candle_925_low,
                        'reference_candle': '9:25 Low',
                        'breakdown_strength': ((candle_925_low - candle_close) / candle_925_low) * 100
                    }
                    signals.append(signal)
                    
                    print(f"   🔴 {symbol:8s} PUT  | {candle_time.strftime('%H:%M')} | ₹{candle_close:.2f} < ₹{candle_925_low:.2f} (9:25L)")
                    signal_generated = True
                    break
            
            if not signal_generated:
                status = f"Above {candle_925_high:.2f}" if direction == 'positive' else f"Above {candle_925_low:.2f}"
                print(f"   ⏳ {symbol:8s}: No signal | Waiting for breakout/breakdown")
        
        self.final_signals = signals
        print(f"\n✅ Step 3B Complete: {len(signals)} trading signals generated")
        return signals
    
    def run_enhanced_backtest(self) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """Run the complete enhanced backtesting strategy"""
        
        print("🚀 Enhanced Trading Strategy Backtest")
        print("=" * 80)
        print(f"📅 Testing Date: {self.collection_info.get('date_range', 'Unknown')}")
        
        # Step 1: Find 2% movers at 9:20
        movers_920 = self.find_2_percent_movers_at_920()
        
        # Step 2: Check momentum at 9:25
        momentum_925 = self.check_momentum_at_925()
        
        # Step 3A: Filter by OI change
        oi_qualified = self.filter_by_oi_change(min_oi_change=7.0)
        
        # Step 3B: Detect breakouts/breakdowns
        final_signals = self.detect_breakouts_breakdowns()
        
        # Summary
        print("\n📋 ENHANCED BACKTEST SUMMARY")
        print("=" * 80)
        print(f"🎯 Step 1 - 9:20 AM 2%+ Movers: {len(movers_920)}")
        print(f"⚡ Step 2 - 9:25 AM Momentum: {len(momentum_925)}")
        print(f"📊 Step 3A - OI >= 7%: {len(oi_qualified)}")
        print(f"🎪 Step 3B - Final Signals: {len(final_signals)}")
        
        if final_signals:
            print(f"\n🏆 FINAL TRADING SIGNALS:")
            print("=" * 80)
            calls = [s for s in final_signals if s['signal_type'] == 'CALL']
            puts = [s for s in final_signals if s['signal_type'] == 'PUT']
            
            print(f"📞 CALL Signals: {len(calls)}")
            for signal in calls:
                strength = signal.get('breakout_strength', 0)
                print(f"   🟢 {signal['symbol']:8s} | {signal['signal_time']} | ₹{signal['signal_price']:.2f} | +{strength:.2f}%")
            
            print(f"\n📉 PUT Signals: {len(puts)}")  
            for signal in puts:
                strength = signal.get('breakdown_strength', 0)
                print(f"   🔴 {signal['symbol']:8s} | {signal['signal_time']} | ₹{signal['signal_price']:.2f} | -{strength:.2f}%")
        
        return movers_920, momentum_925, oi_qualified, final_signals

def main():
    """Main function to run the enhanced backtest"""
    
    previous_closes_file = "test_folder/previous_day_closes_20251019_192152.json"
    ohlc_data_file = "test_folder/latest_ohlc_data.json"
    
    try:
        # Initialize enhanced backtest
        backtest = EnhancedTradingStrategyBacktest(previous_closes_file, ohlc_data_file)
        
        # Run the enhanced strategy
        movers_920, momentum_925, oi_qualified, final_signals = backtest.run_enhanced_backtest()
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"enhanced_backtest_results_{timestamp}.json"
        
        results = {
            "summary": {
                "step1_movers_920": len(movers_920),
                "step2_momentum_925": len(momentum_925),
                "step3a_oi_qualified": len(oi_qualified),
                "step3b_final_signals": len(final_signals)
            },
            "final_signals": final_signals
        }
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {results_file}")
        print("✅ Enhanced backtest completed successfully!")
        
        return results
        
    except Exception as e:
        print(f"❌ Enhanced backtest failed: {e}")
        return None

if __name__ == "__main__":
    main()