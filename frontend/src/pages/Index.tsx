import { useState, useEffect, useMemo, useCallback } from "react";
import { ChatWindow } from "@/components/ChatWindow";
import { ChatInput } from "@/components/ChatInput";
import { ThemeToggle } from "@/components/ThemeToggle";
import { type Message } from "@/components/ChatMessage";
import { v4 as uuidv4 } from 'uuid';
import PaymentPanel from "@/components/PaymentPanel/PaymentPanel";
import { useReconnectingWebSocket, WebSocketStatus } from "@/hooks/useReconnectingWebSocket";

// Define the shape of the expected API response
interface ApiResponse {
    response?: string;
    error?: string;
}

const Index = () => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId] = useState<string>(() => uuidv4()); // Generate once
    const [isPanelOpen, setPanelOpen] = useState(false);
    const [showPaymentPanelButton, setShowPaymentPanelButton] = useState(false);
    const [clientSecret, setClientSecret] = useState('');
    const [paypalOrderId, setPaypalOrderId] = useState('');

    // Construct WebSocket URL
    const wsUrl = useMemo(() => {
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        return `${protocol}://${window.location.host}/api/ws/${sessionId}`;
    }, [sessionId]);

    // Memoized WebSocket callbacks to prevent reconnection loop
    const handleWebSocketOpen = useCallback(() => {
        console.info("Index: WebSocket connection established successfully!");
        console.info(`Index: Session UUID: ${sessionId}`);
    }, [sessionId]);

    const handleWebSocketClose = useCallback((event: CloseEvent) => {
        console.warn(`Index: WebSocket disconnected. Code: ${event.code}, Reason: ${event.reason}`);
    }, []);

    const handleWebSocketMessage = useCallback((event: MessageEvent) => {
        try {
            const msg = JSON.parse(event.data);
            console.debug("Index: WebSocket message received:", msg);

            if (msg.type === 'payment_intent_created' && msg.client_secret) {
                console.info(`Index: Received 'payment_intent_created' event.`);
                console.debug(`Index: Client Secret: ${msg.client_secret.substring(0, 10)}...`);

                setClientSecret(msg.client_secret);

                if (msg.paypal_order_id) {
                    setPaypalOrderId(msg.paypal_order_id);
                    console.info(`Index: Paypal order id: ${msg.paypal_order_id}`);
                }

                setPanelOpen(true);
                setShowPaymentPanelButton(true);
            } else if (msg.type === 'agent_message' && msg.ai_message) {
                console.info(`Index: Received 'agent_message' event.`);
                const aiMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    text: msg.ai_message,
                    sender: 'assistant',
                    timestamp: new Date(),
                };
                setMessages(prev => [...prev, aiMessage]);
                setIsLoading(false);
            } else {
                console.warn(`Index: Received unknown message type or incomplete data:`, msg);
            }
        } catch (e) {
            console.error("Index: Failed to parse WebSocket message:", e);
            setIsLoading(false);
        }
    }, []);

    const handleWebSocketError = useCallback((error: Event) => {
        console.error("Index: WebSocket error: ", error);
    }, []);

    // Use reconnecting WebSocket hook with memoized callbacks
    const { ws, status, isConnected, send } = useReconnectingWebSocket(wsUrl, {
        onOpen: handleWebSocketOpen,
        onClose: handleWebSocketClose,
        onMessage: handleWebSocketMessage,
        onError: handleWebSocketError,
        heartbeatInterval: 60000, // 30 seconds
        reconnectInterval: 5000, // 2 seconds
        maxReconnectAttempts: 10,
    });

    // Display initial welcome message
    useEffect(() => {
        const timer = setTimeout(() => {
            const initialMessage: Message = {
                id: Date.now().toString(),
                text:
                "Welcome to Bharat Bazar! 🛍️ - I’m your smart shopping assistant. \n\n" +
                "What are you shopping today? I can help you find it 😊\n\n" +
                "🥬 Veggies\n\n" +
                "🌾 Rice & Wheat\n\n" +
                "🍜 Pulses / Daliya / Poha / Noodles\n\n" +
                "🌶️ Spices\n\n" +
                "🍿 Snacks",
                sender: 'assistant',
                timestamp: new Date()
            };
            setMessages(prev => [...prev, initialMessage]);
            console.info("Index: Initial welcome message displayed.");
        }, 1000);

        return () => clearTimeout(timer);
    }, []);

    const handleSendMessage = async (messageText: string) => {
        console.info(`Index: User is sending a message to the backend: '${messageText}'`);
        
        const userMessage: Message = {
            id: Date.now().toString(),
            text: messageText,
            sender: 'user',
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setIsLoading(true);

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: messageText, session_id: sessionId }),
            });

            console.info(`Index: Received HTTP response with status: ${response.status}`);
            const data: ApiResponse = await response.json();

            if (data.response) {
                console.debug("Index: Backend response:", data.response);
                const aiMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    text: data.response,
                    sender: 'assistant',
                    timestamp: new Date(),
                };
                setMessages((prevMessages) => [...prevMessages, aiMessage]);
            } else {
                console.error('Index: Error from backend:', data.error);
                const errorMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    text: "Sorry, something went wrong: " + data.error,
                    sender: 'assistant',
                    timestamp: new Date(),
                };
                setMessages((prevMessages) => [...prevMessages, errorMessage]);
            }
        } catch (error) {
            console.error('Index: Failed to fetch from backend:', error);
            const errorMessage: Message = {
                id: (Date.now() + 1).toString(),
                text: "Sorry, I couldn't connect to the server",
                sender: 'assistant',
                timestamp: new Date(),
            };
            setMessages((prevMessages) => [...prevMessages, errorMessage]);
        }

        setIsLoading(false);
    };

    return (
        <div className="h-screen flex flex-col bg-gradient-to-b from-background to-chat-bg ">
            {/* Header */}
            <div className="border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
                <div className="max-w-4xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-gradient-to-br from-primary to-orange-500 rounded-full flex items-center justify-center">
                            <span className="text-sm">🛍️</span>
                        </div>
                        <div>
                            <h1 className="font-semibold text-[hsl(var(--header-text))]">Bharat Bazar</h1>
                            <p className="text-xs text-muted-foreground">AI E-commerce Assistant</p>
                        </div>
                    </div>
                    <ThemeToggle />
                </div>
            </div>

            {/* Chat Window */}
            <div className="flex  flex-1">
                <ChatWindow messages={messages} />
                {/* Payment panel button appears once payment is ready to be taken so that if the user accidentally closes it, they can reopen */}
                {showPaymentPanelButton && (
                    <button
                        className="toggle-payment-button"
                        onClick={() => {
                            console.info(`Index: Toggling payment panel. Current state: ${!isPanelOpen}`);
                            setPanelOpen(!isPanelOpen);
                        }}
                        aria-label="Toggle panel"
                    >
                        {isPanelOpen ? '›' : '‹'}
                    </button>
                )}
            </div>

            {/* Chat Input */}
            <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} messages={messages} />

            <PaymentPanel
                isOpen={isPanelOpen}
                setIsOpen={setPanelOpen}
                clientSecret={clientSecret}
                paypalOrderId={paypalOrderId}
                socket={ws}
                setMessages={setMessages}
                sendMessage={send}
                isSocketConnected={isConnected}
            />
        </div>
    );
};

export default Index;
