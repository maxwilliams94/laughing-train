import azure.functions as func
import json
import logging
from typing import Any, Dict, Optional, cast
from validate import check_headers, validate_payload, DRY_RUN_MODE

app = func.FunctionApp()

@app.route(route="arbWebhook", auth_level=func.AuthLevel.ANONYMOUS)
def arbWebhook(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('TradingView webhook request received')
    
    # Get client IP
    x_forwarded_for = cast(Optional[str], req.headers.get('X-Forwarded-For'))  # type: ignore[call-overload]
    client_ip: Optional[str] = None
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(',')[0].strip()
    if not client_ip:
        x_real_ip = cast(Optional[str], req.headers.get('X-Real-IP'))  # type: ignore[call-overload]
        if x_real_ip:
            client_ip = x_real_ip
    
    # Extract client certificate information if available
    # Azure Functions may provide cert info via headers or context
    client_cert: Optional[Dict[str, str]] = None
    cert_subject = cast(Optional[str], req.headers.get('X-ARR-ClientCert-Subject'))  # type: ignore[call-overload]
    if cert_subject:
        # Parse certificate subject string (format: "C=US, ST=Ohio, L=Westerville, ...")
        client_cert = {}
        for part in cert_subject.split(','):
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                client_cert[key.strip()] = value.strip()
    
    # Validate headers, IP, and certificate
    headers_valid, headers_error = check_headers(dict(req.headers), client_ip, client_cert)
    if not headers_valid:
        logging.error(f"Header validation failed: {headers_error}")
        return func.HttpResponse(
            json.dumps({"error": headers_error}),
            status_code=403,
            mimetype="application/json"
        )
    
    # Parse request body
    try:
        req_body: Dict[str, Any] = req.get_json()
    except ValueError as e:
        logging.error(f"Invalid JSON payload: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON payload"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Validate payload
    payload_valid, payload_error = validate_payload(req_body)
    if not payload_valid:
        logging.error(f"Payload validation failed: {payload_error}")
        return func.HttpResponse(
            json.dumps({"error": payload_error}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Log the validated webhook data
    logging.info(f"Valid webhook received - Symbol: {req_body['symbol']}, "
                f"Action: {req_body['action']}, Quantity: {req_body['quantity']}")
    
    # Check if in dry-run mode
    if DRY_RUN_MODE:
        logging.info("DRY RUN MODE: Skipping actual order processing")
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "message": "Webhook received and validated (DRY RUN - no order placed)",
                "dry_run": True,
                "data": {
                    "symbol": req_body["symbol"],
                    "action": req_body["action"],
                    "quantity": req_body["quantity"],
                    "quantity_type": req_body["quantity_type"],
                    "close": req_body["close"]
                }
            }),
            status_code=200,
            mimetype="application/json"
        )
    
    # TODO: Process the webhook (place order, etc.)
    
    return func.HttpResponse(
        json.dumps({
            "status": "success",
            "message": "Webhook received and validated",
            "data": {
                "symbol": req_body["symbol"],
                "action": req_body["action"],
                "quantity": req_body["quantity"],
                "quantity_type": req_body["quantity_type"]
            }
        }),
        status_code=200,
        mimetype="application/json"
    )