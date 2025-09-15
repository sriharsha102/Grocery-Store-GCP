from langchain_core.tools import tool
from tools.quickbooks.quickbooks_wrapper import QuickBooksWrapper
import json
from state.session import is_guest

@tool
def check_guest_tool(session_id: str) -> bool:
    """
    Checks if the current customer is a guest.
    """

    try:
        if (is_guest(session_id)):
            return f"The current customer is a guest"
        else:
            return f"The current customer is not a guest. They are an existing customer."
    except Exception as e:
        # If there's an error retrieving the customer, assume they're not a guest
        print(f"Error checking customer status: {e}")
        return False