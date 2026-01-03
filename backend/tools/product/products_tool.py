# tools/product/products_tool.py
import os, requests
from langchain_core.tools import tool

#BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
BASE = "http://localhost:8080"

def fetch_menu(category: str | None = None) -> dict:
    """
    Plain helper. Returns {"items":[{"name":..., "price": ..., ...}, ...]} or {"error":...}
    """
    try:
        params = {"category": category} if category else None
        r = requests.get(f"{BASE}/api/inventory/menu", params=params, timeout=8)
        if r.status_code != 200:
            return {"error": r.text}
        return r.json()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

@tool("get_products")
def get_products(category: str | None = None) -> dict:
    """
    LangChain tool that returns the live menu (names + prices) from Google Sheets.
    """
    return fetch_menu(category=category)

# export the tool instance for your registry
products_tool = get_products
