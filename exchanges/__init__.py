"""
Exchange authentication package.

Supports authentication for various cryptocurrency exchanges.
"""
from typing import Protocol, Dict, Any


class ExchangeAuthenticator(Protocol):
    """Protocol defining the interface for exchange authenticators."""
    
    def get_auth_headers(
        self,
        request_method: str,
        request_path: str,
        **kwargs: Any
    ) -> Dict[str, str]:
        """
        Get HTTP headers for authenticated API request.
        
        Args:
            request_method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path
            **kwargs: Additional exchange-specific parameters
            
        Returns:
            Dictionary of HTTP headers including Authorization
        """
        ...


# Re-export authenticators for easy imports
from .coinbase import get_coinbase_authenticator, place_order, verify_coinbase_connection, format_symbol_for_coinbase
from .kraken import get_kraken_authenticator

__all__ = [
    'ExchangeAuthenticator',
    'get_coinbase_authenticator',
    'get_kraken_authenticator',
    'place_order',
    'verify_coinbase_connection',
    'format_symbol_for_coinbase',
]
