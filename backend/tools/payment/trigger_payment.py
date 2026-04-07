import os
import logging
import sys
from typing import List, Dict, Any, Tuple
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from backend.integrations.google_sheets.sheets_dal import get_menu, get_menu_for_tabs, get_tab_titles
from backend.state.session import get_active_tabs
from backend.state.session import get_websocket, set_stripe_order_id, set_item_tab_mapping
import stripe

# Import sheet DAL functions
from backend.integrations.google_sheets.sheets_dal import get_menu, get_tab_titles

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


class CartItem(BaseModel):
    name: str = Field(..., description="Exact product name from the menu.")
    quantity: int = Field(..., gt=0, description="Quantity requested.")
    price: float = Field(..., gt=0, description="Unit price that the agent thinks is correct.")

class TriggerPaymentArgs(BaseModel):
    cart_items: List[CartItem] = Field(..., description="Items to charge for right now only.")
    session_id: str = Field(..., description="Session ID for this user/chat.")


def _fetch_menu_direct(
    tabs: List[str] | None = None,
    required_items: List[str] | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Fetch menu from ALL tabs and return combined items with tab mapping.

    Returns:
        Tuple of (all_items, item_to_tab_mapping)
        - all_items: List of all items from all tabs
        - item_to_tab_mapping: Dict mapping item_name_lowercase -> tab_name
    """
    tab_titles = tabs or []
    if not tab_titles:
        try:
            # Get all tab titles
            tab_titles = get_tab_titles()
            log.info(f"Found {len(tab_titles)} tabs: {tab_titles}")

        except Exception as e:
            log.warning(f"Failed to get tab titles, falling back to default tab: {e}")
            # Fallback to default "Inventory" tab if get_tab_titles fails
            items = get_menu()
            item_to_tab = {item["name"].strip().lower(): "Inventory" for item in items}
            return items, item_to_tab

    all_items: List[Dict[str, Any]] = []
    item_to_tab_mapping: Dict[str, str] = {}
    try:
        tab_results = get_menu_for_tabs(tab_titles)
    except Exception as e:
        log.warning("Batch fetch failed, falling back to per-tab reads: %s", e)
        tab_results = {}
        for tab_name in tab_titles:
            try:
                tab_results[tab_name] = get_menu(tab=tab_name)
            except Exception as exc:
                log.warning("Failed to fetch from tab '%s': %s", tab_name, exc)
                tab_results[tab_name] = []
    for tab_name, tab_items in tab_results.items():
        log.info(f"Fetched {len(tab_items)} items from tab '{tab_name}'")
        for item in tab_items:
            item_key = item["name"].strip().lower()
            # If item exists in multiple tabs, the last one wins
            item_to_tab_mapping[item_key] = tab_name
            all_items.append(item)

    if required_items:
        missing = [name for name in required_items if name not in item_to_tab_mapping]
        if missing and tabs:
            log.info(
                "Missing items in active tabs %s, falling back to all tabs: %s",
                tabs,
                missing,
            )
            return _fetch_menu_direct(tabs=None, required_items=None)

    log.info(f"Total items fetched from tabs: {len(all_items)}")
    return all_items, item_to_tab_mapping

def _validate_cart_against_sheet(
    cart_items: List[CartItem],
    menu_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Check each requested item against live sheet data:
    - item exists (case-insensitive match)
    - enough stock
    - price didn't change
    """
    problems = []
    sheet_lookup = {row["name"].strip().lower(): row for row in menu_items}

    for line in cart_items:
        wanted_key = line.name.strip().lower()
        sheet_row = sheet_lookup.get(wanted_key)
        if not sheet_row:
            problems.append({
                "name": line.name,
                "reason": "not_found_in_menu"
            })
            continue

        sheet_qty = int(sheet_row.get("quantity", 0))
        sheet_price = float(sheet_row.get("price", 0))

        if line.quantity > sheet_qty:
            problems.append({
                "name": line.name,
                "reason": f"only {sheet_qty} left"
            })

        # protect against stale price in agent memory
        if float(line.price) != sheet_price:
            problems.append({
                "name": line.name,
                "reason": f"price_changed_to_{sheet_price}"
            })

    if problems:
        return {"ok": False, "problems": problems}
    return {"ok": True}


@tool(args_schema=TriggerPaymentArgs)
async def trigger_payment(cart_items: List[CartItem], session_id: str):
    """
    1. Pull live sheet inventory/prices.
    2. Validate the cart (stock + price).
    3. If OK, create Stripe embedded checkout session and send client_secret
       over the session websocket.
    4. If not OK, DO NOT create checkout; return an 'unavailable' error
       so the agent can tell the user and stop.
    """

    log.info("trigger_payment called for session_id=%s", session_id)

    if not stripe.api_key:
        log.error("Stripe API key is not configured.")
        return {
            "error": "stripe_not_configured",
            "message": "Payment processor is not configured. Missing STRIPE_SECRET_KEY.",
        }

    ws = get_websocket(session_id)
    if not ws:
        log.warning("No active WebSocket for session %s.", session_id)
        return {
            "error": "no_websocket",
            "message": "No active WebSocket for this session. Cannot initialize payment UI.",
        }

    # 1. get fresh menu directly from Sheets
    try:
        active_tabs = get_active_tabs(session_id)
        required_items = [item.name.strip().lower() for item in cart_items]
        menu_items, item_tab_mapping = _fetch_menu_direct(
            tabs=active_tabs,
            required_items=required_items,
        )
        # Store the item-to-tab mapping for later use in finalize_stock
        set_item_tab_mapping(session_id, item_tab_mapping)
    except Exception as e:
        log.exception("Failed to read menu from Sheets before checkout.")
        return {
            "error": "menu_fetch_failed",
            "message": f"Could not confirm stock/price before payment: {e}",
        }

    # 2. validate against sheet
    check = _validate_cart_against_sheet(cart_items, menu_items)
    if not check["ok"]:
        log.warning(
            "Stock/price validation failed for session %s: %s",
            session_id,
            check["problems"],
        )
        return {
            "error": "unavailable",
            "details": check["problems"],
        }

    # 3. Build Stripe line_items
    line_items = []
    for item in cart_items:
        amount_cents = int(round(item.price * 100))
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": item.name,
                },
                "unit_amount": amount_cents,
            },
            "quantity": item.quantity,
        })
    log.info("Line items for Stripe: %s", line_items)

    # 4. Create Stripe embedded Checkout Session
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=line_items,
            mode="payment",
            ui_mode="embedded_page",
            billing_address_collection="required",
            redirect_on_completion="never",
            metadata={"chat_session_id": session_id},
        )
    except Exception as e:
        log.exception("Stripe Checkout Session creation failed.")
        return {
            "error": "stripe_error",
            "message": f"Could not create Stripe Checkout session: {e}",
        }

    log.info("Stripe Checkout Session created: %s", checkout_session.id)

    # save checkout_session.id for stripe_checkout_status_tool later
    set_stripe_order_id(session_id, checkout_session.id)

    # 5. send client_secret back over WS so frontend can render the embedded checkout
    try:
        message = {
            "type": "payment_intent_created",
            "client_secret": checkout_session.client_secret,
        }
        await ws.send_json(message)
    except Exception as e:
        log.exception("Failed to send client_secret over websocket.")
        return {
            "error": "websocket_send_failed",
            "message": f"Payment created, but failed to notify client: {e}",
            "stripe_session_id": checkout_session.id,
        }

    # 6. final LLM text
    return (
        "Payment form has been initialized. Tell the user: "
        "'The payment form has been initialized. Please complete your payment.' "
        "Do NOT ask them to tell you when they're done."
    )


trigger_payment_tool = trigger_payment
