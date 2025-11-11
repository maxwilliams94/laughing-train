from typing import Any, Dict

def check_headers(headers: Dict[str, str]):
    return True

def validate_payload(payload: Dict[str, Any]):
    return payload.keys() >= {"symbol", "side", "quantity_type", "quantity", "price"}