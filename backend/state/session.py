from typing import Dict
from fastapi import WebSocket
from state.chat_state import ChatState

session_state: Dict[str, ChatState] = {} # [session_id, ChatState]

### State ###

def get_state(session_id: str) -> ChatState:
    if session_id not in session_state:
        session_state[session_id] = ChatState()
    return session_state[session_id]

def save_state(session_id:str, state: ChatState) -> None:
    session_state[session_id] = state
    

### Customer ###

def set_customer(session_id: str, customer_id: str | None, *, is_guest: bool | None = None) -> None:
    s = get_state(session_id)
    s.customer_id = customer_id
    if is_guest is not None:
        s.is_guest = is_guest
    save_state(session_id, s)
    
def get_customer(session_id: str):
    return get_state(session_id).customer_id

def mark_guest(session_id: str) -> None:
    s = get_state(session_id)
    s.is_guest = True
    save_state(session_id, s)

def promote_to_real(session_id: str) -> None:
    s = get_state(session_id)
    s.is_guest = False
    save_state(session_id, s)
    
def is_guest(session_id: str) -> bool:
    s = get_state(session_id)
    return s.is_guest


### Cart ###

def get_cart(session_id: str):
    return get_state(session_id).cart

def add_to_cart(session_id: str, item_name: str, quantity: int):
    cart = get_state(session_id).cart
    cart[item_name] += quantity
    
def remove_x_from_cart(session_id: str, item_name: str, quantity: int):
    cart = get_state(session_id).cart
    cart[item_name] -= quantity

def remove_completely_from_cart(session_id: str, item_name: str):
    cart = get_state(session_id).cart
    del cart[item_name]
    

### WebSocket ###

def set_websocket(session_id: str, ws: WebSocket):
    s = get_state(session_id)
    s.websocket = ws
    save_state(session_id, s)

def get_websocket(session_id:str):
    return get_state(session_id).websocket


### Stripe Order ###

def set_stripe_order_id(session_id: str, stripe_order_id: str):
    s = get_state(session_id)
    s.stripe_order_id = stripe_order_id 
    save_state(session_id, s)

def get_stripe_order_id(session_id:str):
    return get_state(session_id).stripe_order_id

### PayPal Order ###

def set_paypal_order_id(session_id: str, paypal_order_id: str):
    s = get_state(session_id)
    s.paypal_order_id = paypal_order_id 
    save_state(session_id, s)

def get_paypal_order_id(session_id:str):
    return get_state(session_id).paypal_order_id
