"""
Integration tests for chat API endpoints.

Tests the chat endpoints including streaming and session management.
"""

import json
import uuid

import pytest


class TestChatStatus:
    """Tests for /api/v1/chat/status endpoint."""

    def test_status_returns_configuration(self, client):
        """Test that status endpoint returns agent configuration info."""
        response = client.get("/api/v1/chat/status")

        assert response.status_code == 200
        data = response.json()
        assert "agent_configured" in data
        assert "provider" in data
        assert "max_iterations" in data
        assert "supported_providers" in data
        assert isinstance(data["max_iterations"], int)

    def test_provider_catalog_endpoint(self, client):
        """Test provider catalog endpoint for BYOK UI wiring."""
        response = client.get("/api/v1/chat/providers")

        assert response.status_code == 200
        data = response.json()
        assert "default_provider" in data
        assert "supported_providers" in data
        assert isinstance(data["supported_providers"], list)

    def test_provider_validation_endpoint(self, client):
        """Test runtime provider validation without external API calls."""
        response = client.post(
            "/api/v1/chat/providers/validate",
            json={
                "runtime": {
                    "provider": "openai_compatible",
                    "model": "deepseek-chat",
                    "api_key": "test-key",
                    "base_url": "https://api.deepseek.com/v1",
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openai_compatible"
        assert data["valid"] is True


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

    def test_agent_stream_event_ordering_contract(self, client, monkeypatch):
        """Stream should emit thinking first and done last."""
        from src.services import agent_graph

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "tool_call",
                "content": {"name": "search_properties", "input": {}},
            }
            yield {"type": "tool_result", "content": "ok"}
            yield {"type": "token", "content": "hello"}
            yield {"type": "final", "content": "hello"}

        monkeypatch.setattr(agent_graph.agent_service, "astream", fake_stream)

        response = client.post(
            "/api/v1/chat/agent",
            json={"messages": [{"role": "user", "content": "Find condo in Ari"}]},
        )

        assert response.status_code == 200
        events = [
            json.loads(line[6:])
            for line in response.text.split("\n")
            if line.startswith("data: ") and line[6:] and line[6:] != "[DONE]"
        ]
        assert events[0]["event"] == "thinking"
        assert events[-1]["event"] == "done"

    def test_agent_stream_blocked_tool_evidence_path(self, client, monkeypatch):
        """Blocked tool-evidence should emit waiting_user step and done."""
        from src.services import agent_graph

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "clarification",
                "content": {
                    "message": "Need tool evidence first",
                    "missing_constraints": ["tool_evidence"],
                    "questions": [],
                },
            }

        monkeypatch.setattr(agent_graph.agent_service, "astream", fake_stream)

        response = client.post(
            "/api/v1/chat/agent",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "Compare Bangkok condo prices for next 5 years",
                    }
                ]
            },
        )

        assert response.status_code == 200
        events = [
            json.loads(line[6:])
            for line in response.text.split("\n")
            if line.startswith("data: ") and line[6:] and line[6:] != "[DONE]"
        ]
        step_events = [e for e in events if e.get("event") == "step"]
        assert any(
            (evt.get("data") or {}).get("type") == "waiting_user" for evt in step_events
        )
        assert events[-1]["event"] == "done"

    def test_agent_finance_query_can_use_runtime_without_compare_prompt(
        self, client, monkeypatch
    ):
        from src.services import agent_graph

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "tool_call",
                "content": {"name": "compute_dsr_and_affordability", "input": {}},
            }
            yield {"type": "tool_result", "content": "ok"}
            yield {"type": "final", "content": "ผลการคำนวณ DSR พร้อมแล้ว"}

        monkeypatch.setattr(agent_graph.agent_service, "astream", fake_stream)
        response = client.post(
            "/api/v1/chat/agent",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "จะซื้อบ้าน 8 ล้าน เงินเดือน 80,000 ภาระผ่อนรถ 12,000 ช่วยคำนวณวงเงินกู้สูงสุด DSR และดอกเบี้ย",
                    }
                ]
            },
        )

        assert response.status_code == 200
        assert (
            "Which two or more districts/properties should I compare?"
            not in response.text
        )

    def test_agent_rewrite_emits_finance_tool_call(self, client, monkeypatch):
        from src.services import agent_graph

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "tool_call",
                "content": {"name": "compute_dsr_and_affordability", "input": {}},
            }
            yield {"type": "tool_result", "content": "ok"}
            yield {"type": "final", "content": "เสร็จแล้ว"}

        monkeypatch.setattr(agent_graph.agent_service, "astream", fake_stream)
        response = client.post(
            "/api/v1/chat/agent",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "จะซื้อบ้าน 8 ล้าน เงินเดือน 80,000 ภาระผ่อนรถ 12,000 ช่วยคำนวณ DSR และดอกเบี้ย",
                    }
                ]
            },
        )

        assert response.status_code == 200
        assert "compute_dsr_and_affordability" in response.text

    def test_agent_rewrite_emits_legal_tool_call(self, client, monkeypatch):
        from src.services import agent_graph

        async def fake_stream(*args, **kwargs):
            yield {
                "type": "tool_call",
                "content": {"name": "legal_estate_sale_checklist_th", "input": {}},
            }
            yield {"type": "tool_result", "content": "ok"}
            yield {"type": "final", "content": "เช็กลิสต์พร้อมแล้ว"}

        monkeypatch.setattr(agent_graph.agent_service, "astream", fake_stream)
        response = client.post(
            "/api/v1/chat/agent",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "เจ้าของเสียชีวิตแล้วยังไม่ได้ตั้งผู้จัดการมรดก ต้องทำอย่างไร",
                    }
                ]
            },
        )

        assert response.status_code == 200
        assert "legal_estate_sale_checklist_th" in response.text

    def test_chat_status_exposes_engine_metadata(self, client):
        response = client.get("/api/v1/chat/status")

        assert response.status_code == 200
        data = response.json()
        assert data["engine"]["kind"] == "workflow_rewrite"
        assert len(data["engine"]["revision"]) == 12


