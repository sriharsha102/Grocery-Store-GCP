# WebSocket Connection Fixes - Complete Guide

## Problem Summary

**Issue:** "No active websocket for session, payment not initialized"

This occurs when:
1. WebSocket connection drops silently
2. User tries to initiate payment
3. Backend checks for WebSocket and doesn't find one
4. Payment is blocked

## Solutions Implemented (SOLUTION 1 - DONE ✅)

### 1. Automatic Reconnection with Exponential Backoff

**What was added:**
- Custom hook: `useReconnectingWebSocket` in `frontend/src/hooks/useReconnectingWebSocket.ts`
- Automatically reconnects when connection drops
- Exponential backoff (2s, 3s, 4.5s, 6.75s...)
- Max 10 reconnection attempts

**How it works:**
```typescript
const { ws, status, isConnected, send } = useReconnectingWebSocket(wsUrl, {
    heartbeatInterval: 30000,      // Ping every 30 seconds
    reconnectInterval: 2000,        // Base retry interval
    maxReconnectAttempts: 10       // Give up after 10 tries
});
```

**Benefits:**
- ✅ Connection automatically restored if dropped
- ✅ Works across Cloud Run instance restarts
- ✅ User doesn't need to refresh page

---

### 2. Heartbeat/Ping-Pong Mechanism

**What was added:**
- Frontend sends `ping` every 30 seconds
- Backend responds with `pong`
- Detects silent disconnections

**Frontend (automatic):**
```typescript
// Sends every 30 seconds
ws.send(JSON.stringify({ type: 'ping' }));
```

**Backend (main.py:183-186):**
```python
if data.get("type") == "ping":
    logging.debug(f"Received ping from session: {session_id}, sending pong")
    await ws.send_json({"type": "pong"})
    continue
```

**Benefits:**
- ✅ Keeps connection alive through Cloud Run timeout
- ✅ Detects dead connections quickly
- ✅ Prevents "zombie" connections

---

### 3. Connection Status Indicator

**What was added:**
- Visual indicator showing connection state
- Component: `frontend/src/components/ConnectionStatus.tsx`

**States:**
- 🟢 Connected (hidden - clean UI)
- 🟡 Connecting...
- 🟠 Reconnecting...
- 🔴 Disconnected
- ⛔ Connection Failed

**Benefits:**
- ✅ User knows when connection is lost
- ✅ Clear feedback during reconnection
- ✅ User can wait instead of refreshing

---

### 4. Better Error Handling in PaymentPanel

**What was changed:**
```typescript
const notificationSent = sendMessage({
    event: 'payment_complete',
    status: 'success'
});

if (!notificationSent) {
    // Show error message to user
    const errorMessage: Message = {
        text: "⚠️ Payment completed, but there was a connection issue.
               Please refresh the page or contact support."
    };
    setMessages(prev => [...prev, errorMessage]);
}
```

**Benefits:**
- ✅ User notified if notification fails
- ✅ No silent failures
- ✅ Clear next steps provided

---

## SOLUTION 2: HTTP Fallback (RECOMMENDED - TO IMPLEMENT)

**Problem with Solution 1:** If WebSocket is completely dead, payment notification still fails.

**Solution:** Add HTTP POST fallback when WebSocket fails.

### Implementation Steps:

#### Step 1: Create Backend Endpoint

Add to `backend/main.py`:
```python
@app.post("/api/payment-complete")
async def payment_complete_fallback(request: Request):
    """
    HTTP fallback for payment completion when WebSocket is down.
    """
    try:
        data = await request.json()
        session_id = data.get("session_id")

        if not session_id:
            return JSONResponse(
                {"error": "session_id required"},
                status_code=400
            )

        logging.info(f"Payment complete via HTTP fallback for session: {session_id}")
        update_session_activity(session_id)

        # Process payment confirmation
        memory = get_memory_for_session(session_id)
        agent_executor = create_agent(memory)
        response = await agent_executor.ainvoke(
            {"input": "The payment has been verified. Please move on to shipping."}
        )

        return {"response": response.get("output")}

    except Exception as e:
        error_id = str(uuid.uuid4())
        logging.exception(f"Error {error_id} in payment-complete fallback: {e}")
        return JSONResponse(
            {"error": "Failed to process payment confirmation", "error_id": error_id},
            status_code=500
        )
```

