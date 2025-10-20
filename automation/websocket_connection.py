#!/usr/bin/env python3
"""
WebSocket Connection Manager - Centralized WebSocket Logic

PURPOSE: Handles all WebSocket connection, subscription, and data parsing logic
SEPARATES: WebSocket infrastructure from trading strategy logic

FUNCTIONS OVERVIEW:
├── WebSocketManager (Class) -> Main WebSocket connection manager
├── parse_stock_data() -> Parse incoming WebSocket data
├── setup_connection() -> Configure WebSocket event handlers
├── connect() -> Establish WebSocket connection
├── disconnect() -> Clean up connection
├── subscribe_to_codes() -> Subscribe to stock codes
└── get_current_prices() -> Get all received price data

USAGE:
    from websocket_connection import WebSocketManager
    ws_manager = WebSocketManager()
    ws_manager.connect()
    ws_manager.subscribe_to_codes(websocket_codes)
"""

import socketio, threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from icici_functions import (
    get_websocket_session,
    WEBSOCKET_URL
)

class WebSocketManager:
    """Centralized WebSocket connection and data management"""
    
    def __init__(self, data_callback: Optional[Callable] = None):
        """
        Initialize WebSocket manager
        
        Args:
            data_callback: Optional callback function for real-time data processing
        """
        # Connection state
        self._sio = None
        self._session_token = None
        self._user_id = None
        self._is_connected = False
        
        # Data storage
        self._current_prices = {}
        self._connection_lock = threading.Lock()
        
        # Callback for real-time data processing
        self._data_callback = data_callback
        
    def parse_stock_data(self, data) -> Optional[Dict]:
        """
        Parse incoming WebSocket stock data
        
        Args:
            data: Raw WebSocket data array
            
        Returns:
            Parsed stock data dictionary or None if invalid
        """
        if not data or not isinstance(data, list) or len(data) < 12:
            return None
        
        try:
            return {
                "symbol": data[0],
                "open": float(data[1]),
                "price": float(data[2]),
                "high": float(data[3]),
                "low": float(data[4]),
                "change": float(data[5]),
                "volume": data[10],
                "timestamp": datetime.now()
            }
        except (ValueError, IndexError):
            return None
    
    def _setup_event_handlers(self):
        """Setup WebSocket event handlers"""
        
        @self._sio.event
        def connect():
            print("🔗 WebSocket connected successfully!")
            self._is_connected = True
        
        @self._sio.event
        def disconnect():
            print("🔌 WebSocket disconnected")
            self._is_connected = False
        
        @self._sio.on('stock')
        def on_stock_data(data):
            """Handle incoming stock data"""
            parsed = self.parse_stock_data(data)
            if parsed and parsed['symbol']:
                with self._connection_lock:
                    self._current_prices[parsed['symbol']] = parsed
                    
                    # Call external callback if provided
                    if self._data_callback:
                        try:
                            self._data_callback(parsed)
                        except Exception as e:
                            print(f"⚠️  Callback error: {e}")
                    
                    # Log progress
                    if len(self._current_prices) <= 5:
                        print(f"📊 Received: {parsed['symbol']} → ₹{parsed.get('price', 'N/A')} ({parsed.get('change', 'N/A'):+.2f})")
                    elif len(self._current_prices) % 50 == 0:
                        print(f"📊 Progress: {len(self._current_prices)} stocks received...")
    
    def get_websocket_credentials(self) -> bool:
        """
        Get WebSocket session credentials using centralized utility
        
        Returns:
            True if credentials obtained successfully, False otherwise
        """
        self._user_id, self._session_token = get_websocket_session()
        
        if not self._user_id or not self._session_token:
            print("❌ Failed to get WebSocket session credentials")
            return False
        
        print("🔑 WebSocket credentials obtained")
        return True
    
    def connect(self) -> bool:
        """
        Establish WebSocket connection
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._is_connected:
            print("✅ Already connected to WebSocket")
            return True
        
        # Get credentials
        if not self.get_websocket_credentials():
            return False
        
        # Create SocketIO client and setup handlers
        self._sio = socketio.Client()
        self._setup_event_handlers()
        
        try:
            auth = {"user": self._user_id, "token": self._session_token}
            print(f"🔗 Connecting to {WEBSOCKET_URL}...")
            
            self._sio.connect(
                WEBSOCKET_URL,
                headers={"User-Agent": "python-socketio[client]/socket"},
                auth=auth,
                transports="websocket",
                wait_timeout=10
            )
            
            self._is_connected = self._sio.connected
            
            if self._is_connected:
                print("✅ WebSocket connection established")
            else:
                print("❌ WebSocket connection failed")
                
            return self._is_connected
            
        except Exception as e:
            print(f"❌ WebSocket connection error: {e}")
            self._is_connected = False
            return False
    
    def subscribe_to_codes(self, websocket_codes: List[str]) -> bool:
        """
        Subscribe to WebSocket codes for live data
        
        Args:
            websocket_codes: List of WebSocket codes to subscribe to
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self._is_connected or not self._sio:
            print("❌ Not connected to WebSocket")
            return False
        
        print(f"📡 Subscribing to {len(websocket_codes)} stock codes...")
        print(f"📋 Sample codes: {websocket_codes[:5]}...")
        
        try:
            for code in websocket_codes:
                self._sio.emit('join', code)
            
            print(f"✅ Subscription requests sent for {len(websocket_codes)} stocks")
            return True
            
        except Exception as e:
            print(f"❌ Subscription error: {e}")
            return False
    
    def get_current_prices(self) -> Dict:
        """
        Get all current price data
        
        Returns:
            Dictionary of current prices (thread-safe copy)
        """
        with self._connection_lock:
            return self._current_prices.copy()
    
    def get_price_count(self) -> int:
        """
        Get count of received prices
        
        Returns:
            Number of stocks with current price data
        """
        with self._connection_lock:
            return len(self._current_prices)
    
    def clear_prices(self):
        """Clear all stored price data"""
        with self._connection_lock:
            self._current_prices.clear()
            print("🧹 Price data cleared")
    
    def disconnect(self):
        """Clean up WebSocket connection"""
        try:
            if self._sio and self._sio.connected:
                print("🔌 Disconnecting WebSocket...")
                self._sio.disconnect()
            
            self._is_connected = False
            self.clear_prices()
            print("✅ WebSocket cleanup complete")
            
        except Exception as e:
            print(f"⚠️  Disconnect error: {e}")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self._is_connected
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto cleanup"""
        self.disconnect()

# Utility function for backwards compatibility
def get_websocket_codes_for_tokens(tokens: List[str], stock_data: List[Dict]) -> List[str]:
    """
    Get WebSocket codes for specific tokens
    
    Args:
        tokens: List of stock tokens
        stock_data: List of stock information dictionaries
        
    Returns:
        List of corresponding WebSocket codes
    """
    codes = []
    for token in tokens:
        for stock in stock_data:
            if stock.get('token') == token:
                codes.append(stock['websocket_code'])
                break
    return codes

if __name__ == "__main__":
    """Test WebSocket connection"""
    print("🧪 Testing WebSocket Connection Manager")
    print("=" * 50)
    
    # Test connection
    with WebSocketManager() as ws_manager:
        if ws_manager.connect():
            print("✅ Connection test successful")
            
            # Test with sample codes (if available)
            sample_codes = ["4.1!13.0", "4.1!25780.0"]  # Sample WebSocket codes
            ws_manager.subscribe_to_codes(sample_codes)
            
            import time
            print("⏳ Waiting 3 seconds for data...")
            time.sleep(3)
            
            price_count = ws_manager.get_price_count()
            print(f"📊 Received data for {price_count} stocks")
        else:
            print("❌ Connection test failed")
    
    print("=" * 50)
    print("✅ WebSocket test complete!")