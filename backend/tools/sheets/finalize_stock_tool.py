from pydantic.v1 import BaseModel, Field
from typing import List
from langchain_core.tools import tool
import logging
import os
import time
import requests
import uuid
from backend.integrations.google_sheets.sheets_dal import decrement_quantities

log = logging.getLogger(__name__)

# Email configuration
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")
EMAIL_MODE = os.getenv("EMAIL_MODE", "APPS_SCRIPT").upper()
APPS_SCRIPT_EMAIL_URL = os.getenv("APPS_SCRIPT_EMAIL_URL", "")
EMAIL_WEBHOOK_SECRET = os.getenv("EMAIL_WEBHOOK_SECRET", "")
REQUEST_TIMEOUT = int(os.getenv("EXTERNAL_REQUEST_TIMEOUT", "30"))

class OrderItem(BaseModel):
    name: str = Field(..., description="Product name")
    qty: int = Field(..., gt=0, description="Quantity purchased")

class FinalizeStockArgs(BaseModel):
    session_id: str = Field(..., description="Chat session ID for this checkout")
    items: List[OrderItem] = Field(..., description="Paid items to decrement in stock")

@tool("finalize_stock", args_schema=FinalizeStockArgs)
def finalize_stock(session_id: str, items: List[OrderItem]) -> dict:
    """
    Step 1: Run immediately after Stripe confirms 'paid'.
    Decrements stock, updates order count, and triggers low-stock alerts.
    Calls Google Sheets directly instead of making HTTP requests.
    """
    if not items:
        return {"error": "No items provided"}

    try:
        # Decrement stock in Google Sheets
        result = decrement_quantities([(i.name, i.qty) for i in items], tab=None)
    except Exception as e:
        log.exception("finalize_stock: decrement_quantities failed")
        return {"error": f"Sheet update failed: {e}"}

    # Handle out-of-stock race condition
    if result.get("out_of_stock"):
        return {
            "error": "Some items unavailable after payment",
            "details": result["out_of_stock"]
        }

    order_id = f"ORD-{int(time.time())}"

    # Send low-stock alerts if configured
    low_stock_sent = False
    low_debug = {}
    if EMAIL_MODE == "APPS_SCRIPT" and APPS_SCRIPT_EMAIL_URL and EMAIL_WEBHOOK_SECRET:
        updated_list = result.get("updated", []) or []
        low_items = [u for u in updated_list if u.get("low_stock")]

        if low_items and OWNER_EMAIL:
            low_payload = {
                "secret": EMAIL_WEBHOOK_SECRET,
                "type": "low_stock",
                "owner_email": OWNER_EMAIL,
                "items": [{"name": u["name"], "new_qty": u["new_qty"]} for u in low_items],
            }
            try:
                lr = requests.post(APPS_SCRIPT_EMAIL_URL, json=low_payload, timeout=REQUEST_TIMEOUT)
                try:
                    lr_json = lr.json()
                except (ValueError, requests.exceptions.JSONDecodeError):
                    lr_json = {"raw": lr.text, "parse_error": True}

                low_debug = {"status": lr.status_code, "body": lr_json}
                if lr.status_code == 200 and isinstance(lr_json, dict) and lr_json.get("ok") is True:
                    low_stock_sent = True
            except requests.exceptions.Timeout:
                log.error(f"Timeout sending low-stock alert after {REQUEST_TIMEOUT}s")
                low_debug = {"error": "Request timeout"}
            except Exception as e:
                log.exception("finalize_stock: error sending low-stock alert")
                low_debug = {"error": str(e)}

    return {
        "order_id": order_id,
        "status": "STOCK_UPDATED",
        "low_stock_sent": low_stock_sent,
        "low_debug": low_debug,
        "updated": result.get("updated", []),
    }
