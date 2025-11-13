"""
Coinbase API authentication and JWT generation.
"""
from typing import Dict, Any, Optional
import json
import os
import logging
import jwt
import time
import uuid
import requests


class CoinbaseCredentials:
    """Store Coinbase API credentials loaded from environment."""
    
    def __init__(self, name: str, api_key: str, private_key: str, **kwargs: Any):
        """
        Initialize Coinbase credentials.
        
        Args:
            name: User identifier or credential name
            api_key: Coinbase API key (format: organizations/{org_id}/apiKeys/{key_id})
            private_key: EC private key in PEM format
            **kwargs: Additional credential fields (for future extensibility)
        """
        self.name = name
        self.api_key = api_key
        self.private_key = private_key
        self.extra = kwargs
    
    @classmethod
    def from_env(cls, env_var: str = "COINBASE_CREDENTIALS") -> "CoinbaseCredentials":
        """
        Load credentials from environment variable containing JSON.
        
        Expected JSON format:
        {
            "name": "my-account",
            "api_key": "organizations/{org_id}/apiKeys/{key_id}",
            "private_key": "-----BEGIN EC PRIVATE KEY-----\\n...\\n-----END EC PRIVATE KEY-----\\n"
        }
        
        Args:
            env_var: Environment variable name containing JSON credentials
            
        Returns:
            CoinbaseCredentials instance
            
        Raises:
            ValueError: If credentials are missing or invalid
        """
        creds_json = os.getenv(env_var)
        if not creds_json:
            raise ValueError(f"Environment variable '{env_var}' is not set")
        
        try:
            creds_data = json.loads(creds_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in '{env_var}': {e}")
        
        # Validate required fields
        required_fields = ["name", "api_key", "private_key"]
        missing = [f for f in required_fields if f not in creds_data]
        if missing:
            raise ValueError(f"Missing required credential fields: {', '.join(missing)}")
        
        # Unescape newlines in private key if needed
        private_key = creds_data["private_key"].replace("\\n", "\n")
        
        return cls(
            name=creds_data["name"],
            api_key=creds_data["api_key"],
            private_key=private_key,
            **{k: v for k, v in creds_data.items() if k not in required_fields}
        )


class CoinbaseAuthenticator:
    """Generate JWT tokens for Coinbase API authentication."""
    
    def __init__(self, credentials: CoinbaseCredentials):
        """
        Initialize authenticator with credentials.
        
        Args:
            credentials: CoinbaseCredentials instance
        """
        self.credentials = credentials
        self._cached_token: Optional[str] = None
        self._token_expiry: float = 0.0
    
    def generate_jwt(
        self,
        request_method: str = "GET",
        request_host: str = "api.coinbase.com",
        request_path: str = "/api/v3/brokerage/accounts",
        expires_in: int = 120
    ) -> str:
        """
        Generate a JWT token for Coinbase API authentication.
        
        Args:
            request_method: HTTP method (GET, POST, etc.)
            request_host: API host (e.g., api.coinbase.com)
            request_path: API endpoint path
            expires_in: Token validity in seconds (max 120)
            
        Returns:
            JWT token string
        """
        current_time = int(time.time())
        
        # Build the URI for the 'uri' claim
        uri = f"{request_method} {request_host}{request_path}"
        
        # JWT payload
        payload: Dict[str, Any] = {
            "iss": "cdp",  # Issuer
            "nbf": current_time,  # Not before
            "exp": current_time + min(expires_in, 120),  # Expiration (max 120 seconds)
            "sub": self.credentials.api_key,  # Subject (API key)
            "uri": uri  # Request URI
        }
        
        # JWT headers
        headers = {
            "kid": self.credentials.api_key,  # Key ID
            "nonce": uuid.uuid4().hex  # Unique nonce
        }
        
        # Sign and encode the JWT
        token = jwt.encode(
            payload,
            self.credentials.private_key,
            algorithm="ES256",
            headers=headers
        )
        
        logging.debug(f"Generated JWT for {uri} (expires in {expires_in}s)")
        return token
    
    def get_token(
        self,
        request_method: str = "GET",
        request_host: str = "api.coinbase.com",
        request_path: str = "/api/v3/brokerage/accounts",
        use_cache: bool = True
    ) -> str:
        """
        Get a JWT token, using cached token if still valid.
        
        Args:
            request_method: HTTP method
            request_host: API host
            request_path: API endpoint path
            use_cache: Whether to use cached token if valid
            
        Returns:
            JWT token string
        """
        current_time = time.time()
        
        # Return cached token if still valid (with 10s buffer)
        if use_cache and self._cached_token and current_time < (self._token_expiry - 10):
            logging.debug("Using cached JWT token")
            return self._cached_token
        
        # Generate new token
        expires_in = 120
        token = self.generate_jwt(request_method, request_host, request_path, expires_in)
        
        # Cache the token
        self._cached_token = token
        self._token_expiry = current_time + expires_in
        
        return token
    
    def get_auth_headers(
        self,
        request_method: str = "GET",
        request_host: str = "api.coinbase.com",
        request_path: str = "/api/v3/brokerage/accounts"
    ) -> Dict[str, str]:
        """
        Get HTTP headers for authenticated Coinbase API request.
        
        Args:
            request_method: HTTP method
            request_host: API host
            request_path: API endpoint path
            
        Returns:
            Dictionary of HTTP headers including Authorization
        """
        token = self.get_token(request_method, request_host, request_path)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }


