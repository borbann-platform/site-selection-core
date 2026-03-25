import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, MapPin, X } from "lucide-react";
import { cn } from "../lib/utils";
import { api, type ChatMessage } from "../lib/api";

export type AttachmentType = "location" | "property";

export interface Attachment {
  id: string;
  type: AttachmentType;
  data: Record<string, unknown>;
  label: string;
}

interface ChatMessageWithId extends ChatMessage {
  id: string;
}

interface ChatPanelProps {
  className?: string;
  attachments?: Attachment[];
  onPickLocation?: () => void;
  onRemoveAttachment?: (id: string) => void;
}

let messageIdCounter = 0;
function generateMessageId(): string {
  return `msg-${++messageIdCounter}-${Date.now()}`;
}

export function ChatPanel({
  className,
  attachments = [],
  onPickLocation,
  onRemoveAttachment,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageWithId[]>([
    {
      id: generateMessageId(),
      role: "assistant",
      content:
        "Hello! I'm your real estate AI assistant. I can help you with property prices, market insights, and recommendations. What would you like to know?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && attachments.length === 0) || isStreaming) return;

    let content = input.trim();
    if (attachments.length > 0) {
      const attachmentText = attachments
        .map((a) => `[Attachment: ${a.type} - ${JSON.stringify(a.data)}]`)
        .join("\n");
      content = `${content}\n\n${attachmentText}`.trim();
    }

    const userMessage: ChatMessageWithId = {
      id: generateMessageId(),
      role: "user",
      content,
    };
    const assistantMessageId = generateMessageId();
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
    // Clear attachments after sending (parent should handle this via callback if needed,
    // but for now we assume parent clears them or we just send the text representation)
    // Ideally we should have an onSend callback to clear parent state.
    // For this prototype, we'll just send the text.
    // NOTE: In a real app, we'd call a prop like onMessagesSent to clear attachments in parent.
    // Since we don't have that prop yet, we'll assume the parent clears them when we call onRemoveAttachment for all?
    // Or better, we just send the text and let the user manually clear or we clear them if we controlled the state.
    // Let's just proceed with sending text for now.

    setIsStreaming(true);

    // Add empty assistant message that we'll stream into
    setMessages((prev) => [
      ...prev,
      { id: assistantMessageId, role: "assistant", content: "" },
    ]);

    // Convert to API format (without id)
    const apiMessages = newMessages.map(({ role, content }) => ({
      role,
      content,
    }));

    try {
      let fullResponse = "";
      for await (const chunk of api.streamChat(apiMessages)) {
        fullResponse += chunk;
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            id: assistantMessageId,
            role: "assistant",
            content: fullResponse,
          };
          return updated;
        });
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          id: assistantMessageId,
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
        };
        return updated;
      });
    } finally {
      setIsStreaming(false);
      inputRef.current?.focus();
      // Hack: Clear attachments by calling remove on all of them
      attachments.forEach((a) => {
        onRemoveAttachment?.(a.id);
      });
    }
  };

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b border-border">
        <div className="w-8 h-8 bg-brand/20 rounded-lg flex items-center justify-center">
          <Bot size={18} className="text-brand" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-foreground">AI Assistant</h3>
          <p className="text-[10px] text-muted-foreground">Real Estate Expert</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex gap-2",
              message.role === "user" ? "flex-row-reverse" : "flex-row"
            )}
          >
            <div
              className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center shrink-0",
                message.role === "user" ? "bg-ai-accent/20" : "bg-brand/20"
              )}
            >
              {message.role === "user" ? (
                <User size={12} className="text-blue-400" />
              ) : (
                <Bot size={12} className="text-brand" />
              )}
            </div>
            <div
              className={cn(
                "max-w-[85%] rounded-xl px-3 py-2 text-sm",
                message.role === "user"
                  ? "bg-ai-accent/20 text-foreground"
                  : "bg-muted/50 text-foreground/90"
              )}
            >
              {message.content || (
                <span className="flex items-center gap-1 text-muted-foreground">
                  <Loader2 size={12} className="animate-spin" />
                  Thinking...
                </span>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-border">
        {/* Attachments */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {attachments.map((att) => (
              <div
                key={att.id}
                className="flex items-center gap-1 bg-muted/50 rounded-full px-2 py-1 text-xs text-foreground/80"
              >
                <span className="truncate max-w-36">{att.label}</span>
                <button
                  type="button"
                  onClick={() => onRemoveAttachment?.(att.id)}
                  className="hover:text-foreground"
                  aria-label="Remove attachment"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <button
            type="button"
            onClick={onPickLocation}
            className="p-2 bg-muted/50 hover:bg-muted rounded-lg text-muted-foreground transition-colors"
            title="Pick location on map"
            aria-label="Pick location on map"
          >
            <MapPin size={18} />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about prices, areas, predictions..."
            disabled={isStreaming}
            className="flex-1 bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-brand/50 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={
              (!input.trim() && attachments.length === 0) || isStreaming
            }
            className="p-2 bg-brand hover:bg-brand/90 disabled:bg-muted disabled:text-muted-foreground rounded-lg text-brand-foreground transition-colors"
            aria-label={isStreaming ? "Sending message" : "Send message"}
          >
            {isStreaming ? (
              <Loader2 size={18} className="animate-spin text-muted-foreground" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
