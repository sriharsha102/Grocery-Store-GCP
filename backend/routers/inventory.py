import os
import time
import logging
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from integrations.google_sheets.sheets_dal import (
    get_menu,
    get_top5_by_orders,
    decrement_quantities,
)
# We no longer import send_receipt / send_low_stock_alert because
# we're moving email sending fully to Apps Script.
# from integrations.gmail.email_sender import send_receipt, send_low_stock_alert

# clear_cart is your existing in-memory/session cart cleanup function.
from tools.cart.cart_tool import clear_cart

router = APIRouter(prefix="/inventory", tags=["inventory"])
log = logging.getLogger(__name__)

# === environment config ===
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")  # e.g. developers@lightningminds.com
EMAIL_MODE = os.getenv("EMAIL_MODE", "APPS_SCRIPT").upper()
APPS_SCRIPT_EMAIL_URL = os.getenv("APPS_SCRIPT_EMAIL_URL", "")
EMAIL_WEBHOOK_SECRET = os.getenv("EMAIL_WEBHOOK_SECRET", "")


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


# ---------- Read-only endpoints ----------

@router.get("/top5")
def top5():
    """
    Return top sellers by orders_count from the sheet.
    """
    try:
        return {"items": get_top5_by_orders()}
    except Exception as e:
        log.exception("top5 failed")
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

@router.post("/finalize")
def finalize(req: FinalizeOrderRequest):
    """
    This is called ONLY AFTER Stripe says 'paid'.

    Steps:
    1. Validate request.
    2. Decrement stock & bump orders_count in Google Sheets.
    3. Build an order_id.
    4. Send receipt + owner copy + low-stock alert via Apps Script webhook.
    5. Clear this session's cart so future orders start empty.
    6. Return a response that the agent can summarize to the user.

    The agent should then say:
      - order confirmed
      - email sent
      - low stock if any
    and NOT expose raw debug objects.
    """

    # --- 1. sanity validation ---
    if not req.items:
        raise HTTPException(status_code=400, detail="No items provided")

    for it in req.items:
        if it.qty <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid qty for {it.name}")

    # --- 2. update Sheets quantities & orders_count ---
    # sheets_dal.decrement_quantities expects List[Tuple[name, qty]]
    try:
        result = decrement_quantities([(it.name, it.qty) for it in req.items])
    except Exception as e:
        log.exception("finalize(): decrement_quantities crashed")
        raise HTTPException(status_code=500, detail=f"Sheet update failed: {e}")

    if result.get("out_of_stock"):
        # This should almost never happen post-payment,
        # but we handle it to avoid lying to the user.
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Some items unavailable",
                "details": result["out_of_stock"],
            },
        )

    order_id = f"ORD-{int(time.time())}"

    # --- 3. send emails via Apps Script webhook ---
    email_sent = False
    low_stock_sent = False
    email_debug: Dict[str, Any] = {}
    low_debug: Dict[str, Any] = {}

    if EMAIL_MODE == "APPS_SCRIPT" and APPS_SCRIPT_EMAIL_URL and EMAIL_WEBHOOK_SECRET:
        # (a) customer receipt (and owner copy)
        receipt_payload = {
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
            er = requests.post(APPS_SCRIPT_EMAIL_URL, json=receipt_payload, timeout=20)
            try:
                er_json = er.json()
            except Exception:
                er_json = {"raw": er.text}

            email_debug = {
                "status": er.status_code,
                "body": er_json,
            }

            if er.status_code == 200 and isinstance(er_json, dict) and er_json.get("ok") is True:
                email_sent = True
        except Exception as e:
            email_debug = {"error": str(e)}
            log.exception("finalize(): error sending receipt email")

        # (b) low stock alert to owner (if any items low_stock == True)
        updated_list = result.get("updated", []) or []
        low_items = [
            u for u in updated_list
            if u.get("low_stock")
        ]

        if low_items and OWNER_EMAIL:
            low_payload = {
                "secret": EMAIL_WEBHOOK_SECRET,
                "type": "low_stock",
                "owner_email": OWNER_EMAIL,
                "items": [
                    {"name": u["name"], "new_qty": u["new_qty"]}
                    for u in low_items
                ],
            }

            try:
                lr = requests.post(APPS_SCRIPT_EMAIL_URL, json=low_payload, timeout=20)
                try:
                    lr_json = lr.json()
                except Exception:
                    lr_json = {"raw": lr.text}

                low_debug = {
                    "status": lr.status_code,
                    "body": lr_json,
                }

                if lr.status_code == 200 and isinstance(lr_json, dict) and lr_json.get("ok") is True:
                    low_stock_sent = True
            except Exception as e:
                low_debug = {"error": str(e)}
                log.exception("finalize(): error sending low-stock alert")

    else:
        log.warning(
            "finalize(): EMAIL_MODE=%s but missing webhook config, skipping email",
            EMAIL_MODE,
        )

    # --- 4. clear user's cart for this session ---
    cart_cleared = False
    try:
        clear_cart(req.session_id)
        cart_cleared = True
    except Exception:
        cart_cleared = False
        log.exception("finalize(): failed to clear cart for session %s", req.session_id)

    # --- 5. return structured response ---
    # NOTE: `email_debug` and `low_debug` are included so you can inspect
    # them in your FastAPI console output and confirm whether Apps Script
    # actually said {ok:true}. The agent shouldn't read these aloud.
    return {
        "order": {
            "order_id": order_id,
            "status": "CONFIRMED",
            "updated": result.get("updated", []),
        },
        "status": "CONFIRMED",
        "cart_cleared": cart_cleared,
        "email_sent": email_sent,
        "low_stock_sent": low_stock_sent,
        "email_debug": email_debug,
        "low_debug": low_debug,
    }
