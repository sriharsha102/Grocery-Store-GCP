from pydantic.v1 import BaseModel, Field
from typing import List, Dict
from langchain_core.tools import tool
import logging
import os
import time
import requests
import uuid
from collections import defaultdict
from backend.integrations.google_sheets.sheets_dal import decrement_quantities
from backend.state.session import get_item_tab_mapping

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

def _resolve_item_key(name: str, item_tab_mapping: dict) -> str:
    """
    Match a potentially truncated item name to its full key in item_tab_mapping.
    e.g. 'lx cumin seed' → 'lx cumin seed 400gm'
    """
    key = name.strip().lower()
    if key in item_tab_mapping:
        return key
    # starts-with: handles LLM stripping weight suffixes
    for mapped_key in item_tab_mapping:
        if mapped_key.startswith(key):
            log.info("Resolved item '%s' → '%s'", key, mapped_key)
            return mapped_key
    # contains: last resort
    for mapped_key in item_tab_mapping:
        if key in mapped_key:
            log.info("Resolved item '%s' → '%s' (contains match)", key, mapped_key)
            return mapped_key
    return key  # no match — will fall through to Inventory fallback

@tool("finalize_stock", args_schema=FinalizeStockArgs)
def finalize_stock(session_id: str, items: List[OrderItem]) -> dict:
    """
    Step 1: Run immediately after Stripe confirms 'paid'.
    Decrements stock, updates order count, and triggers low-stock alerts.
    Supports multi-tab inventory by grouping items by tab and decrementing separately.
    """
    if not items:
        return {"error": "No items provided"}

    # Get the item-to-tab mapping from session state
    item_tab_mapping = get_item_tab_mapping(session_id)
    log.info(f"Item-to-tab mapping for session {session_id}: {item_tab_mapping}")

    # Group items by tab
    items_by_tab: Dict[str, List[tuple]] = defaultdict(list)
    unknown_tab_items = []

    for item in items:
        item_key = _resolve_item_key(item.name, item_tab_mapping)
        tab_name = item_tab_mapping.get(item_key)

        if tab_name:
            items_by_tab[tab_name].append((item.name, item.qty))
        else:
            # If no mapping found, try default "Inventory" tab as fallback
            log.warning(f"No tab mapping found for item '{item.name}', using default 'Inventory' tab")
            unknown_tab_items.append((item.name, item.qty))

    # Add unknown items to default "Inventory" tab
    if unknown_tab_items:
        items_by_tab["Inventory"].extend(unknown_tab_items)

    log.info(f"Grouped items by tab: {dict(items_by_tab)}")

    # Decrement quantities for each tab
    all_updated = []
    all_out_of_stock = []

    for tab_name, tab_items in items_by_tab.items():
        try:
            log.info(f"Decrementing {len(tab_items)} items from tab '{tab_name}'")
            result = decrement_quantities(tab_items, tab=tab_name)

            # Collect results
            if result.get("updated"):
                all_updated.extend(result["updated"])

            if result.get("out_of_stock"):
                all_out_of_stock.extend(result["out_of_stock"])

        except Exception as e:
            log.exception(f"finalize_stock: decrement_quantities failed for tab '{tab_name}'")
            # Mark all items from this tab as failed
            for item_name, _ in tab_items:
                all_out_of_stock.append({
                    "name": item_name,
                    "reason": f"Sheet update failed for tab '{tab_name}': {e}"
                })

    # Handle out-of-stock race condition
    if all_out_of_stock:
        return {
            "error": "Some items unavailable after payment",
            "details": all_out_of_stock
        }

    order_id = f"ORD-{int(time.time())}"

    # Send low-stock alerts if configured
    low_stock_sent = False
    low_debug = {}
    if EMAIL_MODE == "APPS_SCRIPT" and APPS_SCRIPT_EMAIL_URL and EMAIL_WEBHOOK_SECRET:
        low_items = [u for u in all_updated if u.get("low_stock")]

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
        "updated": all_updated,
    }
