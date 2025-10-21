# tools/product/products_tool.py
import os, requests
from langchain_core.tools import tool

BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

def fetch_menu() -> dict:
    """
    Plain helper. Returns {"items":[{"name":..., "price": ..., ...}, ...]} or {"error":...}
    """
    try:
        r = requests.get(f"{BASE}/api/inventory/menu", timeout=8)
        if r.status_code != 200:
            return {"error": r.text}
        return r.json()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

@tool("get_products")
def get_products() -> dict:
    """
    LangChain tool that returns the live menu (names + prices) from Google Sheets.
    """
    return fetch_menu()

# export the tool instance for your registry
products_tool = get_products
