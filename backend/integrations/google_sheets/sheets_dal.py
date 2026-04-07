# backend/integrations/google_sheets/sheets_dal.py
import os
import logging
from typing import List, Dict, Tuple, Any
from .sheets_client import get_sheets


log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sheet_id() -> str:
    sid = os.getenv("GOOGLE_SHEET_ID").strip()
    if not sid:
        raise RuntimeError("GOOGLE_SHEET_ID is not set. Add it to backend/.env.")
    # Only log first 8 characters for debugging (removed in production)
    log.debug(f"Using sheet ID: {sid[:8] if sid else 'None'}...")
    return sid

def _tab() -> str:
    return os.getenv("INVENTORY_TAB", "Rice & Wheat")

def _svc():
    return get_sheets()

def _to_int(x) -> int:
    try:
        return int(str(x).strip())
    except Exception:
        return 0

def _to_float(x) -> float:
    try:
        return float(str(x).strip())
    except Exception:
        return 0.0

def _col_letter(col_idx_zero_based: int) -> str:
    """
    Convert 0-based column index -> A1 notation letter(s).
    0->A, 1->B, ..., 25->Z, 26->AA, etc.
    """
    n = col_idx_zero_based + 1
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _quote_tab(tab: str) -> str:
    """
    Wrap tab name in single quotes for A1 notation when it contains
    spaces, ampersands, or other special characters.
    Escapes any literal single-quote inside the name.
    """
    if any(c in tab for c in (" ", "&", "-", "/", "'")):
        return "'" + tab.replace("'", "''") + "'"
    return tab

def _read_all(tab: str | None = None) -> tuple[list[str], list[list[str]]]:
    """
    Reads header and all rows for columns A..G (name, price, weight, quantity, date, orders_count).
    """
    svc = _svc()
    sheet_id = _sheet_id()
    tab = tab or _tab()

    # IMPORTANT: include column G so orders_count/top_selling_items are present
    qt = _quote_tab(tab)
    hdr = (
        svc.values()
        .get(spreadsheetId=sheet_id, range=f"{qt}!A1:G1")
        .execute()
        .get("values", [[]])[0]
    )
    rows = (
        svc.values()
        .get(spreadsheetId=sheet_id, range=f"{qt}!A2:G")
        .execute()
        .get("values", [])
    )
    return hdr, rows

def _rows_as_dicts_from_values(header: list[str], rows: list[list[str]]) -> List[Dict[str, Any]]:
    """
    Read all rows from the Inventory sheet, map header -> value,
    and normalize some known columns so downstream code can trust the shape.
    Map header -> value and normalize some known columns so downstream code can trust the shape.

    Output keys:
      - name (str)
      - price (float)
      - weight (str)
      - quantity (int)
      - date (str, untouched)
      - orders_count (int)
      - top_selling (str: "Y"/"N"/"")
      - sale (str promo text or "")

    We still include ANY other columns in the sheet automatically too,
    because we start from the raw header dict.
    """
    header = [h.strip().lower() for h in header]
    out: List[Dict[str, Any]] = []
    # Find column indices by header (case-insensitive)
    try:
        name_idx = header.index("name")
    except ValueError:
        name_idx = 0
    price_idx = header.index("price") if "price" in header else None
    weight_idx = header.index("weight") if "weight" in header else None
    qty_idx   = header.index("quantity") if "quantity" in header else None
    #oc_idx    = header.index("orders_count") if "orders_count" in header else None
    top_selling_idx    = header.index("top_selling_items") if "top_selling_items" in header else None

    for r in rows:
        # pad in case row shorter than header
        r = r + [""] * (len(header) - len(r))

        # start with raw mapping of EVERY column
        rec = {header[i]: r[i] for i in range(len(header))}

        # price -> float
        if price_idx is not None:
            rec["price"] = _to_float(rec.get("price"))

        # weight -> str (optional)
        if weight_idx is not None:
            rec["weight"] = str(rec.get("weight", "")).strip()

        # quantity -> int
        if qty_idx is not None:
            rec["quantity"] = _to_int(rec.get("quantity"))

        rec["name"] = str(rec.get("name", "")).strip()

        if top_selling_idx is not None:
            rec["top_selling"] = str(rec.get("top_selling_items", "")).strip()

        if rec["name"]:
            out.append(rec)

    return out

def _rows_as_dicts(tab: str | None = None) -> List[Dict[str, Any]]:
    """
    Read all rows from the Inventory sheet, map header -> value,
    and normalize some known columns so downstream code can trust the shape.
    """
    hdr, rows = _read_all(tab=tab)
    return _rows_as_dicts_from_values(hdr, rows)


# ──────────────────────────────────────────────────────────────────────────────
# Public DAL
# ──────────────────────────────────────────────────────────────────────────────

def get_menu(tab: str | None = None) -> List[Dict]:
    """
    Returns full inventory rows with normalized fields.
    """
    return _rows_as_dicts(tab=tab)



def get_menu_for_tabs(tabs: List[str]) -> Dict[str, List[Dict]]:
    """
    Batch fetch menu rows for multiple tabs.
    Returns: {tab_name: [row_dicts]}
    """
    if not tabs:
        return {}

    svc = _svc()
    sheet_id = _sheet_id()
    ranges = [f"{_quote_tab(tab)}!A1:G" for tab in tabs]
    resp = svc.values().batchGet(
        spreadsheetId=sheet_id,
        ranges=ranges,
    ).execute()

    results: Dict[str, List[Dict]] = {}
    for value_range in resp.get("valueRanges", []):
        range_name = value_range.get("range", "")
        tab_name = range_name.split("!", 1)[0] if "!" in range_name else range_name
        tab_name = tab_name.strip("'") 
        values = value_range.get("values", [])
        if not values:
            results[tab_name] = []
            continue
        header = values[0]
        rows = values[1:] if len(values) > 1 else []
        results[tab_name] = _rows_as_dicts_from_values(header, rows)

    return results

def get_top_selling_items(tab: str | None = None) -> List[Dict]:
    """
    Returns top selling items from top_selling_items column.
    """
    items = _rows_as_dicts(tab=tab)
    selected_cols = ["name", "price", "weight", "quantity", "top_selling_items"]
    selected_cols = ["name", "price", "weight", "quantity", "top_selling_items"]
    
    selected_cols = [c.lower() for c in selected_cols]
    filtered_items = [
        {k: v for k, v in item.items() if k.lower() in selected_cols}
        for item in items
    ]
    return filtered_items


def decrement_quantities(order_items: List[Tuple[str, int]], tab: str | None = None) -> Dict:
    """
    order_items: [("Madras Coffee", 2), ("Buttermilk", 1), ...]
    We:
    - check availability (case-insensitive match)
    - decrement quantity
    - increment orders_count
    - return out_of_stock if any problem
    """
    svc = _svc()
    hdr, rows = _read_all(tab=tab)

    # figure out which column is which
    # expected headers: name | quantity | (maybe price) | date | orders_count
    # but we don't assume order, we look them up dynamically:
    try:
        name_idx = hdr.index("name")
    except ValueError:
        raise RuntimeError("Sheet missing 'name' column")

    try:
        qty_idx = hdr.index("quantity")
    except ValueError:
        raise RuntimeError("Sheet missing 'quantity' column")

    # orders_count might exist
    oc_idx = None
    if "orders_count" in hdr:
        oc_idx = hdr.index("orders_count")

    # Build lookup dict of item name -> (rownum, row_values) in LOWERCASE
    # rownum here is the actual sheet row number (starts at 2 because row 1 is header)
    idx = {}
    for i, r in enumerate(rows, start=2):
        # pad row so indexes are safe to access
        padded = r + [""] * (len(hdr) - len(r))
        item_name = str(padded[name_idx]).strip()
        if item_name:
            idx[item_name.lower()] = (i, padded)

    # Verify availability first
    oos = []
    normalized_orders = []  # list of tuples: (norm_key, want_qty)
    for name, want in order_items:
        key = str(name).strip().lower()
        if key not in idx:
            oos.append({"name": name, "reason": "not_found"})
            continue
        _, row = idx[key]
        have = int(row[qty_idx] or 0)
        if have < want:
            oos.append({"name": name, "reason": f"only {have} left"})
        else:
            normalized_orders.append((key, want))

    if oos:
        # we DO NOT mutate sheet if anything is invalid
        return {"updated": [], "out_of_stock": oos}

    # Build batchUpdate payload
    updates = []
    result = []

    sheet_id = _sheet_id()
    tab = tab or _tab()

    for key, want in normalized_orders:
        rownum, row = idx[key]

        # quantity math
        have_qty = int(row[qty_idx] or 0)
        new_qty = have_qty - want

        # orders_count math
        if oc_idx is not None:
            have_oc = int(row[oc_idx] or 0)
            new_oc = have_oc + want
        else:
            new_oc = None

        # queue spreadsheet writes
        # quantity column
        qty_col_letter = chr(ord("A") + qty_idx)   # crude A/B/C... for up to Z
        qt = _quote_tab(tab)
        updates.append({
            "range": f"{qt}!{qty_col_letter}{rownum}",
            "values": [[new_qty]]
        })

        # orders_count column (if it exists)
        if oc_idx is not None:
            oc_col_letter = chr(ord("A") + oc_idx)
            updates.append({
                "range": f"{qt}!{oc_col_letter}{rownum}",
                "values": [[new_oc]]
            })

        result.append({
            "name": row[name_idx],
            "decremented": want,
            "new_qty": new_qty,
            "low_stock": new_qty <= 10
        })

    # Actually write changes
    if updates:
        svc.values().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "valueInputOption": "USER_ENTERED",
                "data": updates
            }
        ).execute()

    return {
        "updated": result,
        "out_of_stock": []
    }


def get_tab_titles(allowlist: List[str] | None = None, denylist: List[str] | None = None) -> List[str]:
    """
    Return the titles of every sheet tab for the configured spreadsheet.

    Optionally filter via allowlist/denylist. Comparisons are case-insensitive.
    """
    svc = _svc()
    sheet_id = _sheet_id()

    resp = (
        svc.get(
            spreadsheetId=sheet_id,
            fields="sheets.properties.title",
        ).execute()
    )

    sheets = resp.get("sheets", []) or []
    titles = [
        s.get("properties", {}).get("title")
        for s in sheets
        if s.get("properties", {}).get("title")
    ]

    if allowlist:
        allowed = {t.lower() for t in allowlist}
        titles = [t for t in titles if t.lower() in allowed]

    if denylist:
        denied = {t.lower() for t in denylist}
        titles = [t for t in titles if t.lower() not in denied]

    return titles