# Global authenticator instance (loaded lazily)
_authenticator: Optional[CoinbaseAuthenticator] = None


def get_coinbase_authenticator() -> CoinbaseAuthenticator:
    """
    Get or create the global CoinbaseAuthenticator instance.
    
    Returns:
        CoinbaseAuthenticator instance
        
    Raises:
        ValueError: If credentials cannot be loaded
    """
    global _authenticator
    
    if _authenticator is None:
        credentials = CoinbaseCredentials.from_env()
        _authenticator = CoinbaseAuthenticator(credentials)
        logging.info(f"Initialized Coinbase authenticator for account: {credentials.name}")
    
    return _authenticator


def place_order(
    symbol: str,
    action: str,
    quantity_type: str,
    quantity: float,
    close_price: Optional[float] = None,
    api_base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Place a market order on Coinbase Advanced Trade API.
    
    Args:
        symbol: Trading pair (e.g., "BTC-USD")
        action: "buy" or "sell"
        quantity_type: "cash" or "units"
        quantity: Amount to trade (in cash or units depending on quantity_type)
        close_price: Current price (required when selling with cash to calculate units)
        api_base_url: Override default API base URL (for testing)
        
    Returns:
        Dictionary with order response from Coinbase API
        
    Raises:
        ValueError: If parameters are invalid
        requests.HTTPError: If API request fails
    """
    import requests
    
    # Validate action
    action = action.upper()
    if action not in ["BUY", "SELL"]:
        raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'")
    
    # Validate quantity_type
    if quantity_type not in ["cash", "units"]:
        raise ValueError(f"Invalid quantity_type: {quantity_type}. Must be 'cash' or 'units'")
    
    # For SELL orders with cash, we need the close price to calculate units
    if action == "SELL" and quantity_type == "cash":
        if close_price is None or close_price <= 0:
            raise ValueError("SELL orders with quantity_type='cash' require a valid close_price to calculate units")
        # Calculate how many units to sell based on cash amount and current price
        calculated_units = quantity / close_price
        logging.info(f"Converting SELL cash amount ${quantity} to {calculated_units} units at price ${close_price}")
        quantity = calculated_units
        quantity_type = "units"  # Now we're working with units
    
    # Get API base URL
    if api_base_url is None:
        api_base_url = os.getenv("COINBASE_API_BASE_URL", "https://api.coinbase.com")
    
    # Build order configuration
    order_config: Dict[str, Any] = {}
    
    if action == "BUY":
        if quantity_type == "cash":
            # Buy with cash amount (quote currency)
            order_config["market_market_ioc"] = {
                "quote_size": str(quantity)
            }
        else:
            # Buy with crypto amount (base currency)
            order_config["market_market_ioc"] = {
                "base_size": str(quantity)
            }
    else:  # SELL
        # Sell always uses base_size (crypto amount)
        order_config["market_market_ioc"] = {
            "base_size": str(quantity)
        }
    
    # Build request body
    request_body = {
        "client_order_id": str(uuid.uuid4()),
        "product_id": symbol,
        "side": action,
        "order_configuration": order_config
    }
    
    # Get authenticator and generate headers
    authenticator = get_coinbase_authenticator()
    request_path = "/api/v3/brokerage/orders"
    
    # Extract host from URL for JWT generation
    host = api_base_url.replace("https://", "").replace("http://", "")
    
    headers = authenticator.get_auth_headers(
        request_method="POST",
        request_host=host,
        request_path=request_path
    )
    
    # Make API request
    url = f"{api_base_url}{request_path}"
    
    # Log request details
    logging.info(f"Placing {action} order for {symbol}: {quantity_type}={quantity}")
    if action == "SELL" and quantity_type == "units":
        # Log if this was a cash-to-units conversion
        logging.info(f"Order details - Symbol: {symbol}, Side: {action}, Base Size: {quantity}")
    logging.debug(f"API URL: {url}")
    logging.debug(f"Request body: {json.dumps(request_body, indent=2)}")
    
    response = requests.post(url, headers=headers, json=request_body, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    
    # Log response details
    if result.get("success"):
        success_resp = result.get("success_response", {})
        logging.info(f"Order API response - Success: True, Order ID: {success_resp.get('order_id')}, "
                    f"Product: {success_resp.get('product_id')}, Side: {success_resp.get('side')}")
    else:
        logging.warning(f"Order API response - Success: False")
    
    logging.debug(f"Full API response: {json.dumps(result, indent=2)}")
    
    # Check if order was successful
    if not result.get("success"):
        error_response = result.get("error_response", {})
        error_msg = error_response.get("message", "Unknown error")
        error_details = error_response.get("error_details", "")
        error_reason = error_response.get("error", "UNKNOWN")
        logging.error(f"Order failed - Error: {error_reason}, Message: {error_msg}, Details: {error_details}")
        raise ValueError(f"Order failed: {error_msg}. Details: {error_details}")
    
    return result

