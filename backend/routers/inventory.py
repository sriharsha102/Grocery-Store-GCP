import os
import time
import logging
import uuid
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any
from dotenv import load_dotenv
#from tools.cart import clear_cart, view_cart

load_dotenv()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from backend.integrations.google_sheets.sheets_dal import (
    get_menu,
    get_top_selling_items,
    decrement_quantities,
    get_tab_titles,
)
# We no longer import send_receipt / send_low_stock_alert because
# we're moving email sending fully to Apps Script.
# from integrations.gmail.email_sender import send_receipt, send_low_stock_alert

# clear_cart is your existing in-memory/session cart cleanup function.
from backend.tools.cart.cart_tool import clear_cart

router = APIRouter(prefix="/inventory", tags=["inventory"])
log = logging.getLogger(__name__)

# === environment config ===
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")  # e.g. developers@lightningminds.com
EMAIL_MODE = os.getenv("EMAIL_MODE", "APPS_SCRIPT").upper()
APPS_SCRIPT_EMAIL_URL = os.getenv("APPS_SCRIPT_EMAIL_URL", "")
EMAIL_WEBHOOK_SECRET = os.getenv("EMAIL_WEBHOOK_SECRET", "")
REQUEST_TIMEOUT = int(os.getenv("EXTERNAL_REQUEST_TIMEOUT", "30"))
TAB_ALLOWLIST = [t.strip() for t in os.getenv("SHEETS_TAB_ALLOWLIST", "").split(",") if t.strip()]
TAB_DENYLIST = [t.strip() for t in os.getenv("SHEETS_TAB_DENYLIST", "").split(",") if t.strip()]

# Validate critical configuration at module load
if EMAIL_MODE == "APPS_SCRIPT":
    if not APPS_SCRIPT_EMAIL_URL:
        log.warning("EMAIL_MODE is APPS_SCRIPT but APPS_SCRIPT_EMAIL_URL not configured")
    if not EMAIL_WEBHOOK_SECRET:
        log.warning("EMAIL_MODE is APPS_SCRIPT but EMAIL_WEBHOOK_SECRET not configured - webhooks will fail")


# ---------- Pydantic models ----------

class OrderItem(BaseModel):
    name: str
    qty: int

class OrderRequest(BaseModel):
    customer_email: EmailStr
    items: List[OrderItem]

class FinalizeOrderRequest(BaseModel):
    session_id: str
    customer_email: EmailStr
    items: List[OrderItem]

class FinalizeStockRequest(BaseModel):
    session_id: str
    items: List[OrderItem]

class FinalizeReceiptRequest(BaseModel):
    session_id: str
    customer_email: EmailStr
# ---------- Read-only endpoints ----------

@router.get("/top")
def top():
    """
    Return top sellers by orders_count from the sheet.
    """
    try:
        return {"items": get_top_selling_items()}
    except Exception as e:
        log.exception("top selling items failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/menu")