#### Step 2: Update PaymentPanel

Replace the TODO in `PaymentPanel.tsx:94-99`:
```typescript
if (!notificationSent) {
    console.error("[PaymentPanel] Failed to send via WebSocket, trying HTTP fallback");

    try {
        const response = await fetch('/api/payment-complete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        });

        const data = await response.json();

        if (response.ok && data.response) {
            const aiMessage: Message = {
                id: (Date.now() + 3).toString(),
                text: data.response,
                sender: 'assistant',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, aiMessage]);
            console.info("[PaymentPanel] Payment confirmed via HTTP fallback");
        } else {
            throw new Error(data.error || 'HTTP fallback failed');
        }
    } catch (error) {
        console.error("[PaymentPanel] HTTP fallback also failed:", error);

        // Show error to user
        const errorMessage: Message = {
            id: (Date.now() + 2).toString(),
            text: "⚠️ Payment completed, but there was a connection issue. Please refresh the page or contact support with your payment confirmation.",
            sender: 'assistant',
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, errorMessage]);
    }
}
```

#### Step 3: Pass sessionId to PaymentPanel

Update `Index.tsx:197-206`:
```typescript
<PaymentPanel
    isOpen={isPanelOpen}
    setIsOpen={setPanelOpen}
    clientSecret={clientSecret}
    paypalOrderId={paypalOrderId}
    socket={ws}
    setMessages={setMessages}
    sendMessage={send}
    isSocketConnected={isConnected}
    sessionId={sessionId}  // ADD THIS
/>
```

---

## SOLUTION 3: Stripe Webhooks (BEST LONG-TERM SOLUTION)

**Why this is better:**
- ✅ No dependency on WebSocket or HTTP
- ✅ Stripe guarantees delivery
- ✅ Handles edge cases (browser crashes, network failures)
- ✅ Industry standard

### Implementation Steps:

#### Step 1: Create Webhook Endpoint

Add to `backend/main.py`:
```python
import stripe

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events for payment confirmation.
    This is the MOST RELIABLE way to confirm payments.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logging.error("Invalid payload in Stripe webhook")
        return JSONResponse({"error": "Invalid payload"}, status_code=400)
    except stripe.error.SignatureVerificationError:
        logging.error("Invalid signature in Stripe webhook")
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    # Handle checkout.session.completed event
    if event.type == "checkout.session.completed":
        session = event.data.object
        session_id = session.metadata.get("chat_session_id")

        logging.info(f"Payment confirmed via webhook for session: {session_id}")

        # Process fulfillment (idempotent)
        await fulfill_order(session_id)

    return {"received": True}


async def fulfill_order(session_id: str):
    """
    Fulfill order after payment confirmed.
    MUST be idempotent (safe to call multiple times).
    """
    # Check if already fulfilled
    # ... (implement with database or flag)

    memory = get_memory_for_session(session_id)
    agent_executor = create_agent(memory)
    response = await agent_executor.ainvoke(
        {"input": "The payment has been verified. Please move on to shipping."}
    )

    # Send response via WebSocket if available
    ws = get_websocket(session_id)
    if ws:
        try:
            await ws.send_json({
                "type": "agent_message",
                "ai_message": response.get("output")
            })
        except:
            logging.warning(f"Could not send via WebSocket for {session_id}")
```

#### Step 2: Configure Stripe Webhook

1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://your-app.run.app/webhooks/stripe`
3. Select events: `checkout.session.completed`
4. Copy webhook signing secret
5. Add to `.env`: `STRIPE_WEBHOOK_SECRET=whsec_...`

#### Step 3: Test Webhook Locally

```bash
# Install Stripe CLI
stripe listen --forward-to localhost:8080/webhooks/stripe

# Trigger test event
stripe trigger checkout.session.completed
```

---

## SOLUTION 4: Cloud Run Configuration

