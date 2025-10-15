
# Project Setup & Token Management Guide

## 1. Create & Activate Virtual Environment

```bash
python -m venv .venv
```

- On **Windows (PowerShell)**:
```powershell
.venv\Scripts\Activate.ps1
```

- On **macOS/Linux**:
```bash
source .venv/bin/activate
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```
in both frontend and backend directories
---

## 3. QuickBooks Token Smoke Test - optional

This step is meant as a sanity check to see if your QuickBooks token refresh flow is actually working before you run the full chatbot.

```bash
python qb_refresh_smoketest.py
```

---
## 4. To copy frontend/dist to backend/static run the following commands:
```bash
           mkdir -p backend/static
           cp -R frontend/dist/* backend/static/

```
## 5. Execute the following new powershell

```bash
npm install
npm run build
```
## 6. Start the Application

Run the following command in backend directory
```bash
uvicorn gateway:root --reload --port 8000
```
---

## 7. Token Management (QuickBooks) -check this step only if you get token related issues

The code in the `chatbot_fastapi_tools_tokens` branch uses `token_service.py`, a FastAPI microservice, to manage and refresh QuickBooks API tokens.

- When the `access_token` (valid for 1 hour) expires, the backend automatically detects a `401 Unauthorized` response and triggers a refresh by calling the `/token/refresh` endpoint on `http://localhost:8000`.
- This uses the `refresh_token` (valid for 100 days) to get a new access token from Intuit's servers.

### To view the latest tokens:
```bash
curl http://localhost:8000/token
```

This will return the current `access_token` and `refresh_token` in JSON format.


If the refresh token itself expires (rare, after long inactivity), a manual re-authentication via browser is required to obtain new credentials.

## Run following cmd in root folder
```bash
curl http://127.0.0.1:8000/token/quickbooks/authorize | ConvertFrom-Json | Select-Object -ExpandProperty authorize_url
```
copy paste the give url into browser (url should look something like this - https://appcenter.intuit.com/connect/oauth2?...)
when you copy paste it into browser make sure to remove "api/" from the url
you will get the "Quickbook connected" message in the browser, now rerun step 6.
---



## 8. Deactivating the Environment

When you are finished working on the project, you can deactivate the environment and return to your global Python context by simply running:
```bash
deactivate
```

---

## 9. Error Handling Tips

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Expired access token | Ensure token service is running; it should refresh automatically |
| `invalid_grant` | Expired/invalid refresh token | Delete `.tokens.json` and re-authorize |
| `connection refused` | Token service not running | Start it with `uvicorn backend.token_service:app --reload --port 8000` |
| `file not found` | `.tokens.json` missing | Re-run the authorization flow |

---

## 10. Environment Variables (`.env`)

Your `.env` file must include:
```env
QUICKBOOKS_CLIENT_ID=your_client_id
QUICKBOOKS_CLIENT_SECRET=your_client_secret
QUICKBOOKS_REDIRECT_URI=http://localhost:8000/api/token/quickbooks/callback
QUICKBOOKS_ENVIRONMENT=sandbox
```

---

**Now you are ready to run the chatbot with automatic QuickBooks token refresh!**
