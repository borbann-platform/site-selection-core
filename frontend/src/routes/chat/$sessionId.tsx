/**
 * Chat session route - displays a specific chat session
 */

import { createFileRoute, redirect } from "@tanstack/react-router";
import { ChatLayout } from "../../components/chat";

export const Route = createFileRoute("/chat/$sessionId")({
  component: ChatSession,
  beforeLoad: ({ params }) => {
    // Check if user is authenticated - if not, redirect to login
    const token = localStorage.getItem("access_token");
    if (!token) {
      throw redirect({
        to: "/login",
        search: {
          redirect: `/chat/${params.sessionId}`,
        },
      });
    }
  },
});

function ChatSession() {
  const { sessionId } = Route.useParams();
  
  return <ChatLayout sessionId={sessionId} />;
}
