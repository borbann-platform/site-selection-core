/**
 * Chat index route - redirects to new chat or shows welcome
 */

import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { ChatLayout } from "../../components/chat";
import { useChatStore } from "../../stores/chatStore";

export const Route = createFileRoute("/chat/")({
  component: ChatIndex,
});

function ChatIndex() {
  const navigate = useNavigate();
  const { currentSessionId } = useChatStore();

  // If we have a current session, redirect to it
  useEffect(() => {
    if (currentSessionId) {
      navigate({ to: "/chat/$sessionId", params: { sessionId: currentSessionId } });
    }
  }, [currentSessionId, navigate]);

  return <ChatLayout />;
}
