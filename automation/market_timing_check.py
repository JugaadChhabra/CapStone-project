#!/usr/bin/env python3
"""
Market Timing Test Script
Shows different behavior during market hours vs after hours
"""

from datetime import datetime

def check_market_status():
    print("🕐 MARKET TIMING ANALYSIS")
    print("=" * 50)
    
    current_time = datetime.now().time()
    market_open = datetime.now().replace(hour=9, minute=15).time()
    market_close = datetime.now().replace(hour=15, minute=30).time()
    is_market_hours = market_open <= current_time <= market_close
    
    print(f"Current time: {current_time.strftime('%H:%M:%S')}")
    print(f"Market hours: 09:15 AM - 03:30 PM IST")
    print(f"Market status: {'🟢 OPEN' if is_market_hours else '🔴 CLOSED'}")
    
    if is_market_hours:
        print("\n✅ DURING MARKET HOURS:")
        print("- WebSocket live data: Available")
        print("- Historical data API: Available") 
        print("- Options trading system: Fully functional")
        print("- Expected results: Real stock screening")
    else:
        print("\n⚠️  OUTSIDE MARKET HOURS:")
        print("- WebSocket live data: Not available")
        print("- Historical data API: Limited/unavailable")
        print("- Options trading system: Uses fallback dummy data")
        print("- Expected results: No tradeable stocks found")
        
        # Calculate time until next market open
        now = datetime.now()
        tomorrow = now.replace(hour=9, minute=15, second=0, microsecond=0)
        if now.time() >= market_close:
            # Market closed for today, calculate tomorrow
            tomorrow = tomorrow.replace(day=tomorrow.day + 1)
        
        time_diff = tomorrow - now
        hours, remainder = divmod(time_diff.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        
        print(f"\n⏰ Next market open in: {int(hours)}h {int(minutes)}m")
        print(f"Next trading session: {tomorrow.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n🎯 RECOMMENDATIONS:")
    if is_market_hours:
        print("- Run the options trading system now for real results")
        print("- System will connect to live data and find actual movers")
    else:
        print("- Wait for market hours (9:15 AM - 3:30 PM)")
        print("- Current run will use dummy data for testing only")
        print("- No real trading opportunities available")

if __name__ == "__main__":
    check_market_status()