class TestRuntimeConfigStorage:
    """Tests for encrypted BYOK runtime config persistence endpoints."""

    def test_runtime_config_crud(self, client):
        save_response = client.put(
            "/api/v1/chat/runtime-config",
            json={
                "runtime": {
                    "provider": "openai_compatible",
                    "model": "deepseek-chat",
                    "api_key": "sk-test-secret",
                    "base_url": "https://api.deepseek.com/v1",
                    "reasoning_mode": "hybrid",
                }
            },
        )
        assert save_response.status_code == 200
        save_data = save_response.json()
        assert save_data["source"] == "database"
        assert save_data["has_api_key"] is True
        assert "api_key" not in save_data["runtime"]

        get_response = client.get("/api/v1/chat/runtime-config")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["source"] == "database"
        assert get_data["has_api_key"] is True
        assert get_data["api_key_masked"]
        assert "api_key" not in get_data["runtime"]

        clear_response = client.delete("/api/v1/chat/runtime-config")
        assert clear_response.status_code == 200
        assert clear_response.json()["deleted"] is True


class TestSessionManagement:
    """Tests for session management endpoints."""

    def test_create_session(self, client):
        """Test creating a new conversation session."""
        response = client.post("/api/v1/chat/sessions", json={})

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert len(data["id"]) > 0

    def test_get_session_history_empty(self, client):
        """Test getting history for an empty session."""
        create_response = client.post("/api/v1/chat/sessions", json={})
        session_id = create_response.json()["id"]
        response = client.get(f"/api/v1/chat/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert data["messages"] == []

    def test_clear_session(self, client):
        """Test clearing a session."""
        # First create a session
        create_response = client.post("/api/v1/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Then clear it
        clear_response = client.delete(f"/api/v1/chat/sessions/{session_id}")

        assert clear_response.status_code == 204

    def test_archive_session_triggers_summary_refresh(self, client, monkeypatch):
        """Archiving a session should trigger forced summary refresh."""
        from src.services.chat_service import ChatService

        calls: list[tuple[uuid.UUID, uuid.UUID, bool]] = []

        async def fake_refresh(self, session_id, user_id, force=False, **kwargs):
            calls.append((session_id, user_id, force))
            return True

        monkeypatch.setattr(ChatService, "refresh_rolling_summary", fake_refresh)

        create_response = client.post("/api/v1/chat/sessions", json={})
        session_id = create_response.json()["id"]

        archive_response = client.patch(
            f"/api/v1/chat/sessions/{session_id}",
            json={"is_archived": True},
        )

        assert archive_response.status_code == 200
        assert archive_response.json()["is_archived"] is True
        assert len(calls) == 1
        assert calls[0][0] == uuid.UUID(session_id)
        assert calls[0][2] is True


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
