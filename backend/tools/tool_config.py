from langchain.agents import Tool
import logging
from backend.tools.sheets.get_top_sellers_tool import get_top_sellers
from backend.tools.sheets.place_order_tool import place_order
from backend.tools.sheets.finalize_stock_tool import finalize_stock
from backend.tools.cart.cart_tool import cart_tools

from backend.tools.product.products_tool import products_tool
from backend.tools.product.summary_tool import generate_summary

from backend.tools.payment.applepay.apple_pay_tool import apple_pay_tools
from backend.tools.payment.trigger_payment import trigger_payment_tool
from backend.tools.payment.stripe.stripe_tool import stripe_checkout_status_tool

logger = logging.getLogger(__name__)

def get_all_tools() -> list[Tool]:
    """
    Gathers and returns all tool instances for the LangChain agent.
    """
    tools = (
        cart_tools
        + [
            products_tool,
            generate_summary,
            trigger_payment_tool,
            stripe_checkout_status_tool,
            get_top_sellers,   # ← NEW (reads top 5 from Sheets)
            finalize_stock,
            place_order       # ← NEW (decrement Sheet + send emails)
        ]
        # + apple_pay_tools
        # + get_paypal_tools()
    )
    logger.info(f"Successfully loaded {len(tools)} tools for the agent.")
    return tools
