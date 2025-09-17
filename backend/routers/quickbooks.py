from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from tools.quickbooks.create_invoice_tool import create_invoice_tool
# router = APIRouter(prefix="/api/quickbooks", tags=["quickbooks"])
router = APIRouter(prefix="/api/quickbooks", tags=["quickbooks"])
class Item(BaseModel):
    name: str
    quantity: int
class InvoiceRequest(BaseModel):
    session_id: str
    # customer_id: str # Changed this to str from int
    items: List[Item]
    note: Optional[str] = None
@router.post("/invoice")
def create_invoice(req: InvoiceRequest):
    try:
        # Create a prompt for create_invoice_tool if it expects text
        items_text = ", ".join([f"{i.quantity} {i.name}" for i in req.items])
        prompt = f"{items_text}"
        # prompt = f"Create invoice for customer {req.customer_id} with items: {items_text}."
        if req.note: prompt += f" Note: {req.note}."
        return create_invoice_tool(prompt, req.session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
