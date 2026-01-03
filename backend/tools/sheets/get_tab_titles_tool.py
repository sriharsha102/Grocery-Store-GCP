# backend/tools/sheets/get_tab_titles_tool.py
import os
import requests
from langchain_core.tools import tool

BASE = os.getenv("API_BASE", "http://localhost:8080")  # align with other tools; override with API_BASE if needed
FALLBACK_BASE = "http://127.0.0.1:8000"


def fetch_tab_titles() -> dict:
    """
    Calls the backend categories endpoint and returns {"categories": [...]}
    """
    base = os.getenv("API_BASE", BASE)
    try:
        r = requests.get(f"{base}/api/inventory/categories", timeout=8)
        if r.status_code == 200:
            return r.json()
        err_text = r.text
    except requests.exceptions.ConnectionError:
        err_text = None
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    # Fallback attempt: if API_BASE not set and primary failed to connect, try 8000
    if os.getenv("API_BASE") is None or os.getenv("API_BASE") == "":
        try:
            r2 = requests.get(f"{FALLBACK_BASE}/api/inventory/categories", timeout=8)
            if r2.status_code == 200:
                return r2.json()
            return {"error": r2.text}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    return {"error": err_text or "Unknown error contacting backend"}


@tool("get_tab_titles")
def get_tab_titles() -> dict:
    """
    LangChain tool that returns the available categories (sheet tab names).
    """
    return fetch_tab_titles()


# export the tool instance for registry use
tab_titles_tool = get_tab_titles
