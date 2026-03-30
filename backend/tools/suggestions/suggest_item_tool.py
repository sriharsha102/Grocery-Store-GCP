import os
import logging
from langchain.tools import tool
from backend.integrations.gmail.email_sender import send_item_suggestion

logger = logging.getLogger(__name__)

@tool("suggest_item")
def suggest_item_tool(item_suggestion: str) -> str:
    """
    Use this tool when a customer wants to suggest an item to be added to the store.
    Input: a plain-text description of the item the customer is suggesting (e.g. 'samosa', 'mango pickle 500g').
    Sends an email notification to the store owner with the suggestion.
    """
    owner_email = os.getenv("OWNER_EMAIL")
    if not owner_email:
        return "Could not send suggestion: owner email is not configured."
    try:
        send_item_suggestion(owner_email=owner_email, item_suggestion=item_suggestion.strip())
        return f"Suggestion sent to the store owner: '{item_suggestion.strip()}'. Thank you for your feedback!"
    except Exception as e:
        logger.error(f"Failed to send item suggestion: {e}")
        return "Sorry, I couldn't send your suggestion right now. Please try again later."
