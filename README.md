Azure Function for turning Trading View webhook notifications into BUY/SELL orders

## Security Configuration

The webhook handler supports two security verification methods that can be enabled via environment variables:

### Environment Variables

- **`ENABLE_IP_WHITELIST`** (default: `false`)
  - Set to `true` to enable IP address whitelisting
  - When enabled, only requests from IPs in `TRADINGVIEW_ALLOWED_IPS` will be accepted
  - Configure allowed IPs in `validate.py`

- **`ENABLE_CERT_CHECK`** (default: `false`)
  - Set to `true` to enable client certificate verification
  - When enabled, validates the client certificate against TradingView's expected certificate subject:
    ```
    C = US
    ST = Ohio
    L = Westerville
    O = TradingView, Inc.
    CN = webhook-server@tradingview.com
    ```

- **`DRY_RUN_MODE`** (default: `false`)
  - Set to `true` to enable dry-run mode
  - When enabled, webhooks are validated but no actual order processing occurs
  - Returns acknowledgement with `"dry_run": true` flag
  - Useful for testing webhook integration without placing real orders

- **`COINBASE_CREDENTIALS`** (required for Coinbase integration)
  - JSON string containing Coinbase API credentials
  - Format: `{"name": "account-name", "api_key": "organizations/.../apiKeys/...", "private_key": "-----BEGIN EC PRIVATE KEY-----\\n...\\n-----END EC PRIVATE KEY-----\\n"}`
  - Used to generate JWT tokens for Coinbase API authentication
  - Keep this secure - never commit actual credentials to version control

### Example Configuration

In `local.settings.json`:
```json
{
  "Values": {
    "ENABLE_IP_WHITELIST": "true",
    "ENABLE_CERT_CHECK": "true",
    "DRY_RUN_MODE": "false",
    "COINBASE_CREDENTIALS": "{\"name\":\"my-account\",\"api_key\":\"organizations/YOUR_ORG/apiKeys/YOUR_KEY\",\"private_key\":\"-----BEGIN EC PRIVATE KEY-----\\nYOUR_KEY\\n-----END EC PRIVATE KEY-----\\n\"}"
  }
}
```

In Azure Portal (Application Settings):
```
ENABLE_IP_WHITELIST = true
ENABLE_CERT_CHECK = true
DRY_RUN_MODE = false
COINBASE_CREDENTIALS = {"name":"my-account","api_key":"organizations/YOUR_ORG/apiKeys/YOUR_KEY","private_key":"-----BEGIN EC PRIVATE KEY-----\nYOUR_KEY\n-----END EC PRIVATE KEY-----\n"}
```

## Webhook Payload

Expected JSON payload from TradingView:
```json
{
    "symbol": "BTCUSD",
    "action": "buy",
    "quantity_type": "cash",
    "quantity": "100",
    "close": "50000.00"
}
```

### Required Fields

- `symbol` - Trading symbol (string)
- `action` - Order action: `buy` or `sell`
- `quantity_type` - Type of quantity: `cash`, `contracts`, or `percent`
- `quantity` - Positive number as string
- `close` - Current close price (positive number)

## Coinbase Integration

### Authentication
The application uses JWT (JSON Web Token) authentication for Coinbase API calls. Credentials are loaded from the `COINBASE_CREDENTIALS` environment variable.

### Setting Up Coinbase Credentials

1. **Get your API key from Coinbase Developer Platform**:
   - Go to [CDP Portal](https://portal.cdp.coinbase.com/)
   - Create a new API key
   - Copy the API key name (format: `organizations/{org_id}/apiKeys/{key_id}`)
   - Download the private key file

2. **Format the credentials as JSON**:
   ```json
   {
     "name": "my-trading-account",
     "api_key": "organizations/abc123/apiKeys/xyz789",
     "private_key": "-----BEGIN EC PRIVATE KEY-----\nMHc...your key here...==\n-----END EC PRIVATE KEY-----\n"
   }
   ```

3. **Set the environment variable**:
   - For local development: Add to `local.settings.json`
   - For Azure: Add to Application Settings (Portal or CLI)
   - **Important**: Escape newlines as `\\n` in `local.settings.json`, use literal `\n` in Azure Portal

### JWT Token Generation
The `exchanges/coinbase.py` module handles:
- Loading credentials from environment
- Generating JWT tokens with proper claims and signatures
- Token caching (tokens are valid for 120 seconds)
- Building Authorization headers for API requests

Example usage:
```python
from exchanges import get_coinbase_authenticator

# Get authenticator instance
auth = get_coinbase_authenticator()

# Generate JWT for specific API call
headers = auth.get_auth_headers(
    request_method="POST",
    request_host="api.coinbase.com",
    request_path="/api/v3/brokerage/orders"
)

# Use headers in your HTTP request
# headers = {"Authorization": "Bearer ...", "Content-Type": "application/json"}
```

## Exchange Support

The application uses a modular exchange authentication system located in the `exchanges/` package:

- **`exchanges/coinbase.py`** - Coinbase Advanced Trade API (JWT authentication)
- **`exchanges/kraken.py`** - Kraken API (placeholder for future implementation)
- **`exchanges/__init__.py`** - Common interface and exports

To add a new exchange:
1. Create `exchanges/your_exchange.py`
2. Implement the `ExchangeAuthenticator` protocol
3. Add credentials loading from environment
4. Export via `exchanges/__init__.py`
