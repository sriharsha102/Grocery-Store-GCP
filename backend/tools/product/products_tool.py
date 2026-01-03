# tools/product/products_tool.py
import os, requests
from langchain_core.tools import tool

BASE = os.getenv("API_BASE", "http://localhost:8080")
FALLBACK_BASE = "http://127.0.0.1:8000"

def fetch_menu(category: str | None = None) -> dict:
    """
    Plain helper. Returns {"items":[{"name":..., "price": ..., ...}, ...]} or {"error":...}
    """
    params = {"category": category} if category else None
    # Primary request
    base = BASE
    try:
        r = requests.get(f"{base}/api/inventory/menu", params=params, timeout=8)
        if r.status_code == 200:
            return r.json()
        # Only fallback on connection errors; surface other errors directly
        # (e.g., 4xx/5xx)
        err_text = r.text
    except requests.exceptions.ConnectionError:
        err_text = None
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    # Fallback attempt: if API_BASE not set and primary failed to connect, try 8000
    if os.getenv("API_BASE") is None or os.getenv("API_BASE") == "":
        try:
            r2 = requests.get(f"{FALLBACK_BASE}/api/inventory/menu", params=params, timeout=8)
            if r2.status_code == 200:
                return r2.json()
            return {"error": r2.text}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    return {"error": err_text or "Unknown error contacting backend"}

@tool("get_products")
def get_products(category: str | None = None) -> dict:
    """
    LangChain tool that returns the live menu (names + prices) from Google Sheets.
    """
    return fetch_menu(category=category)

# export the tool instance for your registry
products_tool = get_products
