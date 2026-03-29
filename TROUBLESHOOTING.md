# Burst Request Failure Troubleshooting Guide

## Problem
When receiving 7 requests in a burst, 1-2 are failing without clear reasons.

## Diagnostic Steps

### Step 1: Enable Debug Logging
Set `LOG_LEVEL=DEBUG` in your function app settings:

```bash
# Local development
# Update local.settings.json
{
  "Values": {
    "LOG_LEVEL": "DEBUG"
  }
}

# Azure deployment
az functionapp config appsettings set \
  --name MyFunctionApp \
  --resource-group MyResourceGroup \
  --settings LOG_LEVEL=DEBUG
```

### Step 2: Capture Logs During Burst
Recreate the burst scenario and capture logs. Check for:

```
# What to look for in logs:
- Request body: Same fields being passed?
- Request headers: Content-Type: application/json?
- Any "ERROR" or "EXCEPTION" messages
- Response timestamps: Are requests spaced out or simultaneous?
```

### Step 3: Common Causes and Solutions

#### A. **Content-Type Header Missing**
**Symptom**: Request rejected with "Content-Type must be application/json"
**Solution**: Ensure your requests include:
```
Content-Type: application/json
```

#### B. **Rate Limiting from Coinbase API**
**Symptom**: Orders fail with 429 status code
**Log**: `logging.exception` will show the error
**Solution**: 
- Implement exponential backoff in your TradingView webhook
- Coinbase free tier: ~5 requests/second
- Check [Coinbase Rate Limits Documentation](https://docs.cloud.coinbase.com/exchange/reference/rate-limits)

#### C. **Network Timeouts Under Load**
**Symptom**: Some requests timeout while placing orders
**Log**: `HTTPError` or `ConnectTimeout` in exception
**Solution**:
- Increase Azure Function timeout settings
- Current default: 30 seconds
- In Azure Portal: Function App → Configuration → Function Runtime Settings

#### D. **Invalid JSON from TradingView**
**Symptom**: "Invalid JSON payload" error
**Log**: Will show the exact error at `logging.debug` level
**Solution**:
- Verify TradingView webhook format
- Check if fields are missing or null
- Enable debug logging to see exact payload

#### E. **Coinbase Authentication Failure**
**Symptom**: Order placement fails with 401 error
**Log**: Exception will show authentication details
**Solution**:
- Verify API keys are correct in `local.settings.json`
- Check if API keys have sufficient permissions
- Verify keys haven't expired or been rotated

#### F. **Duplicate/Concurrent Request Handling**
**Symptom**: Random failures with transient errors
**Log**: Check request timestamps and see if processing overlaps
**Solution**:
- Add request deduplication if TradingView sends duplicates
- Implement idempotency keys in order requests
- Check Coinbase's idempotency header support

### Step 4: Analyzing Log Output

**Example Debug Output for Failed Request**:
```
2026-02-08 14:23:45 - root - INFO - TradingView webhook request received
2026-02-08 14:23:45 - root - DEBUG - Request URL: https://yourfunction.azurewebsites.net/api/arbWebhook
2026-02-08 14:23:45 - root - DEBUG - Request method: POST
2026-02-08 14:23:45 - root - DEBUG - Request headers: {
  'content-type': 'application/json',
  'x-forwarded-for': '192.168.1.1',
  ...
}
2026-02-08 14:23:45 - root - DEBUG - Request body: {
  "symbol": "AAPL",
  "action": "buy",
  "quantity": 1,
  "quantity_type": "contracts",
  "close": 150.25
}
2026-02-08 14:23:46 - root - INFO - Valid webhook received - Symbol: AAPL, Action: buy, Quantity: 1
2026-02-08 14:23:47 - root - ERROR - ================================================================================
2026-02-08 14:23:47 - root - ERROR - ORDER PLACEMENT FAILED
2026-02-08 14:23:47 - root - ERROR - Error: 429 Too Many Requests
2026-02-08 14:23:47 - root - ERROR - Error Type: HTTPError
2026-02-08 14:23:47 - root - ERROR - Webhook Data: {...}
2026-02-08 14:23:47 - root - ERROR - ================================================================================
2026-02-08 14:23:47 - root - ERROR - Full exception traceback:
  Traceback (most recent call last):
    ...
```

### Step 5: Log Analysis Checklist

- [ ] Are all 7 requests being received? (Check INFO logs)
- [ ] Are the 2 failing requests identical to succeeding ones? (Compare DEBUG request bodies)
- [ ] Do failures show in ERROR logs? (Check the exact error message)
- [ ] Is there a pattern to which requests fail? (First, last, random?)
- [ ] Are there timeout exceptions? (Check exception tracebacks)
- [ ] Are there Coinbase API errors? (429, 400, 401, 403, 500?)

## Performance Optimization for Bursts

If you're experiencing high failure rates under burst load:

### 1. Async/Parallel Processing
Consider implementing request queuing with Azure Service Bus:
```python
# Current: Synchronous processing
# Proposed: Queue requests for async processing
```

### 2. Connection Pooling
Ensure Coinbase API client reuses connections:
- Check `exchanges/coinbase.py` for session management
- Use `requests.Session` with keep-alive

### 3. Caching
Cache frequently accessed data:
- Coinbase product info
- Account info (update less frequently)

### 4. Circuit Breaker Pattern
Implement graceful degradation:
```python
if coinbase_api_rate_limited:
    return 429, "Please retry in X seconds"
```

## Files to Review

1. **[function_app.py](function_app.py)** - Main webhook handler (now with debug logging)
2. **[validate.py](validate.py)** - Payload validation logic
3. **[exchanges/coinbase.py](exchanges/coinbase.py)** - Coinbase API integration
4. **[local.settings.json](local.settings.json)** - Configuration

## Next Steps

1. Enable `LOG_LEVEL=DEBUG`
2. Run your burst test again
3. Share the logs section from the failure times
4. Cross-reference error messages with solutions above
