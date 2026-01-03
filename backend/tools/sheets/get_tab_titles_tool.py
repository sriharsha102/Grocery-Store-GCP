# backend/tools/sheets/get_tab_titles_tool.py
import os
import requests
from langchain_core.tools import tool

BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")  # align with other tools; override with API_BASE if needed
FALLBACK_BASE = "http://localhost:8080"


def fetch_tab_titles() -> dict:
    """
    Calls the backend categories endpoint and returns {"categories": [...]}
    """
    primary_base = os.getenv("API_BASE", BASE)
    bases_to_try = [primary_base]
    if FALLBACK_BASE not in bases_to_try:
        bases_to_try.append(FALLBACK_BASE)

    last_error = None
    for base_url in bases_to_try:
        try:
            r = requests.get(f"{base_url}/api/inventory/categories", timeout=8)
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


@tool("get_tab_titles")
def get_tab_titles() -> dict:
    """
    LangChain tool that returns the available categories (sheet tab names).
    """
    return fetch_tab_titles()


# export the tool instance for registry use
tab_titles_tool = get_tab_titles
