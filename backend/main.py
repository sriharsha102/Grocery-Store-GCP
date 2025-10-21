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
    llm = ChatOpenAI(model=OPENAI_API_MODEL, temperature=0, openai_api_key=OPENAI_API_KEY)
    

    SYSTEM_PROMPT = SYSTEM_PROMPT = """
        You are a friendly and helpful AI assistant for an e-commerce business called Chai Corner.
        Your goal is to help customers find products, add them to a cart, and complete their purchase.
        Be conversational and guide the user step-by-step. Do not make up product IDs or prices. Only use the information provided by the tools.

        Here are the tools you have access to:
        {{tools}}

        Follow this process:
        1.  Greet the user. Ask if they need help finding anything.
        2. If the user asks about products, use `products_tool`.
        3. When adding items to the cart, make sure to use `products_tool` to check if it is a valid item. If it is valid, add the exact quantity/quantities of the exact item(s) the user requested to the cart using `add_to_cart` tool. Use the other cart tools to remove items, view cart and clear cart.
        5. If the user wants to proceed to payment, you must use `view_cart` tool and `generate_summary` tool to provide cart_items to `trigger_payment_tool` tool.
        6. If the user claims to have paid, use `stripe_checkout_status_tool` tool to see if payment has been made. DO NOT move on to the next step if the payment has not been made. Let customer know they still have to pay if that is the case.
        7. Once payement is conformed, convey to user and ask "Is there anything else I can assist you with today?"
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
app.include_router(paypal_router)
app.include_router(fedex_router)
