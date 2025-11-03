import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send } from "lucide-react";
import { type Message } from "./ChatMessage";

interface ChatInputProps {
    onSendMessage: (message: string) => void;
    isLoading?: boolean;
    messages: Message[];
}

export const ChatInput = ({ onSendMessage, isLoading = false, messages }: ChatInputProps) => {
    const [message, setMessage] = useState("");
    const inputRef = useRef(null);

    useEffect(() => {
        if (inputRef.current) {
            inputRef.current.focus();
        }
    }, [messages]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (message.trim() && !isLoading) {
            onSendMessage(message.trim());
            setMessage("");
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    return (
        <div className="sticky bottom-0 w-full border-t border-border bg-background/95 backdrop-blur-sm px-4 py-4">
            <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
                <div className="flex items-end gap-3">
                    <div className="flex-1">
                        <Input
                            ref={inputRef}
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="Ask about products, add to cart, and proceed to payment..."
                            className="min-h-[44px] resize-none border-message-border focus:ring-primary/20 focus:border-primary transition-all duration-200"
                            disabled={isLoading}
                            autoFocus
                        />
                    </div>
                    <Button
                        type="submit"
                        disabled={!message.trim() || isLoading}
                        className="h-[44px] px-4 bg-primary hover:bg-primary/90 text-primary-foreground rounded-lg transition-all duration-200 disabled:opacity-50"
                    >
                        <Send className="w-4 h-4" />
                        <span className="sr-only">Send message</span>
                    </Button>
                </div>
                {isLoading && (
                    <div className="flex items-center gap-2 mt-2 text-muted-foreground">
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                        <div className="w-1.5 h-1.5 bg-primary rounded-full animate-bounce"></div>
                        <span className="text-sm">Agent is thinking...</span>
                    </div>
                )}
            </form>
        </div>
    );
};