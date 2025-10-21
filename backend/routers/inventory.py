import os, time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from integrations.google_sheets.sheets_dal import get_menu, get_top5_by_orders, decrement_quantities
from integrations.gmail.email_sender import send_receipt, send_low_stock_alert

router = APIRouter(prefix="/inventory", tags=["inventory"])
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")
log = logging.getLogger(__name__)

class OrderItem(BaseModel):
    name: str
    qty: int

class OrderRequest(BaseModel):
    customer_email: str
    items: List[OrderItem]

@router.get("/top5")
def top5():
    try:
        return {"items": get_top5_by_orders()}
    except Exception as e:
        log.exception("top5 failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/menu")
def menu():
    try:
        return {"items": get_menu()}
    except Exception as e:
        log.exception("menu failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order")
def order(req: OrderRequest):
    if not req.items:
        raise HTTPException(400, "No items provided")
    for it in req.items:
        if it.qty <= 0:
            raise HTTPException(400, f"Invalid qty for {it.name}")

    # 1) decrement quantities (no date change)
    result = decrement_quantities([(it.name, it.qty) for it in req.items])
    if result["out_of_stock"]:
        raise HTTPException(409, {"message": "Some items unavailable", "details": result["out_of_stock"]})

    # 2) emails
    order_id = f"ORD-{int(time.time())}"
    try:
        send_receipt(
            customer_email=req.customer_email,
            owner_email=OWNER_EMAIL,
            items=[{"name": it.name, "qty": it.qty} for it in req.items],
            order_id=order_id
        )
        lows = [{"name": u["name"], "new_qty": u["new_qty"]} for u in result["updated"] if u.get("low_stock")]
        send_low_stock_alert(OWNER_EMAIL, lows)
    except Exception:
        # stock already updated; you may log and retry later
        pass

    return {"order_id": order_id, "status": "CONFIRMED", "updated": result["updated"]}
