# backend/tools/sheets/place_order_tool.py

import os
import requests
from typing import List
from pydantic.v1 import BaseModel, Field, EmailStr
from langchain.tools import tool

BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

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
    FINALIZE a *paid* order.

    What this does (server side via /api/inventory/finalize):
    - Validates stock in Sheets (case-insensitive match, so 'buttermilk' == 'Buttermilk')
    - Decrements quantity & increments orders_count
    - Sends receipt email to customer + copy/low-stock alert to owner
    - Clears the user's cart for this session_id so old items won't get re-charged

    The tool should be called ONLY AFTER:
    1. stripe_checkout_status_tool confirms status == 'paid'
    2. you asked the user for their email
    3. you pass ONLY the items they just paid for
    """

    payload = {
        "session_id": session_id,
        "customer_email": customer_email,
        "items": [{"name": i.name, "qty": i.qty} for i in items],
    }

    # Hit the new finalize endpoint (single source of truth)
    url = f"{BASE}/api/inventory/finalize"
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
            "order": data,
            "status": "CONFIRMED",
            "cart_cleared": True,
            "email_sent": True,   # finalize endpoint is responsible for emailing
        }

    # Failure (e.g. out-of-stock race condition)
    return {
        "error": "finalize failed",
        "status_code": r.status_code,
        "response": data,
        "cart_cleared": False,
        "email_sent": False,
    }
