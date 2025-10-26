import os
import logging
import sys
from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
from state.session import get_websocket, set_stripe_order_id, set_paypal_order_id

import stripe
import paypalrestsdk

# NEW: instead of HTTP requests.get(...), we import the sheet DAL directly
from integrations.google_sheets.sheets_dal import get_menu

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

try:
    paypalrestsdk.configure({
        "mode": os.getenv("PAYPAL_MODE", "sandbox"),
        "client_id": os.getenv("PAYPAL_CLIENT_ID"),
        "client_secret": os.getenv("PAYPAL_CLIENT_SECRET"),
    })
    print("PayPal SDK configured successfully.")
except Exception as e:
    print(f"Error configuring PayPal SDK: {e}")


class CartItem(BaseModel):
    name: str = Field(..., description="Exact product name from the menu.")
    quantity: int = Field(..., gt=0, description="Quantity requested.")
    price: float = Field(..., gt=0, description="Unit price that the agent thinks is correct.")

class TriggerPaymentArgs(BaseModel):
    cart_items: List[CartItem] = Field(..., description="Items to charge for right now only.")
    session_id: str = Field(..., description="Session ID for this user/chat.")


def _fetch_menu_direct() -> List[Dict[str, Any]]:
    """
    Directly call the Sheets DAL instead of hitting our own HTTP endpoint.
    This avoids the 127.0.0.1 timeout / re-entrancy problem.
    get_menu() already returns a list like:
    [
      { "name": "Madras Coffee", "price": 20.0, "quantity": 6, ... },
      ...
    ]
    """
    items = get_menu()
    # routers.inventory.menu() wraps this as {"items": get_menu()}
    # We just want that list.
    return items


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

    # 1. get fresh menu directly from Sheets (no HTTP call)
    try:
        menu_items = _fetch_menu_direct()
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
            ui_mode="embedded",
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
    print(f"\n💳 Apple Pay Link Generated: {checkout_session.url}\n")

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
