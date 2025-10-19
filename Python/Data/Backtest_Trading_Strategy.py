import json
import pandas as pd
from datetime import datetime, time
from typing import Dict, List, Tuple
import os

class TradingStrategyBacktest:
    """
    Backtesting version of the trading strategy using historical data files
    """
    
    def __init__(self, previous_closes_file: str, ohlc_data_file: str):
        """
        Initialize backtest with historical data files
        
        Args:
            previous_closes_file: Path to previous day closes JSON file
            ohlc_data_file: Path to OHLC data JSON file with 5-minute intervals
        """
        self.previous_closes_file = previous_closes_file
        self.ohlc_data_file = ohlc_data_file
        self.previous_closes = {}
        self.ohlc_data = {}
        self.stock_data = []
        
        # Storage for strategy results
        self.movers_920 = []
        self.final_stocks_925 = []
        
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
                print(f"📅 Date range: {self.collection_info.get('date_range', 'Unknown')}")
                print(f"⏰ Interval: {self.collection_info.get('interval', 'Unknown')}")
            
            # Load stock CSV data for symbol mapping
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
            else:
                print("⚠️  CSV file not found, using symbols from data files")
                
        except Exception as e:
            print(f"⚠️  Error loading CSV: {e}")
    
    def get_price_at_time(self, symbol: str, target_time: str) -> Dict:
        """
        Get stock price data at a specific time
        
        Args:
            symbol: Stock symbol
            target_time: Target time in format "HH:MM" (e.g., "09:20")
        
        Returns:
            Dict with price data or None if not found
        """
        if symbol not in self.ohlc_data:
            return None
        
        stock_data = self.ohlc_data[symbol]
        if not stock_data:
            return None
        
        # Convert target time to datetime for comparison
        target_hour, target_minute = map(int, target_time.split(':'))
        
        # Find the closest time entry
        closest_entry = None
        min_time_diff = float('inf')
        
        for entry in stock_data:
            try:
                # Parse the timestamp from the entry
                timestamp_str = entry['timestamp']
                entry_datetime = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                entry_time = entry_datetime.time()
                
                # Calculate time difference in minutes
                entry_minutes = entry_time.hour * 60 + entry_time.minute
                target_minutes = target_hour * 60 + target_minute
                time_diff = abs(entry_minutes - target_minutes)
                
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_entry = entry
                    
            except Exception as e:
                continue
        
        return closest_entry
    
    def calculate_percentage_change(self, current_price: float, previous_close: float) -> float:
        """Calculate percentage change from previous day close"""
        if previous_close > 0:
            return ((current_price - previous_close) / previous_close) * 100
        return 0
    
    def find_2_percent_movers_at_920(self) -> List[Dict]:
        """
        Find stocks with 2%+ movement at 9:20 AM
        
        Returns:
            List of stocks with their 9:20 data
        """
        movers = []
        
        print("\n🔍 Analyzing stocks at 9:20 AM...")
        print("=" * 80)
        
        for symbol in self.previous_closes:
            # Get price at 9:20
            price_data_920 = self.get_price_at_time(symbol, "09:20")
            
            if price_data_920:
                previous_close = self.previous_closes[symbol]
                current_price = price_data_920['close']  # Using close price of the 5-minute candle
                
                percentage_change = self.calculate_percentage_change(current_price, previous_close)
                
                if abs(percentage_change) >= 2.0:
                    mover_data = {
                        'symbol': symbol,
                        'previous_close': previous_close,
                        'price_920': current_price,
                        'percentage_920': percentage_change,
                        'volume_920': price_data_920['volume'],
                        'high_920': price_data_920['high'],
                        'low_920': price_data_920['low']
                    }
                    movers.append(mover_data)
                    
                    direction = "📈" if percentage_change >= 0 else "📉"
                    print(f"   {direction} {symbol:8s}: {percentage_change:+6.2f}% | "
                          f"₹{previous_close:8.2f} → ₹{current_price:8.2f} | Vol: {price_data_920['volume']:,}")
        
        self.movers_920 = movers
        print("=" * 80)
        print(f"🎯 Found {len(movers)} stocks with 2%+ movement at 9:20 AM")
        
        return movers
    
    def check_momentum_at_925(self) -> List[Dict]:
        """
        Check which 9:20 movers maintained momentum at 9:25 AM
        
        Returns:
            List of stocks that maintained momentum
        """
        maintained = []
        
        if not self.movers_920:
            print("⚠️  No 9:20 movers found. Run find_2_percent_movers_at_920() first.")
            return maintained
        
        print("\n⚡ Checking momentum maintenance at 9:25 AM...")
        print("=" * 80)
        
        for mover in self.movers_920:
            symbol = mover['symbol']
            
            # Get price at 9:25
            price_data_925 = self.get_price_at_time(symbol, "09:25")
            
            if price_data_925:
                previous_close = mover['previous_close']
                price_925 = price_data_925['close']
                percentage_925 = self.calculate_percentage_change(price_925, previous_close)
                
                original_percentage = mover['percentage_920']
                
                # Check if momentum is maintained (not retraced more than 50%)
                momentum_maintained = False
                
                if original_percentage > 0:  # Was positive at 9:20
                    if percentage_925 >= (original_percentage * 0.5):
                        momentum_maintained = True
                else:  # Was negative at 9:20
                    if percentage_925 <= (original_percentage * 0.5):
                        momentum_maintained = True
                
                if momentum_maintained:
                    maintained_data = {
                        **mover,  # Include all 9:20 data
                        'price_925': price_925,
                        'percentage_925': percentage_925,
                        'volume_925': price_data_925['volume'],
                        'momentum_retention': (percentage_925 / original_percentage) * 100 if original_percentage != 0 else 0
                    }
                    maintained.append(maintained_data)
                    
                    direction = "📈" if percentage_925 >= 0 else "📉"
                    retention = (percentage_925 / original_percentage) * 100 if original_percentage != 0 else 0
                    
                    print(f"   ✅ {symbol:8s}: {original_percentage:+6.2f}% → {percentage_925:+6.2f}% | "
                          f"Retention: {retention:5.1f}% | Vol: {price_data_925['volume']:,}")
                else:
                    retention = (percentage_925 / original_percentage) * 100 if original_percentage != 0 else 0
                    print(f"   ❌ {symbol:8s}: {original_percentage:+6.2f}% → {percentage_925:+6.2f}% | "
                          f"Retention: {retention:5.1f}% | Lost momentum")
        
        self.final_stocks_925 = maintained
        print("=" * 80)
        print(f"🎯 {len(maintained)} stocks maintained momentum from 9:20 to 9:25")
        
        return maintained
    
    def run_full_backtest(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Run the complete backtesting strategy
        
        Returns:
            Tuple of (9:20 movers, 9:25 maintained stocks)
        """
        print("🚀 Starting Trading Strategy Backtest")
        print("=" * 80)
        print(f"📅 Testing Date: {self.collection_info.get('date_range', 'Unknown')}")
        print(f"📊 Available Stocks: {len(self.previous_closes)}")
        print(f"📈 OHLC Data Points: {len(self.ohlc_data)}")
        
        # Step 1: Find 2% movers at 9:20
        movers_920 = self.find_2_percent_movers_at_920()
        
        # Step 2: Check momentum maintenance at 9:25
        maintained_925 = self.check_momentum_at_925()
        
        # Summary
        print("\n📋 BACKTEST SUMMARY")
        print("=" * 80)
        print(f"🎯 9:20 AM - 2%+ Movers: {len(movers_920)}")
        print(f"⚡ 9:25 AM - Momentum Maintained: {len(maintained_925)}")
        print(f"📈 Success Rate: {(len(maintained_925)/len(movers_920)*100) if movers_920 else 0:.1f}%")
        
        if maintained_925:
            print(f"\n🏆 FINAL TRADING CANDIDATES:")
            print("=" * 80)
            for i, stock in enumerate(maintained_925, 1):
                print(f"   {i:2d}. {stock['symbol']:8s} | "
                      f"9:20: {stock['percentage_920']:+6.2f}% | "
                      f"9:25: {stock['percentage_925']:+6.2f}% | "
                      f"Retention: {stock['momentum_retention']:5.1f}%")
        
        return movers_920, maintained_925
    
    def get_detailed_analysis(self) -> Dict:
        """
        Get detailed analysis of the backtest results
        
        Returns:
            Dictionary with detailed analysis
        """
        if not self.final_stocks_925:
            return {"error": "No final stocks found. Run backtest first."}
        
        analysis = {
            "summary": {
                "total_stocks_analyzed": len(self.previous_closes),
                "movers_at_920": len(self.movers_920),
                "maintained_at_925": len(self.final_stocks_925),
                "success_rate": (len(self.final_stocks_925)/len(self.movers_920)*100) if self.movers_920 else 0
            },
            "final_candidates": []
        }
        
        for stock in self.final_stocks_925:
            candidate = {
                "symbol": stock['symbol'],
                "previous_close": stock['previous_close'],
                "price_920": stock['price_920'],
                "price_925": stock['price_925'],
                "percentage_920": stock['percentage_920'],
                "percentage_925": stock['percentage_925'],
                "momentum_retention": stock['momentum_retention'],
                "volume_920": stock['volume_920'],
                "volume_925": stock['volume_925']
            }
            analysis["final_candidates"].append(candidate)
        
        return analysis

def main():
    """Main function to run the backtest"""
    
    # File paths (adjust these to your actual file locations)
    previous_closes_file = "test_folder/previous_day_closes_20251019_192152.json"
    ohlc_data_file = "test_folder/latest_ohlc_data.json"
    
    try:
        # Initialize backtest
        backtest = TradingStrategyBacktest(previous_closes_file, ohlc_data_file)
        
        # Run the full backtest
        movers_920, maintained_925 = backtest.run_full_backtest()
        
        # Get detailed analysis
        analysis = backtest.get_detailed_analysis()
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"backtest_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")
        print("✅ Backtest completed successfully!")
        
        return analysis
        
    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        return None

if __name__ == "__main__":
    main()