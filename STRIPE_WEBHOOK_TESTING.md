# Stripe Webhook Testing Guide

## Quick Start (Local Testing)

### Prerequisites
- Stripe CLI installed
- Backend running on `localhost:8080`

### Step 1: Install Stripe CLI

**Mac:**
```bash
brew install stripe/stripe-cli/stripe
```

**Windows:**
```bash
scoop install stripe
```

**Linux:**
```bash
curl -s https://packages.stripe.com/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.com/stripe-cli-debian-local stable main" | sudo tee /etc/apt/sources.list.d/stripe.list
sudo apt update
sudo apt install stripe
```

### Step 2: Login to Stripe CLI

```bash
stripe login
```

This will open your browser to authorize the CLI with your Stripe account.

### Step 3: Start Your Backend

```bash
cd backend
uvicorn gateway:root --reload --port 8080
```

You should see:
```
⚠️ STRIPE_WEBHOOK_SECRET not set - webhook endpoint will accept unverified requests (DEV ONLY)
```

This is OK for local testing!

### Step 4: Forward Webhooks to Local Server

Open a **new terminal** and run:

```bash
stripe listen --forward-to localhost:8080/webhooks/stripe
```

You'll see output like:
```
> Ready! You are using Stripe API Version [2024-12-05]. Your webhook signing secret is whsec_xxxxxxxxxxxxx (^C to quit)
```

**IMPORTANT:** Copy the webhook signing secret (`whsec_xxxxxxxxxxxxx`)

### Step 5: (Optional) Add Webhook Secret to .env

For production-like testing, add to `backend/.env`:

```env
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
```

Then restart your backend. You should now see:
```
Stripe webhook secret configured - webhook endpoint will verify signatures
```

---

## Testing the Webhook

### Test 1: Trigger Test Event

In another terminal:

```bash
stripe trigger checkout.session.completed
```

**Expected Output:**

Backend logs should show:
```
📨 Stripe webhook received: type=checkout.session.completed, id=evt_xxx
⚠️ Webhook signature verification SKIPPED (dev mode)  [if no secret]
❌ Webhook missing chat_session_id in metadata for Stripe session cs_test_xxx
```

This is **expected** - test events don't have your metadata. Let's test with a real payment next.

---

### Test 2: Real Payment Flow Test

#### Step 1: Start Everything

1. Terminal 1: `uvicorn gateway:root --reload --port 8080`
2. Terminal 2: `stripe listen --forward-to localhost:8080/webhooks/stripe`
3. Terminal 3: `cd frontend && npm run dev`

#### Step 2: Make a Test Purchase

1. Open http://localhost:5173
2. Add items to cart
3. Say "I want to checkout"
4. Complete payment with test card: `4242 4242 4242 4242`
   - Any future expiry date
   - Any 3-digit CVC
   - Any billing address

#### Step 3: Watch the Logs

**Stripe CLI Terminal (Terminal 2):**
```
2024-12-08 10:15:32   --> checkout.session.completed [evt_xxxxx]
2024-12-08 10:15:32  <--  [200] POST http://localhost:8080/webhooks/stripe [evt_xxxxx]
```

**Backend Terminal (Terminal 1):**
```
📨 Stripe webhook received: type=checkout.session.completed, id=evt_xxxxx
💳 Payment completed - Stripe ID: cs_test_xxxxx, Chat session: abc-123-def, Status: paid
Starting order fulfillment for session abc-123-def
✅ Successfully fulfilled order for session abc-123-def
```

**Frontend:**
- You should see the AI ask for your email
- After providing email, receipt is sent
- Cart is cleared

---

## Test 3: Test Idempotency

### Simulate Duplicate Webhook

Stripe sends the same `checkout.session.completed` event twice:

```bash
# First webhook
stripe trigger checkout.session.completed

# Immediately send again (simulating retry)
stripe trigger checkout.session.completed
```

**Expected Backend Logs:**
```
# First webhook
Starting order fulfillment for session xxx
✅ Successfully fulfilled order for session xxx

# Second webhook (duplicate)
Order already fulfilled for Stripe session cs_test_xxx at 2024-12-08T10:15:32
```

✅ **Second webhook should be skipped** (idempotency working!)

---

## Test 4: Test with WebSocket Disconnected

### Simulate Browser Crash

1. Add items and checkout
2. **Before paying**, open DevTools → Network
3. Find WebSocket connection
4. Right-click → Close connection
5. **Now complete payment** on Stripe form

**Expected Behavior:**
- Frontend shows error: "connection issue, please refresh"
- **Webhook still arrives** 2-5 seconds later
- Backend fulfills order anyway
- Refresh page → cart is cleared, order fulfilled

**Backend Logs:**
```
No active WebSocket for abc-123-def. User will see update when they reconnect.
✅ Successfully fulfilled order for session abc-123-def
```

✅ **Order fulfilled despite WebSocket being dead!**

---

## Production Testing (Cloud Run)

### Step 1: Deploy to Cloud Run

```bash
gcloud run deploy bharat-bazar \
    --image gcr.io/your-project/bharat-bazar \
    --region us-central1 \
    --platform managed
```

Get the URL: `https://bharat-bazar-xxxxx.run.app`

### Step 2: Configure Stripe Webhook in Dashboard

1. Go to https://dashboard.stripe.com/webhooks
2. Click "+ Add endpoint"
3. Enter URL: `https://bharat-bazar-xxxxx.run.app/webhooks/stripe`
4. Select events:
   - ✅ `checkout.session.completed`
   - ✅ `checkout.session.expired` (optional)
5. Click "Add endpoint"
6. **Copy the "Signing secret"** (whsec_xxxxx)

