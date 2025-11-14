"""
Tests for Coinbase order placement functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from exchanges.coinbase import place_order

from typing import Any, Tuple


class TestPlaceOrder:
    """Test the place_order function."""
    
    def test_buy_with_cash(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test buying with cash amount (quote_size)."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "success_response": {
                "order_id": "test-order-123",
                "product_id": "BTC-USD",
                "side": "BUY"
            }
        }
        mock_requests.return_value = mock_response  # noqa: F841
        
        # Call place_order with close_price for limit order
        result = place_order("BTC-USD", "buy", "cash", 100.0, close_price=50000.0)
        
        # Verify request was made correctly
        mock_requests.assert_called_once()
        call_args = mock_requests.call_args
        
        # Check URL
        assert call_args[0][0] == "https://api.coinbase.com/api/v3/brokerage/orders"
        
        # Check request body
        request_body = call_args[1]["json"]
        assert request_body["product_id"] == "BTC-USD"
        assert request_body["side"] == "BUY"
        assert "limit_limit_gtc" in request_body["order_configuration"]
        assert request_body["order_configuration"]["limit_limit_gtc"]["quote_size"] == "100"  # Trailing zeros stripped
        assert request_body["order_configuration"]["limit_limit_gtc"]["limit_price"] == "50000"
        assert "base_size" not in request_body["order_configuration"]["limit_limit_gtc"]
        
        # Check result
        assert result["success"] is True
        assert result["success_response"]["order_id"] == "test-order-123"
    
    def test_buy_with_units(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test buying with crypto units (base_size)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "success_response": {
                "order_id": "test-order-456",
                "product_id": "ETH-USD",
                "side": "BUY"
            }
        }
        mock_requests.return_value = mock_response  # noqa: F841
        
        place_order("ETH-USD", "buy", "units", 0.5, close_price=3000.0)
        
        # Check request body
        call_args = mock_requests.call_args
        request_body = call_args[1]["json"]
        assert request_body["product_id"] == "ETH-USD"
        assert request_body["side"] == "BUY"
        assert "limit_limit_gtc" in request_body["order_configuration"]
        assert request_body["order_configuration"]["limit_limit_gtc"]["base_size"] == "0.5"
        assert request_body["order_configuration"]["limit_limit_gtc"]["limit_price"] == "3000"
        assert "quote_size" not in request_body["order_configuration"]["limit_limit_gtc"]
    
    def test_sell_with_units(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test selling with crypto units (base_size)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "success_response": {
                "order_id": "test-order-789",
                "product_id": "BTC-USD",
                "side": "SELL"
            }
        }
        mock_requests.return_value = mock_response  # noqa: F841
        
        place_order("BTC-USD", "sell", "units", 0.001, close_price=50000.0)
        
        # Check request body
        call_args = mock_requests.call_args
        request_body = call_args[1]["json"]
        assert request_body["product_id"] == "BTC-USD"
        assert request_body["side"] == "SELL"
        assert "limit_limit_gtc" in request_body["order_configuration"]
        assert request_body["order_configuration"]["limit_limit_gtc"]["base_size"] == "0.001"
        assert request_body["order_configuration"]["limit_limit_gtc"]["limit_price"] == "50000"
        assert "quote_size" not in request_body["order_configuration"]["limit_limit_gtc"]
    
    def test_sell_with_cash_and_close_price(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test selling with cash amount calculates units from close price."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "success_response": {
                "order_id": "test-order-cash-sell",
                "product_id": "BTC-USD",
                "side": "SELL"
            }
        }
        mock_requests.return_value = mock_response  # noqa: F841
        
        # Sell $100 worth at $50,000/BTC should result in 0.002 BTC
        place_order("BTC-USD", "sell", "cash", 100.0, close_price=50000.0)
        
        # Check request body
        call_args = mock_requests.call_args
        request_body = call_args[1]["json"]
        assert request_body["product_id"] == "BTC-USD"
        assert request_body["side"] == "SELL"
        assert "limit_limit_gtc" in request_body["order_configuration"]
        # Should have calculated 100 / 50000 = 0.002
        assert request_body["order_configuration"]["limit_limit_gtc"]["base_size"] == "0.002"
        assert request_body["order_configuration"]["limit_limit_gtc"]["limit_price"] == "50000"
        assert "quote_size" not in request_body["order_configuration"]["limit_limit_gtc"]
    
    def test_sell_with_cash_requires_close_price(self, mock_authenticator: Mock) -> None:
        """Test that all orders require close_price for limit orders."""
        # All orders now require close_price for limit order functionality
        with pytest.raises(ValueError, match="close_price is required for limit orders"):
            place_order("BTC-USD", "sell", "cash", 100.0)
        
        with pytest.raises(ValueError, match="close_price is required for limit orders"):
            place_order("BTC-USD", "sell", "cash", 100.0, close_price=0)
        
        with pytest.raises(ValueError, match="close_price is required for limit orders"):
            place_order("BTC-USD", "sell", "cash", 100.0, close_price=-1)
    
    def test_invalid_action_raises_error(self, mock_authenticator: Mock) -> None:
        """Test that invalid action raises ValueError."""
        with pytest.raises(ValueError, match="Invalid action: HOLD"):
            place_order("BTC-USD", "hold", "units", 1.0)
    
    def test_invalid_quantity_type_raises_error(self, mock_authenticator: Mock) -> None:
        """Test that invalid quantity_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid quantity_type: dollars"):
            place_order("BTC-USD", "buy", "dollars", 100.0)
    
    def test_api_error_response(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test handling of API error response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error_response": {
                "error": "INSUFFICIENT_FUNDS",
                "message": "Insufficient funds",
                "error_details": "Account balance too low"
            }
        }
        mock_requests.return_value = mock_response  # noqa: F841
        
        with pytest.raises(ValueError, match="Order failed: Insufficient funds"):
            place_order("BTC-USD", "buy", "cash", 10000.0, close_price=50000.0)
    
    def test_http_error(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test handling of HTTP errors."""
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        mock_requests.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            place_order("BTC-USD", "buy", "cash", 100.0, close_price=50000.0)
    
    def test_custom_api_base_url(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test using custom API base URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "success_response": {"order_id": "test-123"}
        }
        mock_requests.return_value = mock_response
        
        place_order("BTC-USD", "buy", "cash", 100.0, close_price=50000.0, api_base_url="https://sandbox.coinbase.com")
        
        # Check URL uses custom base
        call_args = mock_requests.call_args
        assert call_args[0][0] == "https://sandbox.coinbase.com/api/v3/brokerage/orders"
    
    def test_case_insensitive_action(self, mock_requests: Mock, mock_authenticator: Mock, mock_product_precision: Mock) -> None:
        """Test that action is case-insensitive."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "success_response": {"order_id": "test-123"}
        }
        mock_requests.return_value = mock_response
        
        # Test lowercase
        place_order("BTC-USD", "buy", "cash", 100.0, close_price=50000.0)
        call_args = mock_requests.call_args
        assert call_args[1]["json"]["side"] == "BUY"
        
        # Test uppercase
        place_order("BTC-USD", "SELL", "units", 0.1, close_price=50000.0)
        call_args = mock_requests.call_args
        assert call_args[1]["json"]["side"] == "SELL"
        
        # Test mixed case
        place_order("BTC-USD", "BuY", "cash", 50.0, close_price=50000.0)
        call_args = mock_requests.call_args
        assert call_args[1]["json"]["side"] == "BUY"


@pytest.fixture
def mock_requests() -> Any:
    """Mock the requests module."""
    with patch('requests.post') as mock_post:
        yield mock_post


@pytest.fixture
def mock_product_precision() -> Any:
    """Mock the _get_product_precision function to avoid API calls."""
    with patch('exchanges.coinbase._get_product_precision') as mock_precision:
        # Return (base_decimals=8, quote_decimals=2) for BTC-USD and (18, 2) for ETH-USD
        def get_precision(symbol: str, api_base_url: str) -> Tuple[int, int]:
            if "ETH" in symbol:
                return (18, 2)
            return (8, 2)
        mock_precision.side_effect = get_precision
        yield mock_precision


@pytest.fixture
def mock_authenticator() -> Any:
    """Mock the authenticator singleton."""
    with patch('exchanges.coinbase.get_coinbase_authenticator') as mock_get_auth:
        mock_auth = Mock()
        mock_auth.get_auth_headers.return_value = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json"
        }
        mock_get_auth.return_value = mock_auth
        yield mock_auth
