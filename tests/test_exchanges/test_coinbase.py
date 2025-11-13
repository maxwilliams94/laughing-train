"""
Unit tests for Coinbase authentication module.
"""
import pytest
import json
import os
from typing import Any
from unittest.mock import patch

from exchanges.coinbase import (
    CoinbaseCredentials,
    CoinbaseAuthenticator,
    get_coinbase_authenticator
)


class TestCoinbaseCredentials:
    """Test CoinbaseCredentials class."""
    
    def test_init(self):
        """Test basic initialization."""
        creds = CoinbaseCredentials(
            name="test-account",
            api_key="organizations/123/apiKeys/456",
            private_key="-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----\n"
        )
        
        assert creds.name == "test-account"
        assert creds.api_key == "organizations/123/apiKeys/456"
        assert creds.private_key == "-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----\n"
        assert creds.extra == {}
    
    def test_init_with_extra_fields(self):
        """Test initialization with additional fields."""
        creds = CoinbaseCredentials(
            name="test",
            api_key="key123",
            private_key="private",
            extra_field="extra_value",
            another_field=42
        )
        
        assert creds.extra == {"extra_field": "extra_value", "another_field": 42}
    
    def test_from_env_success(self):
        """Test loading credentials from environment variable."""
        test_creds = {
            "name": "env-account",
            "api_key": "organizations/abc/apiKeys/xyz",
            "private_key": "-----BEGIN EC PRIVATE KEY-----\\nkey\\n-----END EC PRIVATE KEY-----\\n"
        }
        
        with patch.dict(os.environ, {"COINBASE_CREDENTIALS": json.dumps(test_creds)}):
            creds = CoinbaseCredentials.from_env()
            
            assert creds.name == "env-account"
            assert creds.api_key == "organizations/abc/apiKeys/xyz"
            # Should unescape newlines
            assert creds.private_key == "-----BEGIN EC PRIVATE KEY-----\nkey\n-----END EC PRIVATE KEY-----\n"
    
    def test_from_env_missing_var(self):
        """Test error when environment variable is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Environment variable 'COINBASE_CREDENTIALS' is not set"):
                CoinbaseCredentials.from_env()
    
    def test_from_env_invalid_json(self):
        """Test error when JSON is invalid."""
        with patch.dict(os.environ, {"COINBASE_CREDENTIALS": "not valid json"}):
            with pytest.raises(ValueError, match="Invalid JSON"):
                CoinbaseCredentials.from_env()
    
    def test_from_env_missing_required_fields(self):
        """Test error when required fields are missing."""
        incomplete_creds = {"name": "test"}
        
        with patch.dict(os.environ, {"COINBASE_CREDENTIALS": json.dumps(incomplete_creds)}):
            with pytest.raises(ValueError, match="Missing required credential fields"):
                CoinbaseCredentials.from_env()
    
    def test_from_env_custom_var_name(self):
        """Test loading from custom environment variable name."""
        test_creds = {
            "name": "custom",
            "api_key": "key",
            "private_key": "private"
        }
        
        with patch.dict(os.environ, {"CUSTOM_VAR": json.dumps(test_creds)}):
            creds = CoinbaseCredentials.from_env("CUSTOM_VAR")
            assert creds.name == "custom"


class TestCoinbaseAuthenticator:
    """Test CoinbaseAuthenticator class."""
    
    @pytest.fixture
    def credentials(self) -> CoinbaseCredentials:
        """Create test credentials."""
        return CoinbaseCredentials(
            name="test-account",
            api_key="organizations/org123/apiKeys/key456",
            private_key="-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIBKHKv0VfCHJG7HqHuMx9wF/NJrT7VHKkXJrOGbXVoK1oAoGCCqGSM49\nAwEHoUQDQgAEJ9bKKqXqLqqKqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq\nqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqg==\n-----END EC PRIVATE KEY-----\n"
        )
    
    @pytest.fixture
    def authenticator(self, credentials: CoinbaseCredentials) -> CoinbaseAuthenticator:
        """Create test authenticator."""
        return CoinbaseAuthenticator(credentials)
    
    def test_init(self, credentials: CoinbaseCredentials) -> None:
        """Test authenticator initialization."""
        auth = CoinbaseAuthenticator(credentials)
        
        assert auth.credentials == credentials
        assert auth._cached_token is None  # type: ignore[misc]
        assert auth._token_expiry == 0.0  # type: ignore[misc]
    
    def test_generate_jwt_structure(self, authenticator: CoinbaseAuthenticator) -> None:
        """Test JWT generation creates valid token structure."""
        with patch('exchanges.coinbase.jwt.encode') as mock_encode:
            mock_encode.return_value = "mock.jwt.token"
            
            token = authenticator.generate_jwt(
                request_method="POST",
                request_host="api.coinbase.com",
                request_path="/api/v3/brokerage/orders"
            )
            
            assert token == "mock.jwt.token"
            assert mock_encode.called
            
            # Check payload structure
            call_args = mock_encode.call_args
            payload: Any = call_args[0][0]
            
            assert payload["iss"] == "cdp"
            assert "nbf" in payload
            assert "exp" in payload
            assert payload["sub"] == "organizations/org123/apiKeys/key456"
            assert payload["uri"] == "POST api.coinbase.com/api/v3/brokerage/orders"
    
    def test_generate_jwt_expiry_limit(self, authenticator: CoinbaseAuthenticator) -> None:
        """Test JWT expiry is limited to 120 seconds."""
        with patch('exchanges.coinbase.jwt.encode') as mock_encode:
            mock_encode.return_value = "token"
            
            # Request 200 seconds, should be capped at 120
            authenticator.generate_jwt(expires_in=200)
            
            payload: Any = mock_encode.call_args[0][0]
            assert payload["exp"] - payload["nbf"] == 120
    
    def test_get_token_caching(self, authenticator: CoinbaseAuthenticator) -> None:
        """Test token caching behavior."""
        with patch.object(authenticator, 'generate_jwt', return_value="new.token") as mock_gen:
            # First call should generate
            token1 = authenticator.get_token()
            assert token1 == "new.token"
            assert mock_gen.call_count == 1
            
            # Second call should use cache
            token2 = authenticator.get_token()
            assert token2 == "new.token"
            assert mock_gen.call_count == 1  # Not called again
    
    def test_get_token_cache_expiry(self, authenticator: CoinbaseAuthenticator) -> None:
        """Test token regeneration when cache expires."""
        with patch.object(authenticator, 'generate_jwt', side_effect=["token1", "token2"]) as mock_gen:
            with patch('exchanges.coinbase.time.time', side_effect=[100.0, 250.0]):  # Second call is past expiry
                token1 = authenticator.get_token()
                assert token1 == "token1"
                
                # Force cache expiry by advancing time
                token2 = authenticator.get_token()
                assert token2 == "token2"
                assert mock_gen.call_count == 2
    
    def test_get_token_no_cache(self, authenticator: CoinbaseAuthenticator) -> None:
        """Test disabling token cache."""
        with patch.object(authenticator, 'generate_jwt', side_effect=["token1", "token2"]) as mock_gen:
            token1 = authenticator.get_token(use_cache=False)
            token2 = authenticator.get_token(use_cache=False)
            
            assert mock_gen.call_count == 2
            assert token1 == "token1"
            assert token2 == "token2"
    
    def test_get_auth_headers(self, authenticator: CoinbaseAuthenticator) -> None:
        """Test HTTP headers generation."""
        with patch.object(authenticator, 'get_token', return_value="test.jwt.token"):
            headers = authenticator.get_auth_headers(
                request_method="GET",
                request_host="api.coinbase.com",
                request_path="/api/v3/brokerage/accounts"
            )
            
            assert headers["Authorization"] == "Bearer test.jwt.token"
            assert headers["Content-Type"] == "application/json"


class TestGetCoinbaseAuthenticator:
    """Test global authenticator getter function."""
    
    def test_singleton_pattern(self) -> None:
        """Test that get_coinbase_authenticator returns same instance."""
        test_creds = {
            "name": "test",
            "api_key": "organizations/123/apiKeys/456",
            "private_key": "-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----\n"
        }
        
        with patch.dict(os.environ, {"COINBASE_CREDENTIALS": json.dumps(test_creds)}):
            # Reset global instance
            import exchanges.coinbase
            exchanges.coinbase._authenticator = None  # type: ignore[attr-defined]
            
            auth1 = get_coinbase_authenticator()
            auth2 = get_coinbase_authenticator()
            
            assert auth1 is auth2
    
    def test_lazy_initialization(self) -> None:
        """Test authenticator is only created when first requested."""
        test_creds = {
            "name": "test",
            "api_key": "key",
            "private_key": "private"
        }
        
        with patch.dict(os.environ, {"COINBASE_CREDENTIALS": json.dumps(test_creds)}):
            # Reset global instance
            import exchanges.coinbase
            exchanges.coinbase._authenticator = None  # type: ignore[attr-defined]
            
            # Should be None initially
            assert exchanges.coinbase._authenticator is None  # type: ignore[attr-defined]
            
            # Gets created on first call
            auth = get_coinbase_authenticator()
            assert exchanges.coinbase._authenticator is not None  # type: ignore[attr-defined]
            assert auth is exchanges.coinbase._authenticator  # type: ignore[attr-defined]
