"""
Unit tests for webhook validation module.
"""
from unittest.mock import patch
from typing import Dict, Any

from validate import (
    check_headers,
    validate_payload,
)


class TestCheckHeaders:
    """Test header validation function."""
    
    def test_valid_headers(self):
        """Test validation passes with correct headers."""
        headers = {"content-type": "application/json"}
        
        with patch('validate.ENABLE_IP_WHITELIST', False):
            with patch('validate.ENABLE_CERT_CHECK', False):
                valid, error = check_headers(headers)
                
                assert valid is True
                assert error is None
    
    def test_missing_content_type(self):
        """Test validation fails without content-type."""
        headers: Dict[str, Any] = {}
        
        valid, error = check_headers(headers)
        
        assert valid is False
        assert error is not None
        assert "Content-Type" in error
    
    def test_wrong_content_type(self):
        """Test validation fails with wrong content-type."""
        headers = {"content-type": "text/plain"}
        
        valid, error = check_headers(headers)
        
        assert valid is False
        assert error is not None
        assert "Content-Type" in error
    
    def test_content_type_case_insensitive(self) -> None:
        """Test content-type check is case insensitive."""
        headers = {"content-type": "APPLICATION/JSON; charset=utf-8"}
        
        with patch('validate.ENABLE_IP_WHITELIST', False):
            with patch('validate.ENABLE_CERT_CHECK', False):
                valid, error = check_headers(headers)
                
                assert valid is True
                assert error is None
    
    def test_ip_whitelist_enabled_valid_ip(self):
        """Test IP whitelist allows whitelisted IP."""
        headers = {"content-type": "application/json"}
        
        with patch('validate.ENABLE_IP_WHITELIST', True):
            with patch('validate.ENABLE_CERT_CHECK', False):
                with patch('validate.TRADINGVIEW_ALLOWED_IPS', {"52.89.214.238"}):
                    valid, error = check_headers(headers, client_ip="52.89.214.238")
                    
                    assert valid is True
                    assert error is None
    
    def test_ip_whitelist_enabled_invalid_ip(self):
        """Test IP whitelist rejects non-whitelisted IP."""
        headers = {"content-type": "application/json"}
        
        with patch('validate.ENABLE_IP_WHITELIST', True):
            with patch('validate.ENABLE_CERT_CHECK', False):
                with patch('validate.TRADINGVIEW_ALLOWED_IPS', {"52.89.214.238"}):
                    valid, error = check_headers(headers, client_ip="1.2.3.4")
                    
                    assert valid is False
                    assert error is not None
                    assert "Unauthorized IP address" in error
    
    def test_ip_whitelist_enabled_no_ip(self):
        """Test IP whitelist fails when no IP provided."""
        headers = {"content-type": "application/json"}
        
        with patch('validate.ENABLE_IP_WHITELIST', True):
            with patch('validate.ENABLE_CERT_CHECK', False):
                with patch('validate.TRADINGVIEW_ALLOWED_IPS', {"52.89.214.238"}):
                    valid, error = check_headers(headers, client_ip=None)
                    
                    assert valid is False
                    assert error is not None
                    assert "Unable to verify client IP" in error
    
    def test_cert_check_enabled_valid_cert(self):
        """Test certificate validation with valid cert."""
        headers = {"content-type": "application/json"}
        cert = {
            "C": "US",
            "ST": "Ohio",
            "L": "Westerville",
            "O": "TradingView, Inc.",
            "CN": "webhook-server@tradingview.com"
        }
        
        with patch('validate.ENABLE_IP_WHITELIST', False):
            with patch('validate.ENABLE_CERT_CHECK', True):
                valid, error = check_headers(headers, client_cert=cert)
                
                assert valid is True
                assert error is None
    
    def test_cert_check_enabled_invalid_cert(self):
        """Test certificate validation with invalid cert."""
        headers = {"content-type": "application/json"}
        cert = {
            "C": "US",
            "ST": "Ohio",
            "L": "Westerville",
            "O": "Wrong Company",
            "CN": "webhook-server@tradingview.com"
        }
        
        with patch('validate.ENABLE_IP_WHITELIST', False):
            with patch('validate.ENABLE_CERT_CHECK', True):
                valid, error = check_headers(headers, client_cert=cert)
                
                assert valid is False
                assert error is not None
                assert "Invalid certificate" in error
    
    def test_cert_check_enabled_no_cert(self):
        """Test certificate validation fails when no cert provided."""
        headers = {"content-type": "application/json"}
        
        with patch('validate.ENABLE_IP_WHITELIST', False):
            with patch('validate.ENABLE_CERT_CHECK', True):
                valid, error = check_headers(headers, client_cert=None)
                
                assert valid is False
                assert error is not None
                assert "Client certificate required" in error


