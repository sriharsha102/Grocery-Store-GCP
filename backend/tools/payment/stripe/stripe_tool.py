import os
import stripe
from langchain_core.tools import tool
from pydantic import BaseModel
from backend.state.session import get_stripe_order_id

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class CheckoutSessionRequest(BaseModel):
    """Request model for checking a checkout session."""
    session_id: str
    
@tool("stripe_checkout_status_tool", return_direct=False)
def stripe_checkout_status_tool(session_id: str) -> str:
    """
    Checks the status of a Stripe Checkout Session.

    Args:
        session_id: The UUID string of the session of the user. Not the Stripe Session ID.

    Returns:
        A string indicating the status of the checkout session.
    """
    if not stripe.api_key:
        return "Error: Stripe API key is not configured."

    try:
        order_id = get_stripe_order_id(session_id)
        order = stripe.checkout.Session.retrieve(order_id)
        return (
            # f"Checkout Session '{order.id}' status: \n"
            f"Payment Status: {order.payment_status}."
            # f"  - Session Status: {order.status}\n"
            # f"  - Customer Email: {order.customer_details.email if order.customer_details else 'N/A'}"
        )
    except stripe.error.StripeError as e:
        return f"Error retrieving checkout session: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


