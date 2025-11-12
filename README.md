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

### Example Configuration

In `local.settings.json`:
```json
{
  "Values": {
    "ENABLE_IP_WHITELIST": "true",
    "ENABLE_CERT_CHECK": "true",
    "DRY_RUN_MODE": "false"
  }
}
```

In Azure Portal (Application Settings):
```
ENABLE_IP_WHITELIST = true
ENABLE_CERT_CHECK = true
DRY_RUN_MODE = false
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
