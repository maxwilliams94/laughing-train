from typing import Any, Dict
import azure.functions as func
import logging

from validate import validate_payload


def handle_web_hook(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("TradingView webhook received.")

    try:
        body: Dict[str, Any] = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)

    symbol: str | None = body.get("symbol")
    side: str | None = body.get("side")
    quantity_type: str | None = body.get("quantity_type")
    quantity: float | None = body.get("quantity")
    price: float | None = body.get("price")
    if not validate_payload(body):
        logging.error("Missing required fields in the request body: {}".format(body))
        return func.HttpResponse("Missing required fields", status_code=400)
    


    return func.HttpResponse(status_code=201)