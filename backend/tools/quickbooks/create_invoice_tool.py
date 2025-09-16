from langchain.tools import tool
from tools.quickbooks.quickbooks_wrapper import QuickBooksWrapper
from state.session import get_customer
import re

import sys
import logging

logger = logging.getLogger(__name__)

@tool("create_invoice_tool")
def create_invoice_tool(input_text: str, session_id: str) -> str:
    """
    Example: 'Generate 2 Madras Coffee and 1 Elaichi Chai for customer 58'
    """
    customer_match = re.search(r"customer\s+(\d+)", input_text, re.IGNORECASE)
    
    customer_id = get_customer(session_id)
    
    # Log with the logger instance
    logger.info(f"Customer_id in create_invoice_tool.py: {customer_id}")
    logger.info(f"create_invoice_tool.py --- input_text: {input_text}")

    item_matches = re.findall(r"(\d+)\s+([a-zA-Z\s]+?)(?:,|and|for|$)", input_text, re.IGNORECASE)
    if not item_matches:
        logger.warning("Could not parse any item quantities from input text.")
        return " Could not parse item quantities."

    name_to_id = {
        "elaichi chai": ("20", 16),
        "ginger chai": ("22", 15),
        "madras coffee": ("19", 20),
        "masala chai": ("21", 20),
    }
    
    logger.info(f"create_invoice_tool.py --- item_matches: {item_matches}")

    line_items = []
    for i, (qty, name) in enumerate(item_matches, start=1):
        name = name.strip().lower()
        item_id, price = name_to_id.get(name, ("0", 0))
        if item_id == "0":
            logger.warning(f"Item name '{name}' not recognized. Skipping.")
            continue
        line_items.append({
            "Description": name.title(),
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "Qty": int(qty),
                "UnitPrice": price,
                "ItemRef": {
                    "name": name.title(),
                    "value": item_id
                }
            },
            "LineNum": i,
            "Amount": int(qty) * price,
            "Id": str(i)
        })
    logger.info(f"create_invoice_tool.py --- Line items: {line_items}")
    if not line_items:
        logger.error("No valid line items were created for the invoice.")
        return "Could not create valid line items for the invoice."

    try:
        qb = QuickBooksWrapper() 
        invoice = qb.create_invoice(customer_id, line_items)
        invoice_id = invoice["Invoice"]["Id"]
        doc_number = invoice["Invoice"].get("DocNumber", invoice_id)


        pdf_link = f"https://chaicorner-agent-hrbwcnaxcvgwhcfc.centralus-01.azurewebsites.net/api/download/invoice/{invoice_id}"
        logger.info(f"Successfully created Invoice #{doc_number} with PDF link: {pdf_link}")
        return f" Created Invoice #{doc_number}\n📄 [Download PDF Invoice]({pdf_link})"
    except Exception as e:
        logger.error(f"An error occurred while creating the invoice: {e}", exc_info=True)
        return f"Error creating invoice: {str(e)}"

invoice_tool = create_invoice_tool