### Step 3: Add Secret to Cloud Run

```bash
# Create secret
echo -n "whsec_xxxxxxxxxxxxx" | gcloud secrets create stripe-webhook-secret --data-file=-

# Grant access to Cloud Run service
gcloud secrets add-iam-policy-binding stripe-webhook-secret \
    --member=serviceAccount:YOUR-SERVICE-ACCOUNT@developer.gserviceaccount.com \
    --role=roles/secretmanager.secretAccessor

# Update Cloud Run service
gcloud run services update bharat-bazar \
    --update-secrets=STRIPE_WEBHOOK_SECRET=stripe-webhook-secret:latest \
    --region us-central1
```

### Step 4: Test Production Webhook

1. Open your production site
2. Make a test purchase (use test mode in Stripe)
3. Check Cloud Run logs:

```bash
gcloud run logs read bharat-bazar --region us-central1 --limit 50
```

**Expected Logs:**
```
Stripe webhook secret configured - webhook endpoint will verify signatures
📨 Stripe webhook received: type=checkout.session.completed
✅ Webhook signature verified for event evt_xxxxx
💳 Payment completed - Stripe ID: cs_xxxxx
✅ Successfully fulfilled order
```

---

## Troubleshooting

### Issue: "No signature header"

**Cause:** Stripe webhook not configured correctly

**Fix:**
1. Check webhook URL in Stripe Dashboard
2. Ensure URL is `https://your-domain/webhooks/stripe` (no typos!)

---

### Issue: "Invalid signature"

**Cause:** Wrong webhook secret

**Fix:**
1. Get the correct signing secret from Stripe Dashboard → Webhooks → Your Endpoint → Signing secret
2. Update `STRIPE_WEBHOOK_SECRET` in your environment
3. Restart backend

---

### Issue: "Webhook missing chat_session_id"

**Cause:** Test events don't have metadata, OR metadata not set during checkout creation

**Fix for real payments:**

Check `backend/tools/payment/trigger_payment.py:163-170`:
```python
checkout_session = stripe.checkout.Session.create(
    ...
    metadata={"chat_session_id": session_id},  # ← This must be present!
)
```

---

### Issue: Webhook arrives but order not fulfilled

**Check:**
1. Backend logs for errors in `fulfill_order_webhook`
2. Is the agent properly calling finalize_stock and place_order?
3. Check Google Sheets connectivity

**Debug:**
```bash
# Check fulfilled_orders dictionary
# Add to backend code temporarily:
logger.info(f"Fulfilled orders: {fulfilled_orders}")
```

---

### Issue: Duplicate fulfillment (stock decremented twice)

**Cause:** Idempotency not working

**Check:**
1. Is `stripe_session_id` correctly used as key?
2. Are you calling fulfillment outside of webhook?

**Fix:** Ensure only webhook calls `fulfill_order_webhook`

---

## Webhook Event Examples

### checkout.session.completed (Success)

```json
{
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_xxxxx",
      "payment_status": "paid",
      "customer_details": {
        "email": "customer@example.com"
      },
      "metadata": {
        "chat_session_id": "abc-123-def-456"
      }
    }
  }
}
```

### checkout.session.expired (Abandoned)

```json
{
  "type": "checkout.session.expired",
  "data": {
    "object": {
      "id": "cs_test_xxxxx",
      "status": "expired",
      "metadata": {
        "chat_session_id": "abc-123-def-456"
      }
    }
  }
}
```

---

## Performance Expectations

| Metric | Expected Value |
|--------|---------------|
| Webhook delivery time | 2-5 seconds after payment |
| Webhook retry attempts | Up to 3 days |
| Webhook timeout | 30 seconds |
| Idempotency guarantee | 100% (same stripe_session_id) |

---

## Security Checklist

- [ ] `STRIPE_WEBHOOK_SECRET` is set in production
- [ ] Webhook signature verification is enabled (not skipped)
- [ ] Webhook endpoint is HTTPS (not HTTP)
- [ ] Logs don't expose sensitive data
- [ ] Webhook secret is stored in Secret Manager (not .env in repo)

---

## Next Steps

1. ✅ Test locally with Stripe CLI
2. ✅ Test duplicate webhook handling
3. ✅ Test with WebSocket disconnected
4. ✅ Deploy to Cloud Run
5. ✅ Configure production webhook
6. ✅ Test production payment flow
7. 📋 Monitor webhook deliveries in Stripe Dashboard
8. 📋 Set up alerting for failed webhooks

---

## Monitoring Webhooks in Production

### Stripe Dashboard

1. Go to https://dashboard.stripe.com/webhooks
2. Click on your endpoint
3. View:
   - Recent deliveries
   - Failed attempts
   - Response status codes

### Cloud Run Logs

```bash
# View recent webhook logs
gcloud run logs read bharat-bazar \
    --region us-central1 \
    --limit 100 \
    --filter "webhooks/stripe"

# Follow live logs
gcloud run logs tail bharat-bazar --region us-central1
```

### Set Up Alerts

```bash
# Alert on webhook failures
gcloud logging metrics create webhook-failures \
    --description="Failed Stripe webhooks" \
    --log-filter='resource.type="cloud_run_revision"
    textPayload=~"Error.*webhook"'
```

---

## Summary

✅ **What You Get with Webhooks:**
- Payment fulfillment works even if browser crashes
- Automatic retries for up to 3 days
- Idempotent processing (no duplicate orders)
- Independent of WebSocket connection
- Industry-standard reliability

🎯 **Production Ready:** Yes! This is how Stripe recommends handling payments.

💡 **Tip:** Keep both WebSocket notification AND webhooks - they complement each other for best UX + reliability.
