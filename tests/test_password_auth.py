"""
Tests for password authentication.
"""
import pytest
import os
from unittest.mock import Mock, patch
from function_app import check_password


class TestPasswordAuthentication:
    """Test the password authentication functionality."""
    
    def test_no_password_configured_allows_all(self) -> None:
        """Test that when no password is configured, all requests are allowed."""
        with patch.dict(os.environ, {"WEBHOOK_PASSWORD": ""}):
            # Reload the module to pick up the environment variable
            from importlib import reload
            import function_app
            reload(function_app)
            
            # Create mock request
            req = Mock()
            req.headers = {}
            req.params = {}
            
            valid, error = function_app.check_password(req)
            assert valid is True
            assert error is None
    
    def test_password_in_authorization_header(self) -> None:
        """Test password check with Bearer token in Authorization header."""
        with patch.dict(os.environ, {"WEBHOOK_PASSWORD": "test-secret-123"}):
            from importlib import reload
            import function_app
            reload(function_app)
            
            req = Mock()
            req.headers = {'Authorization': 'Bearer test-secret-123'}
            req.params = {}
            
            valid, error = function_app.check_password(req)
            assert valid is True
            assert error is None
    
    def test_password_in_custom_header(self) -> None:
        """Test password check with custom X-Webhook-Password header."""
        with patch.dict(os.environ, {"WEBHOOK_PASSWORD": "my-password"}):
            from importlib import reload
            import function_app
            reload(function_app)
            
            req = Mock()
            req.headers = {'X-Webhook-Password': 'my-password'}
            req.params = {}
            
            valid, error = function_app.check_password(req)
            assert valid is True
            assert error is None
    
    def test_password_in_query_param(self) -> None:
        """Test password check with query parameter."""
        with patch.dict(os.environ, {"WEBHOOK_PASSWORD": "query-pwd"}):
            from importlib import reload
            import function_app
            reload(function_app)
            
            req = Mock()
            req.headers = {}
            req.params = {'password': 'query-pwd'}
            
            valid, error = function_app.check_password(req)
            assert valid is True
            assert error is None
    
    def test_wrong_password_rejected(self) -> None:
        """Test that wrong password is rejected."""
        with patch.dict(os.environ, {"WEBHOOK_PASSWORD": "correct-password"}):
            from importlib import reload
            import function_app
            reload(function_app)
            
            req = Mock()
            req.headers = {'Authorization': 'Bearer wrong-password'}
            req.params = {}
            
            valid, error = function_app.check_password(req)
            assert valid is False
            assert error == "Unauthorized: Invalid or missing password"
    
    def test_missing_password_rejected(self) -> None:
        """Test that missing password is rejected when password is required."""
        with patch.dict(os.environ, {"WEBHOOK_PASSWORD": "required-password"}):
            from importlib import reload
            import function_app
            reload(function_app)
            
            req = Mock()
            req.headers = {}
            req.params = {}
            
            valid, error = function_app.check_password(req)
            assert valid is False
            assert error == "Unauthorized: Invalid or missing password"
