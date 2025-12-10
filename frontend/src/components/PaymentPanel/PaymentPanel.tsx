import React, { useState, Dispatch, SetStateAction, useCallback, useEffect } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { EmbeddedCheckoutProvider, EmbeddedCheckout } from '@stripe/react-stripe-js';
import { type Message } from "@/components/ChatMessage";
import './Payment.css';
import { PayPalButtons, PayPalScriptProvider } from '@paypal/react-paypal-js';
import { CreateOrderActions, OnApproveActions } from '@paypal/paypal-js';

// Log the Stripe key availability at module load
const STRIPE_KEY = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY as string;
console.log('[PaymentPanel] Stripe key available:', STRIPE_KEY ? 'Yes' : 'No');
if (STRIPE_KEY) {
    console.log('[PaymentPanel] Stripe key prefix:', STRIPE_KEY.substring(0, 20) + '...');
}

const stripePromise = loadStripe(STRIPE_KEY);
const PAYPAL_CLIENT_ID = import.meta.env.VITE_PAYPAL_CLIENT_ID as string

// Define the type for the component's props
interface PaymentPanelProps {
    isOpen: boolean,
    setIsOpen: Dispatch<SetStateAction<boolean>>,
    clientSecret: string,
    paypalOrderId: string,
    socket: WebSocket | null,
    setMessages: Dispatch<SetStateAction<Message[]>>,
    sendMessage: (data: any) => boolean,
    isSocketConnected: boolean
}

function PaymentPanel({
    isOpen,
    setIsOpen,
    clientSecret,
    paypalOrderId,
    socket,
    setMessages,
    sendMessage,
    isSocketConnected
}: PaymentPanelProps) {


    const initialOptions = {
        "clientId": PAYPAL_CLIENT_ID,
        "enable-funding": "venmo",
        "disable-funding": "",
        "buyer-country": "US",
        currency: "USD",
        "data-page-type": "product-details",
        components: "buttons",
        "data-sdk-integration-source": "developer-studio",
    };

    // console.log("Client Secret in PaymentPanel:", clientSecret);
    const [isComplete, setIsComplete] = useState(false);
    const [open, setOpen] = useState(false);

    // Log panel state changes for debugging
    useEffect(() => {
        if (isOpen) {
            console.log('[PaymentPanel] Panel opened');
            console.log('[PaymentPanel] Client secret available:', clientSecret ? 'Yes' : 'No');
            console.log('[PaymentPanel] Stripe promise:', stripePromise ? 'Initialized' : 'Not initialized');
        }
    }, [isOpen, clientSecret]);

    // Prevent clicks inside the panel from closing it
    const handlePanelClick = (e: React.MouseEvent<HTMLDivElement>) => {
        e.stopPropagation();
    };


    // useEffect(() => {
    //     scrollToBottom();
    // }, [isComplete]);

    const handleComplete = useCallback(() => {
        console.log("[PaymentPanel] Payment completed!");

        // Show confirmation message
        const aiMessage: Message = {
            id: (Date.now() + 1).toString(),
            text: "Please wait while I confirm your payment.",
            sender: 'assistant',
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, aiMessage]);

        setIsComplete(true);
        setIsOpen(false);

        // Attempt to send payment complete notification via WebSocket
        const notificationSent = sendMessage({
            event: 'payment_complete',
            status: 'success'
        });

        if (!notificationSent) {
            console.error("[PaymentPanel] Failed to send payment notification via WebSocket");

            // Show error message to user
            const errorMessage: Message = {
                id: (Date.now() + 2).toString(),
                text: "⚠️ Payment completed, but there was a connection issue. Please refresh the page or contact support with your payment confirmation.",
                sender: 'assistant',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMessage]);

            // TODO: Implement HTTP fallback here (Solution 2)
            // Example:
            // fetch('/api/payment-complete', {
            //     method: 'POST',
            //     body: JSON.stringify({ session_id: sessionId })
            // });
        } else {
            console.info("[PaymentPanel] Payment notification sent successfully");
        }
    }, [sendMessage, setMessages, setIsComplete, setIsOpen]);

    return (
        <>
            {/* Backdrop: Only renders when the panel is open */}
            {isOpen && (
                <div
                    className="panel-backdrop"
                    onClick={() => (setIsOpen(false))}
                ></div>
            )}

            {/* Main Panel */}
            <div className={`payment-panel ${isOpen ? 'open' : ''}`}
                onClick={handlePanelClick}>
                <div className="panel-header">
                    <h2>Complete Your Payment</h2>
                    <button className="close-btn" onClick={() => (setIsOpen(false))}>
                        &times; {/* A simple 'X' icon */}
                    </button>
                </div>

                <div className="panel-body flex-1 min-h-0 overflow-y-auto overscroll-contain">
                {/* <div className="flex-grow p-4 overflow-y-auto min-h-0"> */}
                    {/* Only render the Stripe Checkout when the clientSecret is available. */}
                    {!clientSecret ? (
                        <div className="flex items-center justify-center h-full">
                            <p>Initializing payment...</p>
                        </div>
                    ) : !STRIPE_KEY ? (
                        <div className="flex items-center justify-center h-full">
                            <p style={{color: 'red'}}>Error: Stripe configuration missing. Please contact support.</p>
                        </div>
                    ) : clientSecret && stripePromise ? (
                        <EmbeddedCheckoutProvider
                            key={clientSecret}
                            stripe={stripePromise}
                            options={{ clientSecret, onComplete: handleComplete }}
                        >
                            <EmbeddedCheckout />
                        </EmbeddedCheckoutProvider>
                    ) : (
                        <div className="flex items-center justify-center h-full">
                            <p>Loading payment options...</p>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

export default PaymentPanel;