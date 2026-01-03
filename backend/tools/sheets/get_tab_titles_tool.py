# backend/tools/sheets/get_tab_titles_tool.py
import os
import requests
from langchain_core.tools import tool

BASE = os.getenv("API_BASE", "http://localhost:8080")  # align with other tools; override with API_BASE if needed


def fetch_tab_titles() -> dict:
    """
    Calls the backend categories endpoint and returns {"categories": [...]}
    """
    base = os.getenv("API_BASE", BASE)
    try:
        r = requests.get(f"{base}/api/inventory/categories", timeout=8)
        if r.status_code != 200:
            return {"error": r.text}
        return r.json()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


@tool("get_tab_titles")
def get_tab_titles() -> dict:
    """
    LangChain tool that returns the available categories (sheet tab names).
    """
    return fetch_tab_titles()


# export the tool instance for registry use
tab_titles_tool = get_tab_titles
