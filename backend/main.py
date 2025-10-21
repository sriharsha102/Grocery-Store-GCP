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
from langchain.tools.render import render_text_description
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from routers.inventory import router as inventory_router

# Routers
from routers.fedex import router as fedex_router
from routers.paypal import router as paypal_router

from routers.applepay import router as applepay_router

# Tools & SDKs
from state.session import set_websocket
from tools.tool_config import get_all_tools


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
#qb = QuickBooksWrapper()

# ──────────────────────────────────────────────────────────────────────────────
# Downloads
# ──────────────────────────────────────────────────────────────────────────────
#@app.get("/download/invoice/{invoice_id}")
#def download_invoice(invoice_id: str):
 #   try:
  #      pdf_bytes = qb.get_invoice_pdf(invoice_id)
   #     return StreamingResponse(
    #        io.BytesIO(pdf_bytes),
   #         media_type="application/pdf",
    #        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"},
   #     )
    #except Exception as e:
   #     return JSONResponse(status_code=500, content={"error": str(e)})

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
   
    def _escape_braces(s: str) -> str:
        return s.replace("{", "{{").replace("}", "}}")

    tool_list = "\n".join(
        f"- {getattr(t, 'name', 'tool')}: {_escape_braces(getattr(t, 'description', '').strip())}"
        for t in tools
    )



    system_prompt = (
        "You are a friendly, concise AI assistant for an e-commerce shop called Chai Corner.\n\n"
        "What to do\n"
        "- Help users browse items, add/remove from cart, and checkout.\n"
        "- Never invent product names, prices, or stock. Always rely on tools.\n"
        "- No login; treat every user as a guest.\n"
        "- After successful payment, send email the receipt and update inventory in Google Sheets; "
        "do not paste the full invoice in chat.\n\n"
        "Tools you can call:\n"
        f"{tool_list}\n\n"
        "Exact flow\n"
        "1) Greeting: short hello and offer help. If they ask for menu/popular/top sellers, call get_top_sellers. "
        "If they ask for a specific item, use products_tool to verify name and price.\n"
        "2) Browse & Cart: use products_tool to validate items; then add_to_cart/remove_from_cart/view_cart/clear_cart. "
        "If quantity is unclear, ask one crisp follow-up.\n"
        "3) Checkout: before triggering payment, always call view_cart, then generate_summary to produce cart_items; "
        "then call trigger_payment_tool and share the checkout link only.\n"
        "4) Verify payment: if user says they paid, call stripe_checkout_status_tool. If not paid, say so and stop. "
        "If paid, acknowledge and proceed.\n"
        "5) After payment: Ask the user to share the email id for receipt and call place_order with the customer email and final line items (name and qty) to update Sheets; "
        "send receipt email to the owner; if any item is low stock (≤10), send a low-stock alert to the owner. "
        "Then confirm the order to the user.\n\n"
        "Output style\n"
        "- Be brief and step-by-step.\n"
        "- When you used tools, summarize the result (top 5, cart items, payment status).\n"
        "- Never expose raw tool payloads or IDs unless asked."
    )

    llm = ChatOpenAI(model=OPENAI_API_MODEL, temperature=0, openai_api_key=OPENAI_API_KEY)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
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
app.include_router(inventory_router)
app.include_router(applepay_router)
app.include_router(paypal_router)
app.include_router(fedex_router)
