# tools/product/summary_tool.py
from langchain_core.tools import tool
import re
from backend.tools.product.products_tool import fetch_menu  # <-- import the helper, NOT the tool

def _menu_dict() -> dict[str, float]:
    data = fetch_menu()
    items = data.get("items", []) if isinstance(data, dict) else []
    menu = {}
    for it in items:
        name = str(it.get("name", "")).strip()
        # price may be str/float/int in Sheets -> normalize to float
        raw_price = it.get("price", 0)
        try:
            price = float(raw_price)
        except Exception:
            try:
                price = float(str(raw_price).strip().replace("$", ""))
            except Exception:
                price = 0.0
        if name:
            menu[name.lower()] = price
    return menu

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
