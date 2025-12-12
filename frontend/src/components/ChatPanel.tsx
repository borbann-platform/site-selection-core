import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";
import { api, type ChatMessage } from "../lib/api";

interface ChatMessageWithId extends ChatMessage {
  id: string;
}

interface ChatPanelProps {
  className?: string;
}

let messageIdCounter = 0;
function generateMessageId(): string {
  return `msg-${++messageIdCounter}-${Date.now()}`;
}

export function ChatPanel({ className }: ChatPanelProps) {
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
    if (!input.trim() || isStreaming) return;

    const userMessage: ChatMessageWithId = {
      id: generateMessageId(),
      role: "user",
      content: input.trim(),
    };
    const assistantMessageId = generateMessageId();
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");
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
    }
  };

  return (
    <div className={cn("flex flex-col h-full", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 p-3 border-b border-white/10">
        <div className="w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center">
          <Bot size={18} className="text-emerald-400" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-white">AI Assistant</h3>
          <p className="text-[10px] text-white/50">Real Estate Expert</p>
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
                message.role === "user" ? "bg-blue-500/20" : "bg-emerald-500/20"
              )}
            >
              {message.role === "user" ? (
                <User size={12} className="text-blue-400" />
              ) : (
                <Bot size={12} className="text-emerald-400" />
              )}
            </div>
            <div
              className={cn(
                "max-w-[85%] rounded-xl px-3 py-2 text-sm",
                message.role === "user"
                  ? "bg-blue-500/20 text-white"
                  : "bg-white/5 text-white/90"
              )}
            >
              {message.content || (
                <span className="flex items-center gap-1 text-white/50">
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
      <form onSubmit={handleSubmit} className="p-3 border-t border-white/10">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about prices, areas, predictions..."
            disabled={isStreaming}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-emerald-500/50 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-white/10 disabled:text-white/30 rounded-lg text-black transition-colors"
          >
            {isStreaming ? (
              <Loader2 size={18} className="animate-spin text-white/50" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
