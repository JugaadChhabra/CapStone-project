#!/usr/bin/env python3
"""
Order Management System - ICICI Direct Order Placement & Management

PURPOSE: Centralized order placement, modification, and tracking for automated trading
FEATURES:
├── Place market/limit orders for stocks and options
├── Modify existing orders (price, quantity, stop loss)
├── Cancel orders
├── Track order status and fills
├── Risk management integration
└── Error handling and retry logic

USAGE:
    from order_management import OrderManager
    order_mgr = OrderManager()
    
    # Place a buy order
    order_id = order_mgr.place_equity_order(
        symbol="RELIANCE", 
        action="buy", 
        quantity=10, 
        price=2500.0
    )
    
    # Check order status
    status = order_mgr.get_order_status(order_id)
"""

import json, hashlib, logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Literal, Union
from dataclasses import dataclass, asdict
from icici_functions import get_env_config, get_session_token

# ICICI Direct API endpoints
ORDER_PLACEMENT_URL = "https://api.icicidirect.com/breezeapi/api/v1/order"
ORDER_STATUS_URL = "https://api.icicidirect.com/breezeapi/api/v1/order"
ORDER_BOOK_URL = "https://api.icicidirect.com/breezeapi/api/v1/orderbook"
ORDER_MODIFY_URL = "https://api.icicidirect.com/breezeapi/api/v1/order"
ORDER_CANCEL_URL = "https://api.icicidirect.com/breezeapi/api/v1/order"

@dataclass
class OrderRequest:
    """Data structure for order requests"""
    symbol: str
    exchange: str  # NSE, BSE, NFO, etc.
    action: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop_loss", "stop_loss_limit"]
    quantity: int
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    product: Literal["cash", "margin", "options", "futures"] = "cash"
    validity: Literal["day", "gtc"] = "day"
    disclosed_quantity: int = 0
    user_remark: str = "AutoTrader"
    
    # Options specific
    expiry_date: Optional[str] = None
    strike_price: Optional[float] = None
    option_type: Optional[Literal["call", "put"]] = None

