import os
import logging
import sys
from typing import List
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import BaseModel, Field
#from pydantic import BaseModel, Field
from state.session import get_websocket
import stripe
from state.session import set_stripe_order_id, set_paypal_order_id

import paypalrestsdk

try:
    paypalrestsdk.configure({
        "mode": os.getenv("PAYPAL_MODE", "sandbox"),  # "sandbox" or "live"
        "client_id": os.getenv("PAYPAL_CLIENT_ID"),
        "client_secret": os.getenv("PAYPAL_CLIENT_SECRET")
    })
    print("PayPal SDK configured successfully.")
except Exception as e:
    print(f"Error configuring PayPal SDK: {e}")

# --- Environment Setup ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

# --- Pydantic Models ---
class CartItem(BaseModel):
    name: str = Field(..., description="The full name of the product.")
    quantity: int = Field(..., description="How many units of the product are in the cart.")
    price: float = Field(..., description="The price for a single unit of the product.")

class TriggerPaymentArgs(BaseModel):
    cart_items: List[CartItem] = Field(..., description="A complete list of items to be purchased.")
    session_id: str = Field(..., description="Session ID.")



@tool(args_schema=TriggerPaymentArgs)
async def trigger_payment(cart_items: List[CartItem], session_id: str):
    """
    Creates a Stripe PaymentIntent and sends its client_secret to the user's
    WebSocket to initialize an embedded payment form.
    """
    logging.info(f"Attempting to create PaymentIntent for session_id: {session_id}")

    if not stripe.api_key:
        logging.error("Stripe API key is not configured.")
        return "Error: Payment processor is not configured. Please set the STRIPE_API_KEY environment variable."

    ws = get_websocket(session_id)
    if not ws:
        logging.warning(f"No active WebSocket for session {session_id}.")
        return "Something went wrong. No active WebSocket for this session."


    try:
        # # Format line items for the Checkout Session API
        # items = []
        # total = 0
        # for item in cart_items:
        #     items.append({
        #         'name': item.name,
        #         'price': f"{item.price:.2f}",
        #         'currency': 'USD',
        #         'quantity': item.quantity
        #     })
        #     total += item.price
            
            
            
        # payment = paypalrestsdk.Payment({
        #     "intent": "sale",  # The intent of the payment (sale, authorize, or order)
        #     "payer": {
        #         "payment_method": "paypal"
        #     },
        #     "redirect_urls": {
        #         # URLs where the user will be redirected after payment approval or cancellation
        #         "return_url": "https://lightningminds.com/success",
        #         "cancel_url": "https://lightningminds.com/cancel"
        #     },
        #     "transactions": [{
        #         "item_list": {
        #             "items": items
        #         },
        #         "amount": {
        #             "total": f"{total:.2f}",
        #             "currency": "USD"
        #         },
        #         "description": "Chai Corner Order."
        #     }]
        # })
        # approval_url = ''
        # if payment.create():
        #     print(f"Payment created successfully. ID: {payment.id}")
            
        #     logging.info(f"PAYPAL ID: {payment.id}")
        #     set_paypal_order_id(payment.id)
        #     # Find the approval URL in the links provided by the PayPal response
        #     for link in payment.links:
        #         if link.rel == "approval_url":
        #             approval_url = str(link.href)
        #             # return {"approval_url": approval_url, "payment_id": payment.id}
        #     # If no approval URL is found, raise an error
        #     # raise Exception(status_code=500, detail="Could not find PayPal approval URL.")
        # else:
        #     # If the payment creation fails, log the error and raise an exception
        #     print(f"Error creating payment: {payment.error}")
        #     # raise Exception(status_code=400, detail=payment.error)
        
        # Format line items for the Checkout Session API
        line_items = []
        for item in cart_items:
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': item.name,
                    },
                    'unit_amount': int(item.price * 100),
                },
                'quantity': item.quantity,
            })
            
        
        logging.info(f"Line items: {line_items}")

        checkout_session = stripe.checkout.Session.create(
            line_items=line_items,
            mode='payment',
            ui_mode='embedded',
            # billing_address_collection='auto',
            billing_address_collection='required',
            # Return_url for post-payment redirects
            # return_url=f'http://localhost:8080'
            redirect_on_completion='never'
        )
        
        logging.info(f"Stripe Checkout Session created: {checkout_session.id}")
        set_stripe_order_id(session_id, checkout_session.id) # Save the Stripe checkout order ID for later
        
        print(f"\n💳 Apple Pay Link Generated: {checkout_session.url}\n")

        message = {
            "type": "payment_intent_created",
            "client_secret": checkout_session.client_secret,
            # "paypal_order_id": payment.id
        }
        await ws.send_json(message)

        # The tool returns a confirmation that the payment process has been initiated.
        return f"Payment form initialized for session {session_id}. Let user know, 'The payment form has been initialized.'. DO NOT ask customer to let you know once they are finished paying"

    except Exception as e:
        logging.error(f"Failed to create Stripe PaymentIntent: {e}")
        return f"Error: Could not create a payment session. Details: {e}"


trigger_payment_tool = trigger_payment