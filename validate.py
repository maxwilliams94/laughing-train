from typing import Any, Dict, Optional, Set
import logging
import os

# Environment variables for security checks
ENABLE_IP_WHITELIST = os.getenv("ENABLE_IP_WHITELIST", "true").lower() == "true"
ENABLE_CERT_CHECK = os.getenv("ENABLE_CERT_CHECK", "false").lower() == "true"
DRY_RUN_MODE = os.getenv("DRY_RUN_MODE", "true").lower() == "true"

# TradingView webhook IPs (you should update this with actual IPs)
# TradingView doesn't publish official webhook IPs, so you may need to whitelist specific IPs
TRADINGVIEW_ALLOWED_IPS: Set[str] = set([
    "52.89.214.238",
    "34.212.75.30",
    "54.218.53.128",
    "52.32.178.7",
])

# TradingView certificate subject fields for webhook verification
TRADINGVIEW_CERT_SUBJECT = {
    "C": "US",
    "ST": "Ohio",
    "L": "Westerville",
    "O": "TradingView, Inc.",
    "CN": "webhook-server@tradingview.com"
}

# Required fields in the webhook payload
REQUIRED_FIELDS: Set[str] = {"symbol", "action", "quantity_type", "quantity", "close"}


def check_headers(headers: Dict[str, str], client_ip: Optional[str] = None, 
                  client_cert: Optional[Dict[str, str]] = None) -> tuple[bool, Optional[str]]:
    """
    Validate request headers, client IP, and certificate.
    
    Args:
        headers: Request headers
        client_ip: Client IP address
        client_cert: Client certificate subject fields (if available)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    logging.debug(f"ENABLE_IP_WHITELIST={ENABLE_IP_WHITELIST}, ENABLE_CERT_CHECK={ENABLE_CERT_CHECK}, DRY_RUN_MODE={DRY_RUN_MODE}")
    # Check Content-Type
    content_type = headers.get('content-type', '').lower()
    if 'application/json' not in content_type:
        return False, "Content-Type must be application/json"
    
    # Validate IP whitelist if enabled
    if ENABLE_IP_WHITELIST:
        if not TRADINGVIEW_ALLOWED_IPS:
            logging.warning("IP whitelist is enabled but TRADINGVIEW_ALLOWED_IPS is empty")
        elif client_ip:
            if client_ip not in TRADINGVIEW_ALLOWED_IPS:
                logging.warning(f"Rejected request from non-whitelisted IP: {client_ip}")
                return False, f"Unauthorized IP address: {client_ip}"
        else:
            logging.warning("IP whitelist is enabled but client IP is not available")
            return False, "Unable to verify client IP"
    
    # Validate client certificate if enabled
    if ENABLE_CERT_CHECK:
        if not client_cert:
            logging.warning("Certificate check is enabled but no certificate provided")
            return False, "Client certificate required but not provided"
        
        # Verify certificate subject fields
        for field, expected_value in TRADINGVIEW_CERT_SUBJECT.items():
            actual_value = client_cert.get(field)
            if actual_value != expected_value:
                logging.warning(f"Certificate validation failed: {field} = {actual_value}, expected {expected_value}")
                return False, f"Invalid certificate: {field} mismatch"
        
        logging.info("Client certificate validated successfully")
    
    return True, None


def validate_payload(payload: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate the webhook payload contains required fields.
    
    Args:
        payload: The JSON payload from TradingView
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for required fields
    missing_fields = REQUIRED_FIELDS - payload.keys()
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    # Validate field types and values
    if not isinstance(payload.get("symbol"), str) or not payload.get("symbol"):
        return False, "Field 'symbol' must be a non-empty string"
    
    if payload.get("action") not in ["buy", "sell"]:
        return False, "Field 'action' must be 'buy' or 'sell'"
    
    if payload.get("quantity_type") not in ["cash", "contracts", "percent"]:
        return False, "Field 'quantity_type' must be 'cash', 'contracts', or 'percent'"
    
    # Validate quantity is numeric
    try:
        quantity = float(payload.get("quantity", 0))
        if quantity <= 0:
            return False, "Field 'quantity' must be a positive number"
    except (ValueError, TypeError):
        return False, "Field 'quantity' must be a valid number"
    
    # Validate close price is numeric
    try:
        close = float(payload.get("close", 0))
        if close <= 0:
            return False, "Field 'close' must be a positive number"
    except (ValueError, TypeError):
        return False, "Field 'close' must be a valid number"
    
    return True, None