"""
Coinbase API authentication and JWT generation.
"""
import requests
from typing import Dict, Any, Optional
import json
import os
import logging
import jwt
import time
import uuid


def format_symbol_for_coinbase(symbol: str) -> str:
    """
    Convert symbol to Coinbase product format.
    
    Coinbase requires format: BTC-USD, ETH-USD, BTC-EUR
    This function expects the symbol to already be in the correct format from TradingView.
    
    Args:
        symbol: Symbol in format "BTC-EUR", "ETH-USD", etc.
        
    Returns:
        Symbol in uppercase (e.g., "BTC-USD", "ETH-USD", "BTC-EUR")
        
    Examples:
        >>> format_symbol_for_coinbase("BTC-USD")
        "BTC-USD"
        >>> format_symbol_for_coinbase("btc-usd")
        "BTC-USD"
        >>> format_symbol_for_coinbase("ETH-EUR")
        "ETH-EUR"
    """
    # Just return uppercase - symbol should already be in BTC-USD format
    return symbol.upper()


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
            creds_data: Dict[str, Any] = json.loads(creds_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in '{env_var}': {e}")
        assert isinstance(creds_data, dict), "Credentials JSON must be an object"
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


def _get_product_precision(symbol: str, api_base_url: str) -> tuple[int, int]:
    """
    Get base and quote decimal precision for a product from Coinbase API.
    
    Args:
        symbol: Trading pair (e.g., "BTC-USD")
        api_base_url: Coinbase API base URL
        
    Returns:
        Tuple of (base_decimals, quote_decimals)
    """
    import requests
    from decimal import Decimal
    
    authenticator = get_coinbase_authenticator()
    request_path = f"/api/v3/brokerage/market/products/{symbol}"
    host = api_base_url.replace("https://", "").replace("http://", "")
    
    headers = authenticator.get_auth_headers(
        request_method="GET",
        request_host=host,
        request_path=request_path
    )
    
    url = f"{api_base_url}{request_path}"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    product = response.json()
    
    # Parse increment strings to determine decimal places
    base_increment = Decimal(product.get("base_increment", "0.00000001"))
    quote_increment = Decimal(product.get("quote_increment", "0.01"))
    
    # Count decimal places from increment
    base_decimals: int = abs(int(base_increment.as_tuple().exponent)) if isinstance(base_increment.as_tuple().exponent, int) else 8
    quote_decimals: int = abs(int(quote_increment.as_tuple().exponent)) if isinstance(quote_increment.as_tuple().exponent, int) else 2
    
    logging.debug(f"Product {symbol}: base_increment={base_increment} ({base_decimals} decimals), "
                  f"quote_increment={quote_increment} ({quote_decimals} decimals)")
    
    return base_decimals, quote_decimals


def _format_quantity(value: float, decimals: int) -> str:
    """
    Format quantity with exact decimal precision for Coinbase API.
    
    Args:
        value: The numeric value to format
        decimals: Number of decimal places to use
        
    Returns:
        Formatted string with appropriate decimal places, trailing zeros stripped
    """
    formatted = f"{value:.{decimals}f}".rstrip('0').rstrip('.')
    return formatted


def place_order(
    symbol: str,
    action: str,
    quantity_type: str,
    quantity: float,
    close_price: Optional[float] = None,
    api_base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Place a limit order on Coinbase Advanced Trade API.
    
    Args:
        symbol: Trading pair (e.g., "BTC-USD")
        action: "buy" or "sell"
        quantity_type: "cash" or "units"
        quantity: Amount to trade (in cash or units depending on quantity_type)
        close_price: Current price (required for limit orders and when selling with cash)
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
    
    # Validate close_price - required for limit orders
    if close_price is None or close_price <= 0:
        raise ValueError("close_price is required for limit orders and must be greater than 0")
    
    # Convert symbol to Coinbase format (uppercase normalization)
    coinbase_symbol = format_symbol_for_coinbase(symbol)
    logging.info(f"Symbol conversion: {symbol} -> {coinbase_symbol}")
    
    # For SELL orders with cash, we need the close price to calculate units
    if action == "SELL" and quantity_type == "cash":
        # Calculate how many units to sell based on cash amount and current price
        calculated_units = quantity / close_price
        logging.info(f"Converting SELL cash amount ${quantity} to {calculated_units} units at price ${close_price}")
        quantity = calculated_units
        quantity_type = "units"  # Now we're working with units
    
    # Get API base URL
    if api_base_url is None:
        api_base_url = os.getenv("COINBASE_API_BASE_URL", "https://api.coinbase.com")
    
    # Get product precision from Coinbase API
    base_decimals, quote_decimals = _get_product_precision(coinbase_symbol, api_base_url)
    
    # Build order configuration
    order_config: Dict[str, Any] = {}
    
    # Format limit price with quote currency decimals
    formatted_limit_price = _format_quantity(close_price, quote_decimals)
    
    if action == "BUY":
        if quantity_type == "cash":
            # Buy with cash amount (quote currency)
            order_config["limit_limit_gtc"] = {
                "quote_size": _format_quantity(quantity, quote_decimals),
                "limit_price": formatted_limit_price
            }
        else:
            # Buy with crypto amount (base currency)
            order_config["limit_limit_gtc"] = {
                "base_size": _format_quantity(quantity, base_decimals),
                "limit_price": formatted_limit_price
            }
    else:  # SELL
        # Sell always uses base_size (crypto amount)
        order_config["limit_limit_gtc"] = {
            "base_size": _format_quantity(quantity, base_decimals),
            "limit_price": formatted_limit_price
        }
    
    # Build request body
    request_body: Dict[str, Any] = {
        "client_order_id": str(uuid.uuid4()),
        "product_id": coinbase_symbol,
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
    logging.info(f"Placing {action} order for {coinbase_symbol}: {quantity_type}={quantity}")
    if action == "SELL" and quantity_type == "units":
        # Log if this was a cash-to-units conversion
        logging.info(f"Order details - Symbol: {coinbase_symbol}, Side: {action}, Base Size: {quantity}")
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


def verify_coinbase_connection(api_base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify Coinbase API connectivity by fetching accounts.
    
    This function should be called during startup to ensure:
    - Credentials are properly configured
    - JWT authentication is working
    - API connectivity is established
    
    Args:
        api_base_url: Override default API base URL (for testing)
        
    Returns:
        Dictionary containing account information
        
    Raises:
        ValueError: If credentials are invalid
        requests.HTTPError: If API request fails
    """
    
    # Get API base URL
    if api_base_url is None:
        api_base_url = os.getenv("COINBASE_API_BASE_URL", "https://api.coinbase.com")
    
    # Get authenticator
    authenticator = get_coinbase_authenticator()
    request_path = "/api/v3/brokerage/accounts"
    
    # Extract host from URL for JWT generation
    host = api_base_url.replace("https://", "").replace("http://", "")
    
    headers = authenticator.get_auth_headers(
        request_method="GET",
        request_host=host,
        request_path=request_path
    )
    
    # Make API request - paginate through all accounts
    url = f"{api_base_url}{request_path}"
    logging.info("Verifying Coinbase API connectivity...")
    logging.debug(f"API URL: {url}")
    
    all_accounts: list[Dict[str, Any]] = []
    cursor = None
    
    while True:
        # Add cursor parameter if we have one
        params = {"limit": 250}
        if cursor:
            params["cursor"] = cursor
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Collect accounts from this page
        accounts = result.get("accounts", [])
        all_accounts.extend(accounts)
        
        # Check if there are more pages
        has_next = result.get("has_next", False)
        if not has_next:
            break
        
        # Get cursor for next page
        cursor = result.get("cursor")
        if not cursor:
            break
        
        logging.debug(f"Fetching next page of accounts (cursor: {cursor})")
    
    # Log account information
    logging.info(f"Coinbase API connection verified successfully!")
    logging.info(f"Found {len(all_accounts)} account(s) total")
    
    # Log balances for audit trail
    currencies = set(["BTC", "ETH", "USD", "USDC", "LTC", "BCH", "XRP", "ADA", "DOT", "SOL", "APT", "EUR"])
    balances: Dict[str, str] = {}
    for account in all_accounts:
        currency = account.get("currency", "???")
        if currency not in currencies:
            continue

        available_balance = account.get("available_balance", {})
        balance_value = available_balance.get("value", "0")
        balance_currency = available_balance.get("currency", currency)
        logging.info(f"  - {currency}: {balance_value} {balance_currency} available")
        balances[currency] = f"{balance_value} {balance_currency}"
    
    logging.debug(f"Total accounts fetched: {len(all_accounts)}")
    
    return balances

