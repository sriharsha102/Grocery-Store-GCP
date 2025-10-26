# backend/integrations/google_sheets/sheets_dal.py
import os
from typing import List, Dict, Tuple, Any
from .sheets_client import get_sheets


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sheet_id() -> str:
    sid = os.getenv("GOOGLE_SHEET_ID")
    print("DEBUG GOOGLE_SHEET_ID =", sid)   # temporary
    if not sid:
        raise RuntimeError("GOOGLE_SHEET_ID is not set. Add it to backend/.env.")
    return sid

def _tab() -> str:
    return os.getenv("INVENTORY_TAB", "Inventory")

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

def _read_all() -> tuple[list[str], list[list[str]]]:
    """
    Reads header and all rows for columns A..E (name, price, quantity, date, orders_count).
    """
    svc = _svc()
    sheet_id = _sheet_id()
    tab = _tab()

    # IMPORTANT: include column E so orders_count is present
    hdr = (
        svc.values()
        .get(spreadsheetId=sheet_id, range=f"{tab}!A1:E1")
        .execute()
        .get("values", [[]])[0]
    )
    rows = (
        svc.values()
        .get(spreadsheetId=sheet_id, range=f"{tab}!A2:E")
        .execute()
        .get("values", [])
    )
    return hdr, rows

def _rows_as_dicts() -> List[Dict[str, Any]]:
    """
    Use the sheet header to build dicts; normalize numeric fields.
    """
    hdr, rows = _read_all()
    header = [h.strip().lower() for h in hdr]
    out: List[Dict[str, Any]] = []

    # Find column indices by header (case-insensitive)
    try:
        name_idx = header.index("name")
    except ValueError:
        name_idx = 0
    price_idx = header.index("price") if "price" in header else None
    qty_idx   = header.index("quantity") if "quantity" in header else None
    oc_idx    = header.index("orders_count") if "orders_count" in header else None

    for r in rows:
        r = r + [""] * (len(header) - len(r))
        rec = {header[i]: r[i] for i in range(len(header))}
        # normalize
        if price_idx is not None:
            rec["price"] = _to_float(rec.get("price"))
        if qty_idx is not None:
            rec["quantity"] = _to_int(rec.get("quantity"))
        if oc_idx is not None:
            rec["orders_count"] = _to_int(rec.get("orders_count"))
        # keep date as string if present
        rec["name"] = str(rec.get("name", "")).strip()
        if rec["name"]:
            out.append(rec)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Public DAL
# ──────────────────────────────────────────────────────────────────────────────

def get_menu() -> List[Dict]:
    """
    Returns all inventory rows with numeric price/quantity/orders_count.
    """
    return _rows_as_dicts()

def get_top5_by_orders() -> List[Dict]:
    """
    Returns top 5 rows sorted by 'orders_count' (desc).
    """
    items = _rows_as_dicts()
    items.sort(key=lambda x: x.get("orders_count", 0), reverse=True)
    return items[:5]

# integrations/google_sheets/sheets_dal.py

def decrement_quantities(order_items: List[Tuple[str, int]]) -> Dict:
    """
    order_items: [("Madras Coffee", 2), ("Buttermilk", 1), ...]
    We:
    - check availability (case-insensitive match)
    - decrement quantity
    - increment orders_count
    - return out_of_stock if any problem
    """
    svc = _svc()
    hdr, rows = _read_all()

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
    tab = _tab()

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
        updates.append({
            "range": f"{tab}!{qty_col_letter}{rownum}",
            "values": [[new_qty]]
        })

        # orders_count column (if it exists)
        if oc_idx is not None:
            oc_col_letter = chr(ord("A") + oc_idx)
            updates.append({
                "range": f"{tab}!{oc_col_letter}{rownum}",
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
