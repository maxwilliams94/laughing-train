import azure.functions as func
import json
import logging
import os
from typing import Any, Dict, Optional, cast
from validate import check_headers, validate_payload, DRY_RUN_MODE
from exchanges import place_order, verify_coinbase_connection

app = func.FunctionApp()

# Startup check: Verify Coinbase connectivity
_coinbase_verified = False

# Get password from environment (if empty, no password check needed)
WEBHOOK_PASSWORD = os.getenv("WEBHOOK_PASSWORD", "")


def check_password(req: func.HttpRequest) -> tuple[bool, Optional[str]]:
    """
    Check if the request has the correct password.
    
    Args:
        req: HTTP request object
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # If no password is configured, allow all requests
    if not WEBHOOK_PASSWORD:
        return True, None
    
    # Check for password in Authorization header (Bearer token style)
    auth_header = req.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        if token == WEBHOOK_PASSWORD:
            return True, None
    
    # Check for password in custom X-Webhook-Password header
    password_header = req.headers.get('X-Webhook-Password')
    if password_header == WEBHOOK_PASSWORD:
        return True, None
    
    # Check for password in query parameter
    password_param = req.params.get('password')
    if password_param == WEBHOOK_PASSWORD:
        return True, None
    
    return False, "Unauthorized: Invalid or missing password"


@app.route(route="arbWebhook", auth_level=func.AuthLevel.ANONYMOUS)
def arbWebhook(req: func.HttpRequest) -> func.HttpResponse:
    
    logging.info('TradingView webhook request received')
    
    # Check password first
    password_valid, password_error = check_password(req)
    if not password_valid:
        logging.warning(f"Password check failed: {password_error}")
        return func.HttpResponse(
            json.dumps({"error": password_error}),
            status_code=401,
            mimetype="application/json"
        )
    
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
    
    # Place order on Coinbase
    try:
        logging.info(f"Attempting to place order: {req_body['action']} {req_body['quantity']} "
                    f"{req_body['quantity_type']} of {req_body['symbol']} at close={req_body['close']}")
        
        order_result = place_order(
            symbol=req_body["symbol"],
            action=req_body["action"],
            quantity_type=req_body["quantity_type"],
            quantity=req_body["quantity"],
            close_price=req_body["close"]
        )
        
        # Extract order details from response
        success_response = order_result.get("success_response", {})
        order_id = success_response.get("order_id", "unknown")
        product_id = success_response.get("product_id", req_body["symbol"])
        side = success_response.get("side", req_body["action"])
        
        # Log complete order result for audit trail
        logging.info("="*80)
        logging.info(f"ORDER PLACED SUCCESSFULLY")
        logging.info(f"Order ID: {order_id}")
        logging.info(f"Product: {product_id}")
        logging.info(f"Side: {side}")
        logging.info(f"Webhook Data: action={req_body['action']}, quantity={req_body['quantity']}, "
                    f"quantity_type={req_body['quantity_type']}, close_price={req_body['close']}")
        logging.info(f"Full API Response: {json.dumps(order_result, indent=2)}")
        logging.info("="*80)
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "message": "Order placed successfully",
                "order_id": order_id,
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
    except Exception as e:
        # Log detailed error information
        logging.error("="*80)
        logging.error(f"ORDER PLACEMENT FAILED")
        logging.error(f"Error: {str(e)}")
        logging.error(f"Error Type: {type(e).__name__}")
        logging.error(f"Webhook Data: {json.dumps(req_body, indent=2)}")
        logging.error("="*80)
        logging.exception("Full exception traceback:")
        
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": f"Failed to place order: {str(e)}"
            }),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="webhookVerifyConnectivity", auth_level=func.AuthLevel.ANONYMOUS)
def webhookVerifyConnectivity(req: func.HttpRequest) -> func.HttpResponse:
    
    # Check password first
    password_valid, password_error = check_password(req)
    if not password_valid:
        logging.warning(f"Password check failed: {password_error}")
        return func.HttpResponse(
            json.dumps({"error": password_error}),
            status_code=401,
            mimetype="application/json"
        )
    
    try:
        result: Dict[str, str] = verify_coinbase_connection()
        return func.HttpResponse(
            json.dumps({"status": "success", "message": "Coinbase connectivity verified",
                        "result": result}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"Failed to verify Coinbase connectivity: {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )