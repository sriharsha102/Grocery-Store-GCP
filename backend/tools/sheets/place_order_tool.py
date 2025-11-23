# backend/tools/sheets/place_order_tool.py

import os
import requests
from typing import List
from pydantic.v1 import BaseModel, Field, EmailStr
from langchain.tools import tool

BASE = os.getenv("API_BASE","http://localhost:8080")

class LineItem(BaseModel):
    name: str = Field(..., description="Exact product name")
    qty: int = Field(..., gt=0, description="Quantity ordered")

class PlaceOrderArgs(BaseModel):
    session_id: str = Field(
        ...,
        description="The active chat session id. Used to clear the correct cart after a PAID order."
    )
    customer_email: EmailStr = Field(
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
    """

    # Hard gate: do not proceed without an email
    if not (customer_email and customer_email.strip()):
        return {
            "error": "missing_customer_email",
            "message": "Customer email is required before finalizing the receipt."
        }
    
    payload = {
        "session_id": session_id,
        "customer_email": customer_email,
        "items": [{"name": i.name, "qty": i.qty} for i in items],
    }

    # Hit the new finalize endpoint (single source of truth)
    url = f"{BASE}/api/inventory/finalize_receipt"
    try:
        r = requests.post(url, json=payload, timeout=20)
    except Exception as e:
        return {
            "error": "finalize request failed",
            "exception": str(e),
            "url": url,
            "payload": payload,
        }

    # Try to parse response
    try:
        data = r.json()
    except Exception:
        data = {"raw_text": r.text}

    if r.status_code == 200:
        # Success case
        return {
            "status": "RECEIPT_SENT",
            "order": data.get("order"),
            "cart_cleared": data.get("cart_cleared", False),
            "email_sent": data.get("email_sent", False),
        }

    # Failure (e.g. out-of-stock race condition)
    return {
        "error": "finalize_receipt_failed",
        "status_code": r.status_code,
        "response": data,
        "cart_cleared": False,
        "email_sent": False,
    }
