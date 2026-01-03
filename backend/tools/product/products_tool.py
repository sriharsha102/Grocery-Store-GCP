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

    def _try(base_url: str):
        return requests.get(f"{base_url}/api/inventory/menu", params=params, timeout=8)

    primary_base = os.getenv("API_BASE", BASE)
    bases_to_try = [primary_base]
    # Always try fallback on connection failure, even if API_BASE is set
    if FALLBACK_BASE not in bases_to_try:
        bases_to_try.append(FALLBACK_BASE)

    last_error = None
    for base_url in bases_to_try:
        try:
            r = _try(base_url)
            if r.status_code == 200:
                return r.json()
            last_error = r.text
        except requests.exceptions.ConnectionError as ce:
            last_error = f"ConnectionError to {base_url}: {ce}"
            continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            break

    return {"error": last_error or "Unknown error contacting backend"}

@tool("get_products")
def get_products(category: str | None = None) -> dict:
    """
    LangChain tool that returns the live menu (names + prices) from Google Sheets.
    """
    return fetch_menu(category=category)

# export the tool instance for your registry
products_tool = get_products
