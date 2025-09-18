import os
import io
import sys
import logging
from pathlib import Path
import requests
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Routers
from routers.fedex import router as fedex_router
from routers.paypal import router as paypal_router
from routers.quickbooks import router as quickbooks_router
from routers.customer import router as customer_router
from routers.applepay import router as applepay_router

# Tools & SDKs
from state.session import set_websocket
from tools.tool_config import get_all_tools
from tools.quickbooks.quickbooks_wrapper import QuickBooksWrapper

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
logger.info("Chai Corner Backend starting up...")

# ──────────────────────────────────────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_MODEL = os.getenv("OPENAI_API_MODEL") or "gpt-4o-mini"

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in environment.")

# ──────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Chai Corner Backend")

# CORS
origins = [
    "http://10.0.0.80:8080",
    "http://localhost:8080",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://10.0.0.106:8080",
    "https://chaicorner-agent-hrbwcnaxcvgwhcfc.centralus-01.azurewebsites.net",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health for Azure probe (pick ONE path and keep it consistent in App Settings)
@app.get("/health")
def health():
    return {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────────────
# SDKs
# ──────────────────────────────────────────────────────────────────────────────
qb = QuickBooksWrapper()

# ──────────────────────────────────────────────────────────────────────────────
# Downloads
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/download/invoice/{invoice_id}")
def download_invoice(invoice_id: str):
    try:
        pdf_bytes = qb.get_invoice_pdf(invoice_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/download/label/{tracking_number}")
def download_label(tracking_number: str):
    try:
        label_url = f"https://www.fedex.com/label/{tracking_number}.pdf"
        resp = requests.get(label_url, timeout=20)
        if resp.status_code != 200:
            return JSONResponse(
                status_code=resp.status_code,
                content={"error": f"Failed to fetch label: {resp.status_code}"},
            )
        return StreamingResponse(
            io.BytesIO(resp.content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=label_{tracking_number}.pdf"},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ──────────────────────────────────────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────────────────────────────────────
session_memories = {}

def get_memory_for_session(session_id: str) -> ConversationBufferMemory:
    if session_id not in session_memories:
        session_memories[session_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        session_memories[session_id].chat_memory.add_ai_message(f"Session ID: {session_id}")
    return session_memories[session_id]

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    logging.info(f"Session_id in main.websocket_endpoint: {session_id}")
    await ws.accept()
    set_websocket(session_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            logging.info(f"Websocket --- Message from {session_id}: {data}")
            if data.get("event") == "payment_complete":
                logging.info(f"main.py --- Payment complete for session: {session_id}")
                memory = get_memory_for_session(session_id)
                agent_executor = create_agent(memory)
                response = await agent_executor.ainvoke(
                    {"input": "The payment has been verified. Please move on to shipping."}
                )
                await ws.send_json({
                    "type": "agent_message",
                    "ai_message": response.get("output")
                })
    except Exception:
        set_websocket(session_id, None)

def create_agent(memory: ConversationBufferMemory) -> AgentExecutor:
    tools = get_all_tools()
    llm = ChatOpenAI(model=OPENAI_API_MODEL, temperature=0, openai_api_key=OPENAI_API_KEY)
    
    SYSTEM_PROMPT = """
                You are a friendly and helpful AI assistant for an e-commerce business called Chai Corner.
            Goal: help customers find products, add to cart, and complete purchase. Be conversational.
            Never invent product IDs/prices; only use tool outputs. Do not use markdown.
            
            Tools available:
            {{tools}}
            
            Global rules:
            - Do NOT restart or re-greet if the conversation has begun. Continue from context.
            - If the user asks to “proceed”, “generate invoice”, “checkout”, or similar, SKIP all greetings and move to the next logical step.
            - Before charging or invoicing, always verify the cart via view_cart (and generate_summary when asked).
            - Minimize repeated questions: only ask for info that is missing.
            
            Process:
            1) First turn ONLY (i.e., if chat_history has no assistant messages):
               - Greet the user.
               - Ask for their full name if they are a returning customer, or offer to continue as guest.
               - When a name is provided, immediately call validate_customer_tool (DisplayName in QuickBooks).
                 - If found: “Welcome back, [name]!” and continue.
                 - If not found: ask if they want to continue as guest. If yes, create_guest_tool.
            
            2) Product discovery:
               - When asked about items/menu: use products_tool. Answer from tool results only.
            
            3) Cart management:
               - When user orders items: confirm with products_tool, then add_to_cart. Support remove/view/clear.
            
            4) Cart review & summary:
               - If the user asks to view cart or for an order summary: call view_cart and then generate_summary.
            
            5) Invoice:
               - If the user says “proceed to invoice” (or equivalent) and the cart is not empty:
                   - Call create_invoice_tool and return the invoice link for verification.
                 If the cart is empty: ask what they’d like to order and show products via products_tool.
            
            6) Payment:
               - When the user confirms they’re ready to pay:
                   - Call view_cart and generate_summary to provide cart_items to trigger_payment_tool.
               - If the user claims payment is done: verify via stripe_checkout_status_tool.
                 Do NOT proceed until it’s actually paid.
            
            7) Shipping:
               - After payment is complete:
                   - If user was a guest, collect: First name, Last name, Phone, Email, Shipping address (street, city, state, postal code).
                   - If returning customer: collect Phone and Shipping address.
                   - Use this info (include customer name) to call create_fedex_shipment and return tracking ID + label link.
            
            8) Profile save:
               - Check if the customer is a guest or not using the check_guest_tool. If they are a guest, ask if they would like to save their profile for future orders. If so, call the rename_customer_tool with the information from the previous step.
            
            Important:
            - Never greet again if any assistant message already exists in chat_history.
            - If the user intent clearly maps to a later step (e.g., “proceed to invoice”), jump there directly.
            - Keep answers short and actionable.

        
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True, handle_parsing_errors=True)

# ──────────────────────────────────────────────────────────────────────────────
# Main chat endpoint
# ──────────────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        session_id = request.session_id
        logging.info(f"Session_id in main.chat_endpoint: {session_id}")
        memory = get_memory_for_session(session_id)
        agent_executor = create_agent(memory)
        response = await agent_executor.ainvoke({"input": request.message})
        return {"response": response.get("output")}
    # except Exception as e:
    #     logging.exception("An error occurred in chat endpoint")
    #     return JSONResponse({"error": "An internal server error occurred."}, status_code=500)
    except Exception as e:
        logging.exception("An error occurred in chat endpoint")
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)

# ──────────────────────────────────────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────────────────────────────────────
app.include_router(applepay_router)
app.include_router(customer_router)
app.include_router(quickbooks_router)
app.include_router(paypal_router)
app.include_router(fedex_router)
