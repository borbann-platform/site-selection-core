"""
Integration tests for chat API endpoints.

Tests the chat endpoints including streaming and session management.
"""

import json

import pytest


class TestChatStatus:
    """Tests for /api/v1/chat/status endpoint."""

    def test_status_returns_configuration(self, client):
        """Test that status endpoint returns agent configuration info."""
        response = client.get("/api/v1/chat/status")

        assert response.status_code == 200
        data = response.json()
        assert "agent_configured" in data
        assert "max_iterations" in data
        assert isinstance(data["max_iterations"], int)


class TestChatAgentEndpoint:
    """Tests for /api/v1/chat/agent endpoint."""

    def test_agent_chat_returns_sse_stream(self, client, sample_chat_messages):
        """Test that agent chat endpoint returns SSE stream."""
        response = client.post(
            "/api/v1/chat/agent",
            json={"messages": sample_chat_messages[:1]},  # Just first message
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_agent_chat_returns_session_id(self, client, sample_chat_messages):
        """Test that agent chat returns session ID header."""
        response = client.post(
            "/api/v1/chat/agent",
            json={"messages": sample_chat_messages[:1]},
        )

        assert response.status_code == 200
        assert "X-Session-ID" in response.headers
        assert len(response.headers["X-Session-ID"]) > 0

    def test_agent_chat_accepts_attachments(
        self, client, sample_chat_messages, sample_location_attachment
    ):
        """Test that agent chat accepts location attachments."""
        response = client.post(
            "/api/v1/chat/agent",
            json={
                "messages": sample_chat_messages[:1],
                "attachments": [sample_location_attachment],
            },
        )

        assert response.status_code == 200

    def test_agent_chat_accepts_bbox_attachment(
        self, client, sample_chat_messages, sample_bbox_attachment
    ):
        """Test that agent chat accepts bbox attachments."""
        response = client.post(
            "/api/v1/chat/agent",
            json={
                "messages": sample_chat_messages[:1],
                "attachments": [sample_bbox_attachment],
            },
        )

        assert response.status_code == 200

    def test_agent_chat_stream_contains_events(self, client, sample_chat_messages):
        """Test that agent stream contains valid SSE events."""
        response = client.post(
            "/api/v1/chat/agent",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )

        assert response.status_code == 200

        # Parse SSE events
        content = response.text
        lines = content.split("\n")
        events = []

        for line in lines:
            if line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:])
                    events.append(event_data)
                except json.JSONDecodeError:
                    pass

        # Should have at least one event
        assert len(events) > 0

        # Check for expected event types
        event_types = [e.get("event") for e in events]
        assert any(t in event_types for t in ["thinking", "token", "step", "done"])


class TestSessionManagement:
    """Tests for session management endpoints."""

    def test_create_session(self, client):
        """Test creating a new conversation session."""
        response = client.post("/api/v1/chat/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_get_session_history_empty(self, client):
        """Test getting history for a non-existent session."""
        response = client.get("/api/v1/chat/sessions/nonexistent-session/history")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert data["messages"] == []

    def test_clear_session(self, client):
        """Test clearing a session."""
        # First create a session
        create_response = client.post("/api/v1/chat/sessions")
        session_id = create_response.json()["session_id"]

        # Then clear it
        clear_response = client.delete(f"/api/v1/chat/sessions/{session_id}")

        assert clear_response.status_code == 200
        data = clear_response.json()
        assert data["status"] == "cleared"
        assert data["session_id"] == session_id


class TestLegacyChatEndpoint:
    """Tests for /api/v1/chat endpoint (legacy)."""

    def test_chat_endpoint_returns_stream(self, client):
        """Test that legacy chat endpoint returns SSE stream."""
        response = client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Test message"}]},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_chat_endpoint_with_debug_mode(self, client):
        """Test chat endpoint with debug parameter."""
        response = client.post(
            "/api/v1/chat?debug=true",
            json={"messages": [{"role": "user", "content": "Test message"}]},
        )

        assert response.status_code == 200
