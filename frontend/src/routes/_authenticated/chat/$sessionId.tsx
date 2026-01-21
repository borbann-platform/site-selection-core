/**
 * Chat session route - displays a specific chat session
 */

import { createFileRoute } from "@tanstack/react-router";
import { ChatLayout } from "../../../components/chat";

export const Route = createFileRoute("/_authenticated/chat/$sessionId")({
  component: ChatSession,
});

function ChatSession() {
  const { sessionId } = Route.useParams();
  
  return <ChatLayout sessionId={sessionId} />;
}
