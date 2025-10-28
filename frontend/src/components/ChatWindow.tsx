import { useEffect, useRef } from "react";
import { ChatMessage, type Message } from "./ChatMessage";

interface ChatWindowProps {
    messages: Message[];
}

export const ChatWindow = ({ messages }: ChatWindowProps) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    return (
        <div className="flex-1 overflow-y-auto px-4 py-6 bg-chat-bg">
            {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                        <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-primary to-orange-500 rounded-full flex items-center justify-center shadow-lg">
                            <span className="text-2xl">🫖</span>
                        </div>
                        <h2 className="text-xl font-semibold text-foreground mb-2">
                            Welcome to Bharat Bazar
                        </h2>
                        <p className="text-muted-foreground max-w-sm">
                            Enter your name to get started or continue as guest!
                        </p>
                    </div>
                </div>
            ) : (
                <div className="max-w-4xl mx-auto">
                    {messages.map((message) => (
                        <ChatMessage key={message.id} message={message} />
                    ))}
                    <div ref={messagesEndRef} />
                </div>
            )}
        </div>
    );
};