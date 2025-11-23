import { cn } from "@/lib/utils";
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface Message {
    id: string;
    text: string;
    sender: "user" | "assistant";
    timestamp: Date;
}

interface ChatMessageProps {
    message: Message;
}

export const ChatMessage = ({ message }: ChatMessageProps) => {
    const isUser = message.sender === "user";

    // Markdown renderer (fixed — DOES NOT override <p>)
    const MarkdownText = ({ text }: { text: string }) => (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                strong: ({ children }) => (
                    <strong className="font-semibold">{children}</strong>
                ),
                em: ({ children }) => (
                    <em className="italic">{children}</em>
                ),
                li: ({ children }) => (
                    <li className="ml-4 list-disc">{children}</li>
                ),
                code: ({ children }) => (
                    <code className="bg-black/20 px-1 py-0.5 rounded text-sm">
                        {children}
                    </code>
                ),
            }}
        >
            {text}
        </ReactMarkdown>
    );

    // Button extraction + markdown logic
    const renderMessageContent = () => {
        const linkRegex = /(?:📄\s*)?\[(.?)\]\((.?)\)\.?/;
        const match = message.text.match(linkRegex);

        if (!match) {
            return <MarkdownText text={message.text} />;
        }

        const [fullMatch, buttonText, url] = match;
        const parts = message.text.split(fullMatch);
        const textBefore = parts[0];
        const textAfter = parts[1];

        return (
            <>
                {textBefore && <MarkdownText text={textBefore} />}

                {/* Button */}
                <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={cn(
                        "inline-flex items-center justify-center px-4 py-2 my-2 text-sm font-medium rounded-lg shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2",
                        isUser
                            ? "bg-white/20 hover:bg-white/30 text-white focus:ring-white"
                            : "bg-blue-700 hover:bg-blue-800 text-white focus:ring-blue-500"
                    )}
                >
                    {buttonText}
                </a>

                {textAfter && <MarkdownText text={textAfter} />}
            </>
        );
    };

    return (
        <div
            className={cn(
                "flex w-full mb-4 animate-in fade-in slide-in-from-bottom-2 duration-300",
                isUser ? "justify-end" : "justify-start"
            )}
        >
            <div
                className={cn(
                    "max-w-[70%] rounded-2xl px-4 py-3 shadow-sm border transition-all duration-200 hover:shadow-md",
                    isUser
                        ? "bg-user-message text-user-message-foreground rounded-tr-sm font-medium text-right"
                        : "bg-assistant-message text-assistant-message-foreground border-message-border rounded-tl-sm font-medium text-left"
                )}
            >
                {/* MESSAGE CONTENT */}
                <div className="text-sm leading-relaxed break-words">
                    {renderMessageContent()}
                </div>

                {/* TIMESTAMP */}
                <span
                    className={cn(
                        "text-xs mt-2 block opacity-70",
                        isUser
                            ? "text-user-message-foreground text-left"
                            : "text-muted-foreground text-right"
                    )}
                >
                    {message.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                    })}
                </span>
            </div>
        </div>
    );
};