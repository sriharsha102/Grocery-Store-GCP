import os, logging, requests

logger = logging.getLogger(__name__)
MODE = os.getenv("EMAIL_MODE", "APPS_SCRIPT").upper()

def _secret() -> str:
    return os.getenv("EMAIL_WEBHOOK_SECRET", "")

def _post(payload: dict) -> None:
    """POST to Apps Script and raise if it returns ok:false or an HTTP error."""
    url = os.getenv("APPS_SCRIPT_EMAIL_URL")
    logger.info(f"[email_sender] Posting type={payload.get('type')} to {url}")
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    body = r.json()
    logger.info(f"[email_sender] Apps Script response: {body}")
    if not body.get("ok"):
        raise RuntimeError(f"Apps Script rejected request: {body}")

def send_receipt(customer_email: str, owner_email: str, items: list[dict], order_id: str):
    if MODE == "APPS_SCRIPT":
        _post({"type": "receipt", "secret": _secret(), "order_id": order_id,
               "customer_email": customer_email, "owner_email": owner_email, "items": items})
    else:
        raise NotImplementedError("Set EMAIL_MODE=APPS_SCRIPT or implement Gmail API sender.")

def send_low_stock_alert(owner_email: str, lows: list[dict]):
    if not lows: return
    if MODE == "APPS_SCRIPT":
        _post({"type": "low_stock", "secret": _secret(), "owner_email": owner_email, "items": lows})
    else:
        raise NotImplementedError("Set EMAIL_MODE=APPS_SCRIPT or implement Gmail API sender.")

def send_item_suggestion(owner_email: str, item_suggestion: str):
    if MODE == "APPS_SCRIPT":
        _post({"type": "item_suggestion", "secret": _secret(),
               "owner_email": owner_email, "item_suggestion": item_suggestion})
    else:
        raise NotImplementedError("Set EMAIL_MODE=APPS_SCRIPT or implement Gmail API sender.")