### Update Dockerfile

Add timeout configuration:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Add timeout for long-running WebSocket connections
CMD ["uvicorn", "backend.gateway:root", "--host", "0.0.0.0", "--port", "8080", "--timeout-keep-alive", "300"]
```

### Cloud Run Service Configuration

When deploying:
```bash
gcloud run deploy bharat-bazar \
    --image gcr.io/your-project/bharat-bazar \
    --platform managed \
    --region us-central1 \
    --timeout 300 \
    --min-instances 1 \
    --session-affinity
```

Or via YAML:
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: bharat-bazar
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        run.googleapis.com/sessionAffinity: "true"
    spec:
      timeoutSeconds: 300
      containerConcurrency: 40
      containers:
      - image: gcr.io/your-project/bharat-bazar
        env:
        - name: SESSION_TIMEOUT_HOURS
          value: "2"
```

---

## Testing Guide

### Test 1: Normal Connection

1. Open app in browser
2. Check console: "WebSocket connection established"
3. Top-right should show nothing (connected state)
4. Add item to cart
5. Checkout → payment should work

### Test 2: Reconnection

1. Open app
2. Open DevTools → Network tab
3. Find WebSocket connection
4. Right-click → "Close connection"
5. Watch connection status indicator appear (Reconnecting...)
6. Should auto-reconnect within 2-4 seconds
7. Try payment after reconnection

### Test 3: Payment During Disconnection

1. Open app, add items
2. Start checkout
3. When Stripe form appears, close WebSocket in DevTools
4. Complete payment
5. Should show error message with instructions
6. If HTTP fallback implemented: should recover automatically
7. If webhook implemented: fulfillment happens in background

### Test 4: Heartbeat

1. Open app
2. Watch browser console
3. Every 30 seconds: see "[WebSocket] Heartbeat sent"
4. Check backend logs: should see "Received ping" messages
5. Connection should stay alive indefinitely

---

## Cloud Run Deployment Checklist

- [ ] **Min instances = 1**: Prevent cold starts during checkout
- [ ] **Session affinity enabled**: Keep user on same instance
- [ ] **Timeout = 300s**: Allow long WebSocket connections
- [ ] **Health check configured**: `/health` endpoint
- [ ] **Stripe webhook configured**: For reliable payment processing
- [ ] **Environment variables set**: All secrets in Secret Manager
- [ ] **Logs monitored**: Set up alerts for connection failures

---

## What You Get With These Fixes

### Before (Current Problems):
- ❌ Connection drops silently
- ❌ Payment blocked without explanation
- ❌ User must refresh page
- ❌ Completed payments lost if WebSocket dies

### After (With All Solutions):
- ✅ Auto-reconnection within seconds
- ✅ Visual feedback when disconnected
- ✅ HTTP fallback if WebSocket fails
- ✅ Stripe webhook guarantees payment processing
- ✅ Heartbeat keeps connection alive
- ✅ Works reliably on Cloud Run

---

## Recommended Implementation Order

1. **✅ DONE**: Solution 1 (Reconnection + Heartbeat + Status UI)
2. **NEXT** (1 hour): Solution 2 (HTTP Fallback)
3. **THEN** (2 hours): Solution 3 (Stripe Webhooks) - MOST IMPORTANT
4. **FINALLY** (30 min): Solution 4 (Cloud Run Config)

**Total time to production-ready:** ~4 hours

---

## Questions?

- **Q: Do I need all solutions?**
  - A: Minimum: Solution 1 (done) + Solution 3 (webhooks). Solution 2 is nice-to-have.

- **Q: Will this work with multiple instances?**
  - A: Yes, with session affinity enabled. Webhooks work regardless.

- **Q: What if user's browser dies after payment?**
  - A: Solution 3 (webhooks) handles this - fulfillment happens server-side.

- **Q: How to test webhooks locally?**
  - A: Use Stripe CLI: `stripe listen --forward-to localhost:8080/webhooks/stripe`

- **Q: Performance impact of heartbeat?**
  - A: Negligible - tiny ping/pong every 30s
