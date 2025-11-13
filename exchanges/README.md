# Exchange Authentication Package Structure

## Overview
The `exchanges/` package provides a modular authentication system for different cryptocurrency exchanges.

## Structure
```
exchanges/
├── __init__.py          # Package exports and common protocol
├── coinbase.py          # Coinbase Advanced Trade API (JWT auth)
└── kraken.py            # Kraken API (placeholder)
```

## Key Components

### `ExchangeAuthenticator` Protocol
Defines the common interface all exchange authenticators must implement:

```python
class ExchangeAuthenticator(Protocol):
    def get_auth_headers(
        self,
        request_method: str,
        request_path: str,
        **kwargs: Any
    ) -> Dict[str, str]:
        """Returns HTTP headers for authenticated requests."""
        ...
```

### Import Pattern
```python
# Import specific authenticator
from exchanges import get_coinbase_authenticator

# Get authenticator instance
auth = get_coinbase_authenticator()

# Use it
headers = auth.get_auth_headers("POST", "/api/v3/brokerage/orders")
```

## Supported Exchanges

### ✅ Coinbase (`exchanges.coinbase`)
- **Authentication**: JWT (ES256 signature)
- **Credentials**: JSON in `COINBASE_CREDENTIALS` env var
- **Features**: Token caching, automatic renewal
- **Status**: Fully implemented

### 🚧 Kraken (`exchanges.kraken`)
- **Authentication**: API Key + Signature
- **Status**: Placeholder only

## Adding New Exchanges

1. **Create module**: `exchanges/your_exchange.py`
2. **Implement authenticator class** following the protocol
3. **Add global getter function**: `get_your_exchange_authenticator()`
4. **Export in `__init__.py`**:
   ```python
   from .your_exchange import get_your_exchange_authenticator
   __all__ = [..., 'get_your_exchange_authenticator']
   ```

## Environment Variables

Each exchange has its own credential format in environment variables:

- `COINBASE_CREDENTIALS`: JSON with `name`, `api_key`, `private_key`
- `KRAKEN_CREDENTIALS`: (future) JSON with `api_key`, `api_secret`
- etc.

This keeps credentials organized and easy to manage across different exchanges.
