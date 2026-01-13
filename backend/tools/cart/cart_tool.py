from collections import defaultdict
from langchain_core.tools import tool
import logging
import time
from typing import Dict
from backend.integrations.google_sheets.sheets_dal import get_menu, get_menu_for_tabs, get_tab_titles
from backend.state.session import get_active_tabs, get_weight_cache, is_awaiting_email, set_weight_cache

WEIGHT_CACHE_TTL_SECONDS = 300

# This dictionary will store cart objects, with session IDs as keys.
# Structure: { "session_id_1": {"item_1": qty, "item_2": qty}, "session_id_2": ... }
# WARNING: This is an in-memory store. It will be cleared if the server restarts.
# Session cleanup is handled in backend.main via cleanup_session()

log = logging.getLogger(__name__)

session_carts: Dict[str, defaultdict] = {}

def _guard_if_awaiting_email(session_id: str) -> str | None:
    if is_awaiting_email(session_id):
        return "Payment is confirmed. Please provide your email address to receive the receipt."
    return None

def _build_weight_lookup(session_id: str) -> Dict[str, str]:
    active_tabs = get_active_tabs(session_id)
    if not active_tabs:
        try:
            active_tabs = get_tab_titles()
        except Exception:
            active_tabs = []

    weight_lookup: Dict[str, str] = {}
    if active_tabs:
        try:
            tab_results = get_menu_for_tabs(active_tabs)
            for items in tab_results.values():
                for item in items:
                    name = str(item.get("name", "")).strip().lower()
                    if not name:
                        continue
                    weight = str(item.get("weight", "")).strip()
                    if weight:
                        weight_lookup[name] = weight
            return weight_lookup
        except Exception:
            weight_lookup = {}

    try:
        items = get_menu()
    except Exception:
        return {}

    for item in items:
        name = str(item.get("name", "")).strip().lower()
        if not name:
            continue
        weight = str(item.get("weight", "")).strip()
        if weight:
            weight_lookup[name] = weight
    return weight_lookup


def get_cart_for_session(session_id: str) -> defaultdict:
    """Retrieves or creates a cart object for a given session ID."""
    if session_id not in session_carts:
        session_carts[session_id] = defaultdict(int)
    return session_carts[session_id]

def cleanup_cart_for_session(session_id: str) -> None:
    """Clean up cart data for expired session. Called by session cleanup thread."""
    if session_id in session_carts:
        session_carts.pop(session_id, None)
        log.debug(f"Cleaned up cart for session: {session_id}")

@tool
def add_to_cart(session_id: str, item_name: str, quantity: int) -> str:
    """
    Adds a specified quantity of an item to the shopping cart.
    """
    blocked = _guard_if_awaiting_email(session_id)
    if blocked:
        return blocked
    if quantity <= 0:
        return "Quantity must be a positive integer to add to cart."
    
    cart = get_cart_for_session(session_id)
    
    item_name = item_name.lower()
    
    cart[item_name] += quantity
    log.info(f"--- TOOL CALL: add_to_cart ---")
    log.info(f"Cart state: {dict(cart)}")
    return f"Added {quantity} x {item_name} to the cart. Current quantity: {cart[item_name]}."

@tool
def remove_from_cart(session_id: str, item_name: str, quantity: int) -> str:
    """
    Removes a specified quantity of an item from the shopping cart.
    """
    blocked = _guard_if_awaiting_email(session_id)
    if blocked:
        return blocked
    if quantity <= 0:
        return "Quantity must be a positive integer to remove from cart."
    
    cart = get_cart_for_session(session_id)
    
    item_name = item_name.lower()
    
    if item_name not in cart or cart[item_name] == 0:
        return f"{item_name} is not in the cart."

    current_quantity = cart[item_name]
    if quantity >= current_quantity:
        del cart[item_name]
        log.info(f"--- TOOL CALL: remove_from_cart ---")
        log.info(f"Cart state: {dict(cart)}")
        return f"Removed all {current_quantity} x {item_name} from the cart."
    else:
        cart[item_name] -= quantity
        log.info(f"--- TOOL CALL: remove_from_cart ---")
        log.info(f"Cart state: {dict(cart)}")
        return f"Removed {quantity} x {item_name} from the cart. Remaining quantity: {cart[item_name]}."

@tool
def view_cart(session_id: str) -> str:
    """
    Displays the current contents of the shopping cart.
    """
    blocked = _guard_if_awaiting_email(session_id)
    if blocked:
        return blocked
    cart = get_cart_for_session(session_id)
    
    if not cart:
        log.info(f"--- TOOL CALL: view_cart --- Cart: Empty")
        return "The cart is currently empty."

    cached_weights, cached_ts = get_weight_cache(session_id)
    if cached_weights and (time.time() - cached_ts) < WEIGHT_CACHE_TTL_SECONDS:
        weight_lookup = cached_weights
    else:
        weight_lookup = _build_weight_lookup(session_id)
        set_weight_cache(session_id, weight_lookup)
    cart_items = []
    for item, qty in cart.items():
        weight = weight_lookup.get(item, "")
        if weight:
            cart_items.append(f"{qty} x {item} ({weight})")
        else:
            cart_items.append(f"{qty} x {item}")
    cart_summary = ", ".join(cart_items)
    log.info(f"--- TOOL CALL: view_cart --- Cart: {cart_summary}")
    return f"The cart contains: {cart_summary}."

@tool
def clear_cart(session_id: str) -> str:
    """
    Empties the shopping cart.
    """
    blocked = _guard_if_awaiting_email(session_id)
    if blocked:
        return blocked
    cart = get_cart_for_session(session_id)
    
    cart.clear()
    log.info(f"--- TOOL CALL: clear_cart --- Cart: Cleared")
    return "The cart has been cleared."

cart_tools = [add_to_cart, remove_from_cart, view_cart, clear_cart]
