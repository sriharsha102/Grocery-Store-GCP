# backend/tools/sheets/place_order_tool.py
import os, requests
from typing import List
from pydantic.v1 import BaseModel, Field, EmailStr
from langchain.tools import tool

BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

# Email config (from .env)
EMAIL_MODE = os.getenv("EMAIL_MODE", "APPS_SCRIPT")  # APPS_SCRIPT | OFF
OWNER_EMAIL = os.getenv("OWNER_EMAIL")               # e.g. developer@domain.com
APPS_SCRIPT_EMAIL_URL = os.getenv("APPS_SCRIPT_EMAIL_URL")  # deployed Web App "exec" URL
EMAIL_WEBHOOK_SECRET = os.getenv("EMAIL_WEBHOOK_SECRET")     # same secret you used in Apps Script

class LineItem(BaseModel):
    name: str = Field(..., description="Exact product name")
    qty: int = Field(..., gt=0, description="Quantity ordered")

class PlaceOrderArgs(BaseModel):
    customer_email: EmailStr = Field(..., description="Customer email for receipt")
    items: List[LineItem] = Field(..., description="Line items")

@tool("place_order", args_schema=PlaceOrderArgs)
def place_order(customer_email: str, items: List[LineItem]) -> dict:
    """
    Confirm an order in Sheets, then send emails via Apps Script (if configured).
    """
    # 1) Place order / update Sheets
    payload = {
        "customer_email": customer_email,
        "items": [{"name": i.name, "qty": i.qty} for i in items],
    }
    endpoints = ["/api/inventory/order", "/inventory/order"]
    order_result = None
    attempts = []

    for path in endpoints:
        try:
            r = requests.post(f"{BASE}{path}", json=payload, timeout=20)
            if r.status_code == 200:
                try:
                    order_result = r.json()
                    break
                except Exception:
                    attempts.append({"path": path, "status": r.status_code, "body": r.text})
            else:
                attempts.append({"path": path, "status": r.status_code, "body": r.text})
        except Exception as e:
            attempts.append({"path": path, "error": str(e)})

    if not order_result:
        return {"error": "place_order failed", "attempts": attempts}

    # 2) Send emails (Apps Script webhook) if enabled
    email_attempt = None
    owner_alert_attempt = None

    if EMAIL_MODE.upper() == "APPS_SCRIPT" and APPS_SCRIPT_EMAIL_URL and EMAIL_WEBHOOK_SECRET:
        try:
            # Receipt to customer (and CC owner if your script does that)
            email_payload = {
                "secret": EMAIL_WEBHOOK_SECRET,
                "type": "receipt",
                "order": {
                    "order_id": order_result.get("order_id"),
                    "customer_email": customer_email,
                    "items": [{"name": i.name, "qty": i.qty} for i in items],
                },
                "owner_email": OWNER_EMAIL,
            }
            er = requests.post(APPS_SCRIPT_EMAIL_URL, json=email_payload, timeout=20)
            email_attempt = {"status": er.status_code, "text": er.text}

            # Low-stock alert to owner if any item is low
            updated = order_result.get("updated", []) or []
            low = [u for u in updated if u.get("low_stock")]
            if low and OWNER_EMAIL:
                warn_payload = {
                    "secret": EMAIL_WEBHOOK_SECRET,
                    "type": "low_stock",
                    "owner_email": OWNER_EMAIL,
                    "items": low,
                }
                wr = requests.post(APPS_SCRIPT_EMAIL_URL, json=warn_payload, timeout=20)
                owner_alert_attempt = {"status": wr.status_code, "text": wr.text}
        except Exception as e:
            email_attempt = {"error": str(e)}

    return {
        "order": order_result,
        "email_mode": EMAIL_MODE,
        "email_attempt": email_attempt,
        "owner_alert_attempt": owner_alert_attempt,
    }
