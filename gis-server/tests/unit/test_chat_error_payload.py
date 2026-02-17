"""
Unit tests for structured provider error payload mapping.
"""

from src.routes.chat import build_agent_error_payload


def test_maps_429_insufficient_balance_to_quota_error():
    payload = build_agent_error_payload(
        "Error code: 429 - {'error': {'code': '1113', 'message': 'Insufficient balance or no resource package. Please recharge.'}}"
    )

    assert payload["title"] == "Provider quota exceeded"
    assert payload["status_code"] == 429
    assert payload["provider_code"] == "1113"
    assert "balance" in payload["raw_message"].lower()


def test_maps_auth_failures_to_authentication_error():
    payload = build_agent_error_payload("Error code: 401 - Invalid API key")

    assert payload["title"] == "Provider authentication failed"
    assert payload["status_code"] == 401
