import os, requests

MODE = os.getenv("EMAIL_MODE", "APPS_SCRIPT").upper()

def send_receipt(customer_email: str, owner_email: str, items: list[dict], order_id: str):
    if MODE == "APPS_SCRIPT":
        url = os.getenv("APPS_SCRIPT_EMAIL_URL")
        payload = {"type": "receipt", "order_id": order_id,
                   "customer_email": customer_email, "owner_email": owner_email, "items": items}
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
    else:
        raise NotImplementedError("Set EMAIL_MODE=APPS_SCRIPT or implement Gmail API sender.")

def send_low_stock_alert(owner_email: str, lows: list[dict]):
    if not lows: return
    if MODE == "APPS_SCRIPT":
        url = os.getenv("APPS_SCRIPT_EMAIL_URL")
        payload = {"type": "low_stock", "owner_email": owner_email, "items": lows}
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
    else:
        raise NotImplementedError("Set EMAIL_MODE=APPS_SCRIPT or implement Gmail API sender.")
