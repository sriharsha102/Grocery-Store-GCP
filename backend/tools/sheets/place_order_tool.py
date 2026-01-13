# backend/tools/sheets/place_order_tool.py

import os
import logging
import time
import requests
from typing import List
from pydantic.v1 import BaseModel, Field
from langchain.tools import tool
from backend.tools.cart.cart_tool import clear_cart
from backend.state.session import set_awaiting_email

log = logging.getLogger(__name__)

# Email configuration
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")
EMAIL_MODE = os.getenv("EMAIL_MODE", "APPS_SCRIPT").upper()
APPS_SCRIPT_EMAIL_URL = os.getenv("APPS_SCRIPT_EMAIL_URL", "")
EMAIL_WEBHOOK_SECRET = os.getenv("EMAIL_WEBHOOK_SECRET", "")
REQUEST_TIMEOUT = int(os.getenv("EXTERNAL_REQUEST_TIMEOUT", "30"))

class LineItem(BaseModel):
    name: str = Field(..., description="Exact product name")
    qty: int = Field(..., gt=0, description="Quantity ordered")

class PlaceOrderArgs(BaseModel):
    session_id: str = Field(
        ...,
        description="The active chat session id. Used to clear the correct cart after a PAID order."
    )
    customer_email: str = Field(
        ...,
        description="Customer email where the receipt should be sent."
    )
    items: List[LineItem] = Field(
        ...,
        description="Line items for THIS finalized purchase only (not past orders)."
    )

@tool("place_order", args_schema=PlaceOrderArgs)
def place_order(session_id: str, customer_email: str, items: List[LineItem]) -> dict:
    """
    Send the receipt for a PAID order and clear the cart.

    IMPORTANT CONTRACT:
    - Stock must already be finalized by calling `finalize_stock` exactly once for this purchase.
    - `place_order` ONLY sends the receipt (customer + owner copy) and clears the cart.
    - Do NOT call this until you have a valid customer_email.

    Call this ONLY AFTER:
      1) `stripe_checkout_status_tool` returned status == 'paid'
      2) You collected the customer's email
      3) You pass ONLY the items they just paid for

    Calls backend functions directly instead of making HTTP requests.
    """

    # Hard gate: do not proceed without a valid email
    if not (customer_email and customer_email.strip()):
        return {
            "error": "missing_customer_email",
            "message": "Customer email is required before finalizing the receipt."
        }
    email_value = customer_email.strip()
    if "@" not in email_value or "." not in email_value.split("@")[-1]:
        return {
            "error": "invalid_customer_email",
            "message": "Customer email is required before finalizing the receipt."
        }


    order_id = f"ORD-{int(time.time())}"

    # Send receipt email via Apps Script
    email_sent = False
    email_debug = {}

    if EMAIL_MODE == "APPS_SCRIPT" and APPS_SCRIPT_EMAIL_URL and EMAIL_WEBHOOK_SECRET:
        payload = {
            "secret": EMAIL_WEBHOOK_SECRET,
            "type": "receipt",
            "order": {
                "order_id": order_id,
                "customer_email": email_value,
                "items": [{"name": i.name, "qty": i.qty} for i in items],
            },
            "owner_email": OWNER_EMAIL,
        }

        try:
            er = requests.post(APPS_SCRIPT_EMAIL_URL, json=payload, timeout=REQUEST_TIMEOUT)
            try:
                er_json = er.json()
            except (ValueError, requests.exceptions.JSONDecodeError):
                er_json = {"raw": er.text, "parse_error": True}

            email_debug = {"status": er.status_code, "body": er_json}
            if er.status_code == 200 and isinstance(er_json, dict) and er_json.get("ok") is True:
                email_sent = True
        except requests.exceptions.Timeout:
            log.error(f"Timeout sending receipt email after {REQUEST_TIMEOUT}s")
            email_debug = {"error": "Request timeout"}
        except Exception as e:
            email_debug = {"error": str(e)}
            log.exception("place_order: error sending receipt email")
    else:
        log.warning("place_order: missing webhook config, skipping email")

    # Clear the cart
    cart_cleared = False
    try:
        clear_cart(session_id)
        cart_cleared = True
        set_awaiting_email(session_id, False)
    except Exception:
        log.exception("place_order: failed to clear cart for session %s", session_id)

    return {
        "status": "RECEIPT_SENT",
        "order": {"order_id": order_id, "status": "RECEIPT_SENT"},
        "cart_cleared": cart_cleared,
        "email_sent": email_sent,
        "email_debug": email_debug,
    }