def menu():
    """
    Return full current menu (name, price, quantity, etc.) from the sheet.
    """
    try:
        return {"items": get_menu()}
    except Exception as e:
        log.exception("menu failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
def categories():
    """
    Return the list of tab titles from the Google Sheet, optionally filtered via allowlist/denylist.
    """
    try:
        titles = get_tab_titles(
            allowlist=TAB_ALLOWLIST or None,
            denylist=TAB_DENYLIST or None,
        )
        return {"categories": titles}
    except Exception as e:
        log.exception("categories failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Legacy order endpoint (direct order flow) ----------

@router.post("/order")
def order(req: OrderRequest):
    """
    Older flow: decrement stock + send emails in one shot.
    (Kept for backward compatibility. Your agent probably doesn't call this anymore.)
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="No items provided")
    for it in req.items:
        if it.qty <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid qty for {it.name}")

    # 1) decrement quantities in the sheet
    result = decrement_quantities([(it.name, it.qty) for it in req.items])
    if result["out_of_stock"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Some items unavailable",
                "details": result["out_of_stock"],
            },
        )

    order_id = f"ORD-{int(time.time())}"

    # 2) EMAIL BEHAVIOR HERE WAS USING send_receipt/send_low_stock_alert.
    #    We're migrating to Apps Script in /finalize, so this endpoint
    #    may become obsolete. Leaving it as-is without email to avoid
    #    double-send. If you still need email here, you could call the
    #    exact same logic we use in finalize() below.
    #
    #    For safety in prod, we'll just log.
    log.info("order(): Stock updated for %s, but no email sent (legacy endpoint).", order_id)

    return {
        "order_id": order_id,
        "status": "CONFIRMED",
        "updated": result["updated"],
    }


# ---------- New canonical post-payment finalize ----------



@router.post("/finalize_stock")
def finalize_stock(req: FinalizeStockRequest):
    """
    Step 1: Called immediately after Stripe confirms payment.
    - Decrements stock & bumps orders_count in Sheets.
    - Sends low-stock alert if needed.
    - DOES NOT send receipt yet (email not known).
    """
    req_id = str(uuid.uuid4())[:8]
    
    if not req.items:
        raise HTTPException(status_code=400, detail="No items provided")

    for it in req.items:
        if it.qty <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid qty for {it.name}")

    try:
        result = decrement_quantities([(it.name, it.qty) for it in req.items])
    except Exception as e:
        log.exception("finalize_stock(): decrement_quantities crashed")
        raise HTTPException(status_code=500, detail=f"Sheet update failed: {e}")

    # Handle rare out-of-stock race condition
    if result.get("out_of_stock"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Some items unavailable after payment.",
                "details": result["out_of_stock"],
            },
        )

    order_id = f"ORD-{int(time.time())}"

    # --- Send only low-stock alerts here ---
    low_stock_sent = False
    low_debug = {}
    if EMAIL_MODE == "APPS_SCRIPT" and APPS_SCRIPT_EMAIL_URL and EMAIL_WEBHOOK_SECRET:
        updated_list = result.get("updated", []) or []
        low_items = [u for u in updated_list if u.get("low_stock")]

        if low_items and OWNER_EMAIL:
            low_payload = {
                "secret": EMAIL_WEBHOOK_SECRET,
                "type": "low_stock",
                "owner_email": OWNER_EMAIL,
                "items": [{"name": u["name"], "new_qty": u["new_qty"]} for u in low_items],
            }
            try:
                lr = requests.post(APPS_SCRIPT_EMAIL_URL, json=low_payload, timeout=REQUEST_TIMEOUT)
                # Safe JSON parsing
                try:
                    lr_json = lr.json()
                except (ValueError, requests.exceptions.JSONDecodeError) as json_err:
                    log.warning(f"Failed to parse JSON response: {json_err}")
                    lr_json = {"raw": lr.text, "parse_error": True}

                low_debug = {"status": lr.status_code, "body": lr_json}
                if lr.status_code == 200 and isinstance(lr_json, dict) and lr_json.get("ok") is True:
                    low_stock_sent = True
            except requests.exceptions.Timeout:
                log.error(f"Timeout sending low-stock alert after {REQUEST_TIMEOUT}s")
                low_debug = {"error": "Request timeout"}
            except Exception as e:
                log.exception("finalize_stock(): error sending low-stock alert")
                low_debug = {"error": str(e)}

    return {
        "order_id": order_id,
        "status": "STOCK_UPDATED",
        "low_stock_sent": low_stock_sent,
        "low_debug": low_debug,
        "updated": result.get("updated", []),
    }

# ==============================
#  NEW ENDPOINT #2: finalize_receipt
# ==============================
@router.post("/finalize_receipt")
def finalize_receipt(req: FinalizeOrderRequest):

    if not req.customer_email or not req.customer_email.strip():
        raise HTTPException(status_code=400, detail="customer_email is required")

    order_id = f"ORD-{int(time.time())}"

    email_sent = False
    email_debug = {}


    if EMAIL_MODE == "APPS_SCRIPT" and APPS_SCRIPT_EMAIL_URL and EMAIL_WEBHOOK_SECRET:
        payload = {
            "secret": EMAIL_WEBHOOK_SECRET,
            "type": "receipt",
            "order": {
                "order_id": order_id,
                "customer_email": req.customer_email,
                "items": [{"name": it.name, "qty": it.qty} for it in req.items],
            },
            "owner_email": OWNER_EMAIL,
        }

        try:
            er = requests.post(APPS_SCRIPT_EMAIL_URL, json=payload, timeout=REQUEST_TIMEOUT)
            # Safe JSON parsing
            try:
                er_json = er.json()
            except (ValueError, requests.exceptions.JSONDecodeError) as json_err:
                log.warning(f"Failed to parse JSON response: {json_err}")
                er_json = {"raw": er.text, "parse_error": True}

            email_debug = {"status": er.status_code, "body": er_json}
            if er.status_code == 200 and isinstance(er_json, dict) and er_json.get("ok") is True:
                email_sent = True
        except requests.exceptions.Timeout:
            log.error(f"Timeout sending receipt email after {REQUEST_TIMEOUT}s")
            email_debug = {"error": "Request timeout"}
        except Exception as e:
            email_debug = {"error": str(e)}
            log.exception("finalize_receipt(): error sending receipt email")
    else:
        log.warning("finalize_receipt(): missing webhook config, skipping email")

    cart_cleared = False
    try:
        clear_cart(req.session_id)
        cart_cleared = True
    except Exception:
        log.exception("finalize_receipt(): failed to clear cart for session %s", req.session_id)

    return {
        "order": {"order_id": order_id, "status": "RECEIPT_SENT"},
        "email_sent": email_sent,
        "cart_cleared": cart_cleared,
        "email_debug": email_debug,
    }
