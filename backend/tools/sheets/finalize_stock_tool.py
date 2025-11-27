from pydantic.v1 import BaseModel, Field
from typing import List
from langchain_core.tools import tool
import requests
import os

BASE = os.getenv("API_BASE","http://localhost:8080")
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
    """
    payload = {"session_id": session_id, "items": [{"name": i.name, "qty": i.qty} for i in items]}
    url = f"{BASE}/api/inventory/finalize_stock"
    try:
        r = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return {"error": "Request timeout", "message": f"Timed out after {REQUEST_TIMEOUT}s", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url, "payload": payload}
