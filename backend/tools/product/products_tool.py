# tools/product/products_tool.py
import logging
from langchain_core.tools import tool
from backend.integrations.google_sheets.sheets_dal import get_menu
from backend.state.session import add_active_tab

log = logging.getLogger(__name__)

def fetch_menu(category: str | None = None, session_id: str | None = None) -> dict:
    """
    Plain helper. Returns {"items":[{"name":..., "price": ..., ...}, ...]} or {"error":...}
    Calls Google Sheets directly instead of making HTTP requests.
    """
    try:
        items = get_menu(tab=category)
        if session_id and category:
            add_active_tab(session_id, category)
        return {"items": items}
    except Exception as e:
        log.exception("fetch_menu failed")
        return {"error": f"{type(e).__name__}: {e}"}

@tool("get_products")
def get_products(category: str | None = None, session_id: str | None = None) -> dict:
    """
    LangChain tool that returns the live menu (names + prices) from Google Sheets.
    Pass session_id to remember active category tabs.
    """
    return fetch_menu(category=category, session_id=session_id)

# export the tool instance for your registry
products_tool = get_products
