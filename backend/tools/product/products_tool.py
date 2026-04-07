# tools/product/products_tool.py
import logging
import os, requests
from typing import Optional
from langchain_core.tools import tool
from backend.integrations.google_sheets.sheets_dal import get_menu, get_tab_titles
from backend.state.session import add_active_tab, get_item_tab_mapping, set_item_tab_mapping

log = logging.getLogger(__name__)

def _resolve_category(category: str) -> str:
    """
    Resolve a partial/truncated category name to the exact tab title.
    e.g. "Rice" → "Rice & Wheat", "snacks" → "Snacks & other items"
    Falls back to the original string if no match is found.
    """
    try:
        all_tabs = get_tab_titles()
    except Exception:
        return category

    # 1. Exact match (case-insensitive)
    for tab in all_tabs:
        if tab.lower() == category.lower():
            return tab

    # 2. Starts-with match (case-insensitive)
    for tab in all_tabs:
        if tab.lower().startswith(category.lower()):
            log.info("Resolved partial category '%s' → '%s'", category, tab)
            return tab

    # 3. Contains match (case-insensitive)
    for tab in all_tabs:
        if category.lower() in tab.lower():
            log.info("Resolved contained category '%s' → '%s'", category, tab)
            return tab

    log.warning("Could not resolve category '%s' to any known tab", category)
    return category


def fetch_menu(category: Optional[str] = None, session_id: str | None = None) -> dict:
    try:
        if category:
            category = _resolve_category(category)
        items = get_menu(tab=category)
        if session_id and category:
            add_active_tab(session_id, category)
        return {"items": items}
    except Exception as e:
        log.exception("fetch_menu failed")
        return {"error": f"{type(e).__name__}: {e}"}

@tool("get_products")
def get_products(category: Optional[str] = None, session_id: str | None = None) -> dict:
    """
    LangChain tool that returns the live menu (names + prices) from Google Sheets.
    Pass session_id to remember active category tabs.
    """
    return fetch_menu(category=category, session_id=session_id)

# export the tool instance for your registry
products_tool = get_products