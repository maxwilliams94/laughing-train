"""
Tests for Coinbase connectivity verification.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from exchanges.coinbase import verify_coinbase_connection


class TestVerifyCoinbaseConnection:
    """Test the verify_coinbase_connection function."""
    
    def test_successful_verification(self, mock_requests_get: Mock, mock_authenticator: Mock) -> None:
        """Test successful connection verification."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "accounts": [
                {
                    "uuid": "account-1",
                    "currency": "USD",
                    "available_balance": {
                        "value": "1000.00",
                        "currency": "USD"
                    }
                },
                {
                    "uuid": "account-2",
                    "currency": "BTC",
                    "available_balance": {
                        "value": "0.5",
                        "currency": "BTC"
                    }
                }
            ],
            "has_next": False
        }
        mock_requests_get.return_value = mock_response
        
        result = verify_coinbase_connection()
        
        # Check request was made correctly
        mock_requests_get.assert_called_once()
        call_args = mock_requests_get.call_args
        
        # Check URL
        assert call_args[0][0] == "https://api.coinbase.com/api/v3/brokerage/accounts"
        
        # Check result - returns balances dict (currency -> formatted balance)
        assert "USD" in result
        assert "BTC" in result
        assert result["USD"] == "1000.00 USD"
        assert result["BTC"] == "0.5 BTC"
    
    def test_custom_api_base_url(self, mock_requests_get: Mock, mock_authenticator: Mock) -> None:
        """Test using custom API base URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"accounts": [], "has_next": False}
        mock_requests_get.return_value = mock_response
        
        verify_coinbase_connection(api_base_url="https://sandbox.coinbase.com")
        
        # Check URL uses custom base
        call_args = mock_requests_get.call_args
        assert call_args[0][0] == "https://sandbox.coinbase.com/api/v3/brokerage/accounts"
    
    def test_http_error(self, mock_requests_get: Mock, mock_authenticator: Mock) -> None:
        """Test handling of HTTP errors."""
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        mock_requests_get.return_value = mock_response
        
        with pytest.raises(requests.HTTPError):
            verify_coinbase_connection()
    
    def test_empty_accounts(self, mock_requests_get: Mock, mock_authenticator: Mock) -> None:
        """Test handling of empty accounts list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"accounts": [], "has_next": False}
        mock_requests_get.return_value = mock_response
        
        result = verify_coinbase_connection()
        
        # Result should be empty dict when no accounts
        assert result == {}
    
    def test_authenticator_headers_used(self, mock_requests_get: Mock, mock_authenticator: Mock) -> None:
        """Test that authenticator headers are used in request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"accounts": [], "has_next": False}
        mock_requests_get.return_value = mock_response
        
        verify_coinbase_connection()
        
        # Check headers were passed to request
        call_args = mock_requests_get.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"


@pytest.fixture
def mock_requests_get() -> Mock:
    """Mock the requests.get function."""
    with patch('requests.get') as mock_get:
        yield mock_get


@pytest.fixture
def mock_authenticator() -> Mock:
    """Mock the authenticator singleton."""
    with patch('exchanges.coinbase.get_coinbase_authenticator') as mock_get_auth:
        mock_auth = Mock()
        mock_auth.get_auth_headers.return_value = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json"
        }
        mock_get_auth.return_value = mock_auth
        yield mock_auth