class TestValidatePayload:
    """Test payload validation function."""
    
    def test_valid_payload(self):
        """Test validation passes with complete valid payload."""
        payload = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": "100",
            "close": "50000.00"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is True
        assert error is None
    
    def test_missing_required_field(self):
        """Test validation fails when required field is missing."""
        payload = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": "100"
            # Missing 'close'
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "Missing required fields" in error
        assert "close" in error
    
    def test_empty_symbol(self):
        """Test validation fails with empty symbol."""
        payload = {
            "symbol": "",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": "100",
            "close": "50000.00"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "symbol" in error.lower()
    
    def test_invalid_action(self):
        """Test validation fails with invalid action."""
        payload = {
            "symbol": "BTCUSD",
            "action": "hold",  # Invalid
            "quantity_type": "cash",
            "quantity": "100",
            "close": "50000.00"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "action" in error.lower()
    
    def test_valid_actions(self):
        """Test validation passes for both buy and sell."""
        for action in ["buy", "sell"]:
            payload = {
                "symbol": "BTCUSD",
                "action": action,
                "quantity_type": "cash",
                "quantity": "100",
                "close": "50000.00"
            }
            
            valid, _ = validate_payload(payload)
            assert valid is True, f"Failed for action: {action}"
    
    def test_invalid_quantity_type(self):
        """Test validation fails with invalid quantity_type."""
        payload = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "invalid",
            "quantity": "100",
            "close": "50000.00"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "quantity_type" in error.lower()
    
    def test_valid_quantity_types(self):
        """Test validation passes for all valid quantity types."""
        for qty_type in ["cash", "contracts", "percent"]:
            payload = {
                "symbol": "BTCUSD",
                "action": "buy",
                "quantity_type": qty_type,
                "quantity": "100",
                "close": "50000.00"
            }
            
            valid, _ = validate_payload(payload)
            assert valid is True, f"Failed for quantity_type: {qty_type}"
    
    def test_invalid_quantity_format(self):
        """Test validation fails with non-numeric quantity."""
        payload = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": "not-a-number",
            "close": "50000.00"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "quantity" in error.lower()
    
    def test_negative_quantity(self):
        """Test validation fails with negative quantity."""
        payload = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": "-100",
            "close": "50000.00"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "quantity" in error.lower()
        assert "positive" in error.lower()
    
    def test_zero_quantity(self):
        """Test validation fails with zero quantity."""
        payload = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": "0",
            "close": "50000.00"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "quantity" in error.lower()
    
    def test_invalid_close_format(self):
        """Test validation fails with non-numeric close."""
        payload = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": "100",
            "close": "invalid"
        }
        
        valid, error = validate_payload(payload)
        
        assert valid is False
        assert error is not None
        assert "close" in error.lower()
    
    def test_numeric_quantity_as_number(self):
        """Test validation accepts numeric quantity (not string)."""
        payload: Dict[str, Any] = {
            "symbol": "BTCUSD",
            "action": "buy",
            "quantity_type": "cash",
            "quantity": 100,  # Number instead of string
            "close": 50000.00
        }
        
        valid, _ = validate_payload(payload)
        
        assert valid is True
