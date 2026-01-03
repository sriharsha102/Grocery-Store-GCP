# backend/tools/sheets/get_tab_titles_tool.py
import os
import logging
from langchain_core.tools import tool
from backend.integrations.google_sheets.sheets_dal import get_tab_titles as dal_get_tab_titles

log = logging.getLogger(__name__)

# Read allowlist/denylist from environment
TAB_ALLOWLIST = [t.strip() for t in os.getenv("SHEETS_TAB_ALLOWLIST", "").split(",") if t.strip()]
TAB_DENYLIST = [t.strip() for t in os.getenv("SHEETS_TAB_DENYLIST", "").split(",") if t.strip()]


def fetch_tab_titles() -> dict:
    """
    Calls Google Sheets directly and returns {"categories": [...]}
    """
    try:
        titles = dal_get_tab_titles(
            allowlist=TAB_ALLOWLIST or None,
            denylist=TAB_DENYLIST or None,
        )
        return {"categories": titles}
    except Exception as e:
        log.exception("fetch_tab_titles failed")
        return {"error": f"{type(e).__name__}: {e}"}


@tool("get_tab_titles")
def get_tab_titles() -> dict:
    """
    LangChain tool that returns the available categories (sheet tab names).
    """
    return fetch_tab_titles()


# export the tool instance for registry use
tab_titles_tool = get_tab_titles
