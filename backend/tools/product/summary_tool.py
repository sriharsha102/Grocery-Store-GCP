# tools/product/summary_tool.py
from langchain_core.tools import tool
import re
import logging
from backend.integrations.google_sheets.sheets_dal import get_menu, get_tab_titles

log = logging.getLogger(__name__)

def _menu_dict() -> dict[str, float]:
    """
    Fetch menu from ALL tabs and return a combined price dictionary.
    Returns: {item_name_lowercase: price}
    """
    try:
        # Get all tab titles
        tab_titles = get_tab_titles()
        log.info(f"generate_summary: Found {len(tab_titles)} tabs: {tab_titles}")
    except Exception as e:
        log.warning(f"generate_summary: Failed to get tab titles, falling back to default tab: {e}")
        # Fallback to default tab
        data = get_menu()
        items = data if isinstance(data, list) else []
        menu = {}
        for it in items:
            name = str(it.get("name", "")).strip()
            if name:
                menu[name.lower()] = _parse_price(it.get("price", 0))
        return menu

    # Fetch from all tabs
    menu = {}
    for tab_name in tab_titles:
        try:
            tab_items = get_menu(tab=tab_name)
            log.info(f"generate_summary: Fetched {len(tab_items)} items from tab '{tab_name}'")

            for it in tab_items:
                name = str(it.get("name", "")).strip()
                if name:
                    # If item exists in multiple tabs, last tab wins
                    menu[name.lower()] = _parse_price(it.get("price", 0))

        except Exception as e:
            log.warning(f"generate_summary: Failed to fetch from tab '{tab_name}': {e}")
            continue

    log.info(f"generate_summary: Total unique items across all tabs: {len(menu)}")
    return menu

def _parse_price(raw_price) -> float:
    """Parse price from various formats (str/float/int)."""
    try:
        return float(raw_price)
    except Exception:
        try:
            return float(str(raw_price).strip().replace("$", ""))
        except Exception:
            return 0.0

@tool("generate_summary")
def generate_summary(order_text: str) -> str:
    """
    Parse an order sentence and compute an itemized total using live prices from Sheets.
    """
    menu = _menu_dict()
    if not menu:
        return "Sorry, I couldn't load the menu right now."

    total = 0.0
    lines = []

    # match any menu item by exact name (case-insensitive), quantity optional (defaults to 1)
    text = order_text.lower()
    for item_name, price in menu.items():
        # allow spaces/variations; quantity optional
        pattern = rf"(?:(\d+)\s*)?{re.escape(item_name)}\b"
        for qty_str in re.findall(pattern, text):
            qty = int(qty_str) if qty_str else 1
            subtotal = qty * price
            total += subtotal
            lines.append(f"{qty} {item_name.title()} - ${subtotal:.2f}")

    if not lines:
        return "Sorry, I couldn't detect any valid items in your order."

    lines.append(f"\n**Estimated Total:** ${total:.2f}")
    return "\n".join(lines)
