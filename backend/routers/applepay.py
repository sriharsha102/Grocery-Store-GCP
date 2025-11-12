from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from backend.tools.payment.applepay.apple_pay_tool import (
    generate_apple_pay_link,
    get_apple_pay_session_status,
    save_apple_pay_session_id,
    get_apple_pay_session_id,
)
router = APIRouter(prefix="/api/applepay", tags=["applepay"])
class ApplePayLinkRequest(BaseModel):
    amount: float
    currency: str = "USD"
    order_id: Optional[str] = None
    description: Optional[str] = None

@router.post("/link")
def create_link(req: ApplePayLinkRequest):
    try:
        # product_name can be description or your brand
        product_name = req.description or "Chai Corner Order"
        # ✅ pass the correct parameter names the tool expects
        url = generate_apple_pay_link.invoke({"amount_dollars": req.amount, "product_name": product_name})
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/session/{session_id}")
def set_session(session_id: str):
    try:
        save_apple_pay_session_id(session_id)
        return {"ok": True, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.get("/session")
def get_session():
    try:
        sid = get_apple_pay_session_id()
        return {"session_id": sid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.get("/status/{session_id}")
def status(session_id: str):
    try:
        return get_apple_pay_session_status(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
