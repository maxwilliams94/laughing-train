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
        payload = {
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
