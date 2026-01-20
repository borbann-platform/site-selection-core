/**
 * ChatLayout - Main layout for the dedicated chat page
 * Includes a collapsible session sidebar and the main chat area
 */

import { useEffect, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { PanelLeftClose, PanelLeft, Plus, Search, MessageSquare } from "lucide-react";
import { cn } from "../../lib/utils";
import { useChatStore } from "../../stores/chatStore";
import { SessionSidebar } from "./SessionSidebar";
import { ChatArea } from "./ChatArea";

interface ChatLayoutProps {
  sessionId?: string;
}

export function ChatLayout({ sessionId }: ChatLayoutProps) {
  const navigate = useNavigate();
  const {
    sidebarOpen,
    toggleSidebar,
    searchOpen,
    setSearchOpen,
    loadSessions,
    createSession,
    selectSession,
    currentSessionId,
  } = useChatStore();

  // Load sessions on mount
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Select session from URL param
  useEffect(() => {
    if (sessionId && sessionId !== currentSessionId) {
      selectSession(sessionId).catch(console.error);
    }
  }, [sessionId, currentSessionId, selectSession]);

  // Handle creating a new session
  const handleNewSession = useCallback(async () => {
    try {
      const session = await createSession();
      navigate({ to: "/chat/$sessionId", params: { sessionId: session.id } });
    } catch (error) {
      console.error("Failed to create session:", error);
    }
  }, [createSession, navigate]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd/Ctrl + N: New chat
      if ((e.metaKey || e.ctrlKey) && e.key === "n") {
        e.preventDefault();
        handleNewSession();
      }
      // Cmd/Ctrl + K: Toggle search
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(!searchOpen);
      }
      // Cmd/Ctrl + B: Toggle sidebar
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        toggleSidebar();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleNewSession, searchOpen, setSearchOpen, toggleSidebar]);

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div
        className={cn(
          "flex flex-col border-r border-border bg-muted/30 transition-all duration-300",
          sidebarOpen ? "w-72" : "w-0 overflow-hidden"
        )}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-3 border-b border-border">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-emerald-500" />
            <span className="font-semibold text-sm">Chats</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="p-2 hover:bg-muted rounded-lg transition-colors"
              title="Search (Cmd+K)"
            >
              <Search className="w-4 h-4 text-muted-foreground" />
            </button>
            <button
              type="button"
              onClick={handleNewSession}
              className="p-2 hover:bg-muted rounded-lg transition-colors"
              title="New chat (Cmd+N)"
            >
              <Plus className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* Session List */}
        <SessionSidebar onSelectSession={(id) => navigate({ to: "/chat/$sessionId", params: { sessionId: id } })} />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Chat Header */}
        <div className="flex items-center gap-2 p-3 border-b border-border">
          <button
            type="button"
            onClick={toggleSidebar}
            className="p-2 hover:bg-muted rounded-lg transition-colors"
            title={sidebarOpen ? "Hide sidebar (Cmd+B)" : "Show sidebar (Cmd+B)"}
          >
            {sidebarOpen ? (
              <PanelLeftClose className="w-4 h-4 text-muted-foreground" />
            ) : (
              <PanelLeft className="w-4 h-4 text-muted-foreground" />
            )}
          </button>
          
          {!sidebarOpen && (
            <button
              type="button"
              onClick={handleNewSession}
              className="p-2 hover:bg-muted rounded-lg transition-colors"
              title="New chat (Cmd+N)"
            >
              <Plus className="w-4 h-4 text-muted-foreground" />
            </button>
          )}
        </div>

        {/* Chat Area */}
        <ChatArea />
      </div>
    </div>
  );
}