@dataclass
class OrderResponse:
    """Data structure for order responses"""
    order_id: Optional[str] = None
    status: str = "unknown"
    message: str = ""
    timestamp: datetime = None
    error_code: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class OrderManager:
    """Comprehensive order management system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Get API credentials
        try:
            self.config = get_env_config()
            self.secret_key = self.config['secret_key']
            self.app_key = self.config['app_key']
            self.api_session_token = self.config['session_key']
        except Exception as e:
            self.logger.error(f"Failed to load API credentials: {e}")
            raise
        
        # Order tracking
        self.placed_orders: Dict[str, OrderRequest] = {}
        self.order_responses: Dict[str, OrderResponse] = {}
        
        # Session token (will be refreshed as needed)
        self._session_token = None
        self._session_token_expiry = None
    
    def _get_session_token(self) -> str:
        """Get fresh session token"""
        try:
            # Check if current token is still valid (expires in 24 hours typically)
            if (self._session_token and self._session_token_expiry and 
                datetime.now() < self._session_token_expiry):
                return self._session_token
            
            # Get fresh token
            self._session_token = get_session_token(
                self.secret_key, 
                self.app_key, 
                self.api_session_token
            )
            
            # Set expiry to 23 hours from now (safe margin)
            self._session_token_expiry = datetime.now() + timedelta(hours=23)
            
            self.logger.info("✅ Session token refreshed")
            return self._session_token
            
        except Exception as e:
            self.logger.error(f"Failed to get session token: {e}")
            raise
    
    def _create_checksum(self, payload: str) -> str:
        """Create checksum for API authentication"""
        timestamp = datetime.now(timezone.utc).isoformat()[:19] + '.000Z'
        checksum_string = timestamp + payload + self.secret_key
        checksum = hashlib.sha256(checksum_string.encode("utf-8")).hexdigest()
        return checksum, timestamp
    
    def _create_headers(self, payload: str) -> Dict[str, str]:
        """Create headers for API requests"""
        checksum, timestamp = self._create_checksum(payload)
        session_token = self._get_session_token()
        
        return {
            'Content-Type': 'application/json',
            'X-Checksum': f'token {checksum}',
            'X-Timestamp': timestamp,
            'X-AppKey': self.app_key,
            'X-SessionToken': session_token
        }
    
    def place_equity_order(self, 
                          symbol: str,
                          action: Literal["buy", "sell"],
                          quantity: int,
                          price: Optional[float] = None,
                          order_type: Literal["market", "limit"] = "market",
                          exchange: str = "NSE",
                          stop_loss: Optional[float] = None) -> OrderResponse:
        """
        Place an equity order (stocks)
        
        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS")
            action: "buy" or "sell"
            quantity: Number of shares
            price: Limit price (required for limit orders)
            order_type: "market" or "limit"
            exchange: "NSE" or "BSE"
            stop_loss: Stop loss price (optional)
            
        Returns:
            OrderResponse with order_id if successful
        """
        try:
            # Validate inputs
            if order_type == "limit" and price is None:
                raise ValueError("Price is required for limit orders")
            
            # Create order request
            order_request = OrderRequest(
                symbol=symbol,
                exchange=exchange,
                action=action,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_loss=stop_loss,
                product="cash"
            )
            
            # Build payload
            payload_dict = {
                "stock_code": symbol,
                "exchange_code": exchange,
                "product": "cash",
                "action": action,
                "order_type": order_type,
                "quantity": str(quantity),
                "validity": "day",
                "disclosed_quantity": "0",
                "user_remark": "AutoTrader_Equity"
            }
            
            # Add price for limit orders
            if order_type == "limit" and price:
                payload_dict["price"] = str(price)
            else:
                payload_dict["price"] = "0"  # Market order
            
            # Add stop loss if provided
            if stop_loss:
                payload_dict["stoploss"] = str(stop_loss)
            else:
                payload_dict["stoploss"] = ""
            
            payload = json.dumps(payload_dict, separators=(',', ':'))
            headers = self._create_headers(payload)
            
            # Place order
            self.logger.info(f"📤 Placing {action.upper()} order: {quantity} {symbol} @ {price if price else 'MARKET'}")
            
            import requests
            response = requests.post(ORDER_PLACEMENT_URL, headers=headers, data=payload)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("Status") == "Success":
                order_id = response_data.get("Success", {}).get("order_id")
                
                # Store order details
                self.placed_orders[order_id] = order_request
                order_response = OrderResponse(
                    order_id=order_id,
                    status="placed",
                    message="Order placed successfully"
                )
                self.order_responses[order_id] = order_response
                
                self.logger.info(f"✅ Order placed successfully. Order ID: {order_id}")
                return order_response
                
            else:
                error_msg = response_data.get("Error", "Unknown error")
                self.logger.error(f"❌ Order placement failed: {error_msg}")
                return OrderResponse(
                    status="failed",
                    message=f"Order placement failed: {error_msg}",
                    error_code=str(response.status_code)
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error placing equity order: {e}")
            return OrderResponse(
                status="error",
                message=f"Error placing order: {str(e)}"
            )
    
    def place_options_order(self,
                           symbol: str,
                           strike_price: float,
                           expiry_date: str,  # Format: "2024-10-31"
                           option_type: Literal["call", "put"],
                           action: Literal["buy", "sell"],
                           quantity: int,
                           price: Optional[float] = None,
                           order_type: Literal["market", "limit"] = "market") -> OrderResponse:
        """
        Place an options order
        
        Args:
            symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY")
            strike_price: Strike price
            expiry_date: Expiry date in YYYY-MM-DD format
            option_type: "call" or "put"
            action: "buy" or "sell"
            quantity: Number of lots
            price: Premium price (required for limit orders)
            order_type: "market" or "limit"
            
        Returns:
            OrderResponse with order_id if successful
        """
        try:
            # Format expiry date for API
            expiry_formatted = f"{expiry_date}T06:00:00.000Z"
            
            # Create order request
            order_request = OrderRequest(
                symbol=symbol,
                exchange="NFO",
                action=action,
                order_type=order_type,
                quantity=quantity,
                price=price,
                product="options",
                expiry_date=expiry_formatted,
                strike_price=strike_price,
                option_type=option_type
            )
            
            # Build payload
            payload_dict = {
                "stock_code": symbol,
                "exchange_code": "NFO",
                "product": "options",
                "action": action,
                "order_type": order_type,
                "quantity": str(quantity),
                "validity": "day",
                "stoploss": "",
                "disclosed_quantity": "0",
                "expiry_date": expiry_formatted,
                "right": option_type,
                "strike_price": str(strike_price),
                "user_remark": "AutoTrader_Options"
            }
            
            # Add price for limit orders
            if order_type == "limit" and price:
                payload_dict["price"] = str(price)
            else:
                payload_dict["price"] = "0"  # Market order
            
            payload = json.dumps(payload_dict, separators=(',', ':'))
            headers = self._create_headers(payload)
            
            # Place order
            self.logger.info(f"📤 Placing {action.upper()} options order: {quantity} lots {symbol} {strike_price} {option_type.upper()} @ {price if price else 'MARKET'}")
            
            import requests
            response = requests.post(ORDER_PLACEMENT_URL, headers=headers, data=payload)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("Status") == "Success":
                order_id = response_data.get("Success", {}).get("order_id")
                
                # Store order details
                self.placed_orders[order_id] = order_request
                order_response = OrderResponse(
                    order_id=order_id,
                    status="placed",
                    message="Options order placed successfully"
                )
                self.order_responses[order_id] = order_response
                
                self.logger.info(f"✅ Options order placed successfully. Order ID: {order_id}")
                return order_response
                
            else:
                error_msg = response_data.get("Error", "Unknown error")
                self.logger.error(f"❌ Options order placement failed: {error_msg}")
                return OrderResponse(
                    status="failed",
                    message=f"Options order placement failed: {error_msg}",
                    error_code=str(response.status_code)
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error placing options order: {e}")
            return OrderResponse(
                status="error",
                message=f"Error placing options order: {str(e)}"
            )
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get current status of an order"""
        try:
            payload = json.dumps({
                "order_id": order_id
            }, separators=(',', ':'))
            
            headers = self._create_headers(payload)
            
            import requests
            response = requests.get(ORDER_STATUS_URL, headers=headers, data=payload)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("Status") == "Success":
                return response_data.get("Success")
            else:
                self.logger.error(f"Failed to get order status: {response_data}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting order status: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        try:
            payload = json.dumps({
                "order_id": order_id
            }, separators=(',', ':'))
            
            headers = self._create_headers(payload)
            
            import requests
            response = requests.delete(ORDER_CANCEL_URL, headers=headers, data=payload)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("Status") == "Success":
                self.logger.info(f"✅ Order {order_id} cancelled successfully")
                return True
            else:
                error_msg = response_data.get("Error", "Unknown error")
                self.logger.error(f"❌ Failed to cancel order {order_id}: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_order_book(self) -> List[Dict]:
        """Get all orders for the day"""
        try:
            payload = json.dumps({}, separators=(',', ':'))
            headers = self._create_headers(payload)
            
            import requests
            response = requests.get(ORDER_BOOK_URL, headers=headers, data=payload)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("Status") == "Success":
                return response_data.get("Success", [])
            else:
                self.logger.error(f"Failed to get order book: {response_data}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting order book: {e}")
            return []
    
    def get_placed_orders(self) -> Dict[str, OrderRequest]:
        """Get all orders placed by this manager"""
        return self.placed_orders.copy()
    
    def get_order_responses(self) -> Dict[str, OrderResponse]:
        """Get all order responses"""
        return self.order_responses.copy()

# Convenience functions for easy integration
def create_order_manager() -> OrderManager:
    """Create and return an OrderManager instance"""
    return OrderManager()

def place_stock_buy_order(symbol: str, quantity: int, price: Optional[float] = None) -> OrderResponse:
    """Quick function to place a stock buy order"""
    order_mgr = OrderManager()
    order_type = "limit" if price else "market"
    return order_mgr.place_equity_order(symbol, "buy", quantity, price, order_type)

def place_stock_sell_order(symbol: str, quantity: int, price: Optional[float] = None) -> OrderResponse:
    """Quick function to place a stock sell order"""
    order_mgr = OrderManager()
    order_type = "limit" if price else "market"
    return order_mgr.place_equity_order(symbol, "sell", quantity, price, order_type)