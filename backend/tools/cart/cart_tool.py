from collections import defaultdict
from langchain_core.tools import tool
import logging

# This dictionary will store cart objects, with session IDs as keys.
# Structure: { "session_id_1": {"item_1": qty, "item_2": qty}, "session_id_2": ... }
# WARNING: This is an in-memory store. It will be cleared if the server restarts.

log = logging.getLogger(__name__)

session_carts = {}

def get_cart_for_session(session_id: str) -> defaultdict:
    """Retrieves or creates a cart object for a given session ID."""
    if session_id not in session_carts:
        session_carts[session_id] = defaultdict(int)
    return session_carts[session_id]

@tool
def add_to_cart(session_id: str, item_name: str, quantity: int) -> str:
    """
    Adds a specified quantity of an item to the shopping cart.
    """
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
    cart = get_cart_for_session(session_id)
    
    if not cart:
        log.info(f"--- TOOL CALL: view_cart --- Cart: Empty")
        return "The cart is currently empty."

    cart_items = [f"{qty} x {item}" for item, qty in cart.items()]
    cart_summary = ", ".join(cart_items)
    log.info(f"--- TOOL CALL: view_cart --- Cart: {cart_summary}")
    return f"The cart contains: {cart_summary}."

@tool
def clear_cart(session_id: str) -> str:
    """
    Empties the shopping cart.
    """
    cart = get_cart_for_session(session_id)
    
    cart.clear()
    log.info(f"--- TOOL CALL: clear_cart --- Cart: Cleared")
    return "The cart has been cleared."

cart_tools = [add_to_cart, remove_from_cart, view_cart, clear_cart]