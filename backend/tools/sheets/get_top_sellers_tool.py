# backend/tools/sheets/get_top_sellers_tool.py
import os, requests
from langchain.tools import tool

BASE = os.getenv("API_BASE","http://localhost:8080")

def _json_or_err(r):
    ct = r.headers.get("content-type", "")
    if r.status_code != 200:
        return None, {"status": r.status_code, "text": r.text[:400], "content_type": ct}
    if "application/json" not in ct:
        return None, {"status": r.status_code, "text": r.text[:400], "content_type": ct}
    try:
        return r.json(), None
    except Exception as e:
        return None, {"status": r.status_code, "text": f"JSON parse failed: {e}", "content_type": ct}

@tool("get_top_sellers")
def get_top_sellers() -> dict:
    """
    Return top items. Tries /api/inventory/top first.
    If missing, fetches /api/inventory/menu and computes top locally.
    """
    attempts = {}

    url_top5 = f"{BASE}/api/inventory/top"
    try:
        r = requests.get(url_top5, timeout=8)
        data, err = _json_or_err(r)
        if not err:
            return data
        attempts[url_top5] = err
    except Exception as e:
        attempts[url_top5] = {"error": f"request failed: {type(e).__name__}: {e}"}

    url_menu = f"{BASE}/api/inventory/menu"
    try:
        r = requests.get(url_menu, timeout=8)
        data, err = _json_or_err(r)
        if err:
            attempts[url_menu] = err
        else:
            items = data.get("items", [])
            def orders_of(x):  # tolerate "orders" or "Orders"
                return int(x.get("orders", x.get("Orders", 0)) or 0)
            top = sorted(items, key=orders_of, reverse=True)[:5]
            return {"items": top, "computed": True}
    except Exception as e:
        attempts[url_menu] = {"error": f"request failed: {type(e).__name__}: {e}"}

    return {"error": "Could not fetch top sellers", "attempts": attempts}
