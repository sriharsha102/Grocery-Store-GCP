
# 🛒 AI-Powered E-Commerce Chatbot with GCP Integration

An intelligent e-commerce platform featuring an AI-driven chat interface, multi-channel payment processing, inventory management via Google Sheets, and email notifications. Built with FastAPI and React, deployed on Google Cloud Platform.

## 📋 Table of Contents
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Token Management](#token-management)
- [Error Handling](#error-handling)
- [Deployment](#deployment)

## ✨ Features

### Core Features
- **AI Chat Interface**: Real-time conversational shopping experience with WebSocket support
- **Multi-Payment Support**: Stripe, PayPal, and Apple Pay integration
- **Inventory Management**: Connected to Google Sheets for real-time stock updates
- **Smart Product Recommendations**: AI-powered product suggestions based on user preferences
- **Order Processing**: Automated order creation and fulfillment workflow
- **Email Notifications**: Integration with Gmail for order confirmations and updates
- **Dark/Light Theme**: Theming support for enhanced user experience
- **Responsive UI**: Mobile-friendly React interface with Tailwind CSS

### Technical Features
- Real-time WebSocket connections with automatic reconnection
- Token management for secure API authentication
- Comprehensive error handling and logging
- Docker-ready deployment configuration

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn
- **Database**: Google Sheets (DAL layer)
- **APIs**: Stripe, PayPal, Apple Pay, Google Sheets API, Gmail API, FedEx API
- **Authentication**: OAuth 2.0 for third-party services

### Frontend
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: Shadcn/ui
- **State Management**: React Hooks
- **Communication**: WebSocket & REST API

### Infrastructure
- **Deployment**: Google Cloud Platform (App Service/Cloud Run)
- **Containerization**: Docker
- **Package Management**: pip (Python), npm/bun (Node.js)

## 📁 Project Structure

```
├── backend/                    # FastAPI backend application
│   ├── main.py                # Application entry point
│   ├── gateway.py             # WebSocket gateway & routing
│   ├── tools/                 # Tool implementations
│   │   ├── cart/              # Shopping cart operations
│   │   ├── payment/           # Payment processing (Stripe, PayPal, Apple Pay)
│   │   ├── product/           # Product catalog & recommendations
│   │   ├── sheets/            # Google Sheets operations
│   │   └── suggestions/       # Product suggestions
│   ├── integrations/          # External service integrations
│   │   ├── gmail/             # Email sending
│   │   └── google_sheets/     # Spreadsheet operations
│   ├── state/                 # State management
│   │   ├── chat_state.py      # Chat session state
│   │   └── session.py         # User sessions
│   └── routers/               # API routers
│
├── frontend/                  # React frontend application
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── ChatWindow.tsx # Main chat interface
│   │   │   ├── PaymentPanel/  # Payment processing UI
│   │   │   └── ui/            # UI component library
│   │   ├── hooks/             # Custom React hooks
│   │   └── App.tsx            # Main App component
│   └── package.json           # Node dependencies
│
├── Dockerfile                 # Docker configuration
└── requirements.txt           # Python dependencies
```

## 📋 Prerequisites

- **Python 3.9+**
- **Node.js 16+** (or Bun)
- **npm/bun** for frontend development
- **Google Cloud Account** with credentials
- **API Keys**: Stripe, PayPal, FedEx (optional for testing)

## 🚀 Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/sriharsha102/Grocery-Store-GCP.git
cd Grocery-Store-GCP
```

### 2. Backend Setup

Create and activate virtual environment:

**macOS/Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install Python dependencies:
```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

### 3. Frontend Setup

Install Node dependencies:
```bash
cd frontend
npm install
```

Or using Bun:
```bash
bun install
```

### 4. Build Frontend
```bash
cd frontend
npm run build
```

### 5. Copy Frontend Dist to Backend Static

Linux/macOS:
```bash
rm -rf backend/static
mkdir -p backend/static
cp -R frontend/dist/* backend/static/
```

Windows (PowerShell):
```powershell
Remove-Item "backend\static" -Recurse -Force
mkdir backend\static
Copy-Item frontend\dist\* backend\static\ -Recurse
```

## ⚙️ Configuration

### Backend Environment Variables (`.env`)

Create a `.env` file in the `backend/` directory:

```env
# Core Configuration
DEBUG=true
PORT=8000

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Payment Processors
STRIPE_API_KEY=sk_test_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx
PAYPAL_CLIENT_ID=xxxxx
PAYPAL_CLIENT_SECRET=xxxxx

# Email Configuration
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password

# Third-party APIs
FEDEX_API_KEY=xxxxx
```

### Frontend Environment Variables (`.env`)

Create a `.env` file in the `frontend/` directory:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
VITE_MODE=development
```

### Google Cloud Setup

1. Create a service account in Google Cloud Console
2. Download the service account JSON key
3. Place it in `backend/service-account.json`
4. Enable required APIs:
   - Google Sheets API
   - Gmail API

## 🏃 Running the Application

### Backend (Terminal 1)

```bash
cd backend
uvicorn gateway:root --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend (Terminal 2)

**Development:**
```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173`

**Production Build:**
```bash
cd frontend
npm run build
npm run preview
```

### Combined Production Mode

Serve frontend from backend static folder:

```bash
cd backend
uvicorn gateway:root --port 8000
```

Visit `http://localhost:8000` to access the application.

## 🔐 Token Management

The application automatically manages authentication tokens for various services:

### View Current Tokens

```bash
curl http://localhost:8000/tokens
```

### Manual Token Refresh

If tokens expire or you need to re-authenticate:

```bash
curl http://localhost:8000/auth/authorize
```

This returns an authorization URL. Open it in your browser and follow the authentication flow.

### Token Expiration Handling

- **Access Tokens**: Automatically refreshed when expired (1 hour lifespan)
- **Refresh Tokens**: Valid for extended periods (check service documentation)
- **Manual Re-auth**: Only required if refresh token expires or credentials change

## ⚠️ Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Expired authentication token | Tokens auto-refresh; check error logs for details |
| `400 Bad Request` | Invalid API request | Validate request payload and API configuration |
| `Connection Refused` | Backend service not running | Ensure uvicorn is running on port 8000 |
| `WebSocket Connection Failed` | Frontend unable to reach backend | Check VITE_WS_URL and backend availability |
| `Google Sheets API Error` | Service account not authorized | Verify service account has Sheets API access |
| `Payment Processing Failed` | Invalid payment credentials | Check Stripe/PayPal keys in .env file |

### Debug Mode

Enable detailed logging:

```bash
export DEBUG=true
uvicorn gateway:root --reload --port 8000 --log-level debug
```

## 🚀 Deployment

### Docker Deployment

Build and run with Docker:

```bash
docker build -t grocery-store-gcp .
docker run -p 8000:8000 --env-file .env grocery-store-gcp
```

### Google Cloud Deployment

Deploy to Cloud Run:

```bash
gcloud build submit --tag gcr.io/PROJECT_ID/grocery-store-gcp
gcloud run deploy grocery-store-gcp \
  --image gcr.io/PROJECT_ID/grocery-store-gcp \
  --platform managed \
  --region us-central1 \
  --set-env-vars DEBUG=false
```

## 📝 Environment

**Deactivate Virtual Environment:**
```bash
deactivate
```

---

## 📞 Support & Troubleshooting

For detailed logs and debugging information, enable debug mode:

```bash
DEBUG=true
```

Check the backend console for detailed error messages and WebSocket connection status.

## 👨‍💻 Contributing

1. Create a feature branch (`git checkout -b feature/amazing-feature`)
2. Commit your changes (`git commit -m 'Add amazing feature'`)
3. Push to the branch (`git push origin feature/amazing-feature`)
4. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙋 Questions?

For issues, questions, or suggestions, please open an issue on GitHub or contact the development team.
