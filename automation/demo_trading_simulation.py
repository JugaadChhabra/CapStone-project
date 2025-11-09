#!/usr/bin/env python3
"""
Demo Trading Simulation - Aggressive Version

PURPOSE: Demonstrates trading simulation with more aggressive parameters to ensure trades are generated
This version uses lower thresholds to generate more trading activity for demonstration purposes.
"""

from improved_trading_simulation import ImprovedTradingSimulator
import pandas as pd
import logging
from typing import Tuple, Dict, Any
from trading_config import MAX_POSITIONS

class DemoTradingSimulator(ImprovedTradingSimulator):
    """Demo version with more aggressive trading parameters"""
    
    def __init__(self, initial_capital: float = 500000):
        super().__init__(initial_capital)
        
        # More aggressive trading parameters for demo
        self.min_momentum_threshold = 0.5  # Lower threshold (was 1.5%)
        self.min_volume_ratio = 1.0  # Lower threshold (was 1.2x)
        self.max_rsi_buy = 80  # Higher threshold (was 70)
        self.min_rsi_sell = 20  # Lower threshold (was 30)
        self.trailing_stop_pct = 2.0  # Wider trailing stop (was 1.5%)
        
        self.logger.info("🎯 Demo mode: Using aggressive trading parameters")
        self.logger.info(f"   Min momentum: {self.min_momentum_threshold}% (lowered)")
        self.logger.info(f"   Min volume ratio: {self.min_volume_ratio}x (lowered)")
        self.logger.info(f"   RSI limits: {self.min_rsi_sell}-{self.max_rsi_buy} (widened)")
    
    def should_enter_position(self, symbol: str, current_data: pd.DataFrame) -> Tuple[bool, str, Dict[str, Any]]:
        """More aggressive entry conditions for demo"""
        # Check basic constraints
        if symbol in self.positions:
            return False, "Already in position", {}
        
        if len(self.positions) >= MAX_POSITIONS:
            return False, "Maximum positions reached", {}
        
        # Analyze signals
        signals = self.analyze_entry_signals(current_data)
        
        # Check if we have enough capital
        position_size = min(100000, self.current_capital * 0.15)  # Fixed position size for demo
        if position_size < 1000:  # Minimum ₹1000 per trade
            return False, "Insufficient capital", signals
        
        # More aggressive entry criteria for LONG position
        long_entry = (
            signals['momentum_score'] > self.min_momentum_threshold and  # Very low momentum requirement
            signals['volume_score'] > self.min_volume_ratio and  # Low volume requirement
            signals['rsi'] < self.max_rsi_buy and  # Wide RSI range
            signals['price_change_1'] > -5.0  # Allow larger daily drops
        )
        
        # More aggressive entry criteria for SHORT position  
        short_entry = (
            signals['momentum_score'] < -self.min_momentum_threshold and  # Very low momentum requirement
            signals['volume_score'] > self.min_volume_ratio and  # Low volume requirement
            signals['rsi'] > self.min_rsi_sell and  # Wide RSI range
            signals['price_change_1'] < 5.0  # Allow larger daily gains
        )
        
        # Also add some random trades for demo (10% chance)
        import random
        if random.random() < 0.1 and len(current_data) >= 10:  # 10% chance of random trade
            if random.random() < 0.5:
                reason = f"DEMO LONG: Random entry for demonstration"
                return True, reason, signals
            else:
                reason = f"DEMO SHORT: Random entry for demonstration"
                return True, reason, signals
        
        if long_entry:
            reason = f"LONG: Momentum={signals['momentum_score']:.2f}%, Volume={signals['volume_score']:.2f}x, RSI={signals['rsi']:.1f}"
            return True, reason, signals
        elif short_entry:
            reason = f"SHORT: Momentum={signals['momentum_score']:.2f}%, Volume={signals['volume_score']:.2f}x, RSI={signals['rsi']:.1f}"
            return True, reason, signals
        else:
            reason = f"No entry: Mom={signals['momentum_score']:.1f}%, Vol={signals['volume_score']:.1f}x, RSI={signals['rsi']:.1f}"
            return False, reason, signals

def main():
    """Main function to run the demo trading simulation"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        print("🚀 Starting DEMO Trading Simulation")
        print("=" * 50)
        print("This demo uses aggressive parameters to ensure trading activity")
        print("In real trading, use more conservative thresholds!")
        print("=" * 50)
        
        # Initialize demo simulator
        simulator = DemoTradingSimulator(initial_capital=500000)
        
        # Run simulation (limit to 3 days for testing)
        simulator.run_simulation(max_days=3)
        
        print("\n" + "=" * 50)
        print("📋 DEMO COMPLETED")
        print("=" * 50)
        print("This demo showed:")
        print("1. Different entry/exit logic")
        print("2. Detailed trade reasoning")
        print("3. Risk management (stop loss, take profit, trailing stops)")
        print("4. Position sizing based on volatility")
        print("5. Comprehensive trade ledger")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()