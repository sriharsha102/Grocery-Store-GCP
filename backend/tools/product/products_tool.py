# tools/product/products_tool.py
import logging
from langchain_core.tools import tool
from backend.integrations.google_sheets.sheets_dal import get_menu

log = logging.getLogger(__name__)

def fetch_menu(category: str | None = None) -> dict:
    """
    Plain helper. Returns {"items":[{"name":..., "price": ..., ...}, ...]} or {"error":...}
    Calls Google Sheets directly instead of making HTTP requests.
    """
    try:
        items = get_menu(tab=category)
        return {"items": items}
    except Exception as e:
        log.exception("fetch_menu failed")
        return {"error": f"{type(e).__name__}: {e}"}

@tool("get_products")
def get_products(category: str | None = None) -> dict:
    """
    LangChain tool that returns the live menu (names + prices) from Google Sheets.
    """
    return fetch_menu(category=category)

# export the tool instance for your registry
products_tool = get_products
