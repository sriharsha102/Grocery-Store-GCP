# tools/product/summary_tool.py
from langchain_core.tools import tool
import re
import logging
from backend.integrations.google_sheets.sheets_dal import get_menu, get_menu_for_tabs, get_tab_titles
from backend.state.session import get_active_tabs
from backend.tools.cart.cart_tool import get_cart_for_session

log = logging.getLogger(__name__)

def _menu_dict(tabs: list[str] | None = None) -> dict[str, float]:
    """
    Fetch menu from ALL tabs and return a combined price dictionary.
    Returns: {item_name_lowercase: price}
    """
    tab_titles = tabs or []
    if not tab_titles:
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

    menu = {}
    try:
        tab_results = get_menu_for_tabs(tab_titles)
    except Exception as e:
        log.warning(f"generate_summary: Batch fetch failed: {e}")
        tab_results = {}

    for tab_name, tab_items in tab_results.items():
        log.info(f"generate_summary: Fetched {len(tab_items)} items from tab '{tab_name}'")
        for it in tab_items:
            name = str(it.get("name", "")).strip()
            if name:
                # If item exists in multiple tabs, last tab wins
                menu[name.lower()] = _parse_price(it.get("price", 0))
        

    if not menu and tab_titles:
        for tab_name in tab_titles:
            try:
                tab_items = get_menu(tab=tab_name)
                log.info(f"generate_summary: Fetched {len(tab_items)} items from tab '{tab_name}'")
                for it in tab_items:
                    name = str(it.get("name", "")).strip()
                    if name:
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
def generate_summary(order_text: str, session_id: str | None = None) -> str:
    """
    Compute an itemized total using live prices from Sheets.
    order_text is ignored — cart is read from session state.
    """
    tabs = get_active_tabs(session_id) if session_id else []
    menu = _menu_dict(tabs=tabs)
    if not menu:
        return "Sorry, I couldn't load the menu right now."

    # Read directly from the in-memory cart — don't parse order_text
    cart = get_cart_for_session(session_id) if session_id else {}
    if not cart:
        return "The cart is empty — nothing to summarise."

    total = 0.0
    lines = []
    missing = []

    for item_name, qty in cart.items():
        key = item_name.strip().lower()
        price = menu.get(key)
        if price is None:
            missing.append(item_name)
            continue
        subtotal = qty * price
        total += subtotal
        lines.append(f"{qty} x {item_name.title()} — ${subtotal:.2f}")

    if missing:
        log.warning("generate_summary: items in cart not found in menu: %s", missing)

    if not lines:
        return "Sorry, I couldn't match any cart items to the current menu."

    lines.append(f"\n**Estimated Total:** ${total:.2f}")
    return "\n".join(lines)