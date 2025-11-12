import requests


import os
from langchain_core.tools import tool
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Global variable for Apple Pay session ID (consider using a persistent store in production)
apple_pay_session_id = ""

@tool
def generate_apple_pay_link(amount_dollars: float, product_name: str = "Chai Corner Order") -> str:
    """
    Generates an Apple Pay payment link using Stripe Checkout.
    
    Args:
        amount_dollars (float): The payment amount in dollars
        product_name (str): The name of the product/order (default: "Chai Corner Order")
    
    Returns:
        str: Apple Pay payment link or error message
    """
    try:
        # Try to import stripe dynamically
        import stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        if not stripe.api_key:
            return "https://checkout.stripe.com/demo-apple-pay-link"
        
        amount_cents = int(amount_dollars * 100)
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount_cents,
                    "product_data": {
                        "name": product_name,
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://lightningminds.com/success",
            cancel_url="https://lightningminds.com/cancel",
        )
        
        # Save session ID globally for potential future use
        global apple_pay_session_id
        apple_pay_session_id = session.id
        
        # Print terminal message for debugging
        print(f"\n💳 Apple Pay Link Generated: {session.url}\n")
        
        # Return just the URL
        return session.url
        
    except ImportError:
        print("Stripe not available, using demo link")
        return "https://checkout.stripe.com/demo-apple-pay-link"
    except Exception as e:
        print(f"Apple Pay Error: {str(e)}")
        return "https://checkout.stripe.com/demo-apple-pay-link"

@tool
def get_apple_pay_session_status(session_id: Optional[str] = None) -> str:
    """
    Retrieves the status of an Apple Pay (Stripe) checkout session.
    
    Args:
        session_id (str, optional): The Stripe session ID. If not provided, uses the last generated session.
    
    Returns:
        str: Session status information
    """
    try:
        import stripe
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        if not stripe.api_key:
            return "Error: Stripe API key not configured."
        
        # Use provided session_id or fall back to global one
        session_to_check = session_id or apple_pay_session_id
        
        if not session_to_check:
            return "No Apple Pay session ID available. Please generate a payment link first."
        
        session = stripe.checkout.Session.retrieve(session_to_check)
        
        status_info = {
            "id": session.id,
            "status": session.status,
            "payment_status": session.payment_status,
            "amount_total": session.amount_total / 100 if session.amount_total else 0,  # Convert cents to dollars
            "currency": session.currency,
            "url": session.url
        }
        
        return f"Apple Pay Session Status: {status_info['status']}, Payment Status: {status_info['payment_status']}, Amount: ${status_info['amount_total']}"
        
    except Exception as e:
        return f"Error retrieving Apple Pay session status: {str(e)}"

@tool
def save_apple_pay_session_id(session_id: str) -> str:
    """
    Saves an Apple Pay session ID for later reference.
    
    Args:
        session_id (str): The Stripe session ID to save
    
    Returns:
        str: Confirmation message
    """
    global apple_pay_session_id
    apple_pay_session_id = session_id
    return f"Apple Pay session ID '{session_id}' has been saved successfully."

@tool
def get_apple_pay_session_id() -> str:
    """
    Retrieves the currently saved Apple Pay session ID.
    
    Returns:
        str: The saved session ID or a message if none is saved
    """
    if apple_pay_session_id:
        return apple_pay_session_id
    else:
        return "No Apple Pay session ID has been saved yet."

# List of Apple Pay tools to be imported by tool_config
apple_pay_tools = [
    generate_apple_pay_link,
    get_apple_pay_session_status,
    save_apple_pay_session_id,
    get_apple_pay_session_id
]