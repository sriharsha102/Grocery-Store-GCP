# backend/tools/sheets/get_top_sellers_tool.py
import logging
from langchain.tools import tool
from backend.integrations.google_sheets.sheets_dal import get_top_selling_items

log = logging.getLogger(__name__)

@tool("get_top_sellers")
def get_top_sellers() -> dict:
    """
    Return top selling items from Google Sheets.
    Calls Google Sheets directly instead of making HTTP requests.
    """
    try:
        items = get_top_selling_items()
        return {"items": items}
    except Exception as e:
        log.exception("get_top_sellers failed")
        return {"error": f"{type(e).__name__}: {e}"}
