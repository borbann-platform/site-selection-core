"""LLM-backed natural-language narration for price explanations."""

from __future__ import annotations

import logging

from src.services.model_provider import get_model_provider, resolve_runtime_config
from src.services.price_prediction import PricePrediction

logger = logging.getLogger(__name__)


def _format_currency(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"THB {value:,.0f}"


def build_narration_prompt(
    prediction: PricePrediction,
    actual_price: float | None = None,
) -> str:
    """Build a grounded narration prompt from structured explanation data."""
    signal_lines = []
    for contribution in prediction.feature_contributions[:5]:
        contribution_label = (
            contribution.contribution_display
            if contribution.contribution_display
            else f"{contribution.contribution:.4f}"
        )
        signal_lines.append(
            "- "
            f"{contribution.feature_display}: direction={contribution.direction}, "
            f"value={contribution.value:.2f}, "
            f"label={contribution_label}, "
            f"kind={contribution.contribution_kind}"
        )

    actual_price_text = _format_currency(actual_price)
    district_avg_text = _format_currency(prediction.district_avg_price)
    price_vs_district_text = (
        f"{prediction.price_vs_district:.1f}%"
        if prediction.price_vs_district is not None
        else "unknown"
    )

    return f"""You are writing a short, cautious explanation for a property valuation UI.

Rules:
- Use only the provided facts.
- Do not invent missing features, percentages, or causal claims.
- Do not say the signals are additive THB components.
- Do not mention SHAP unless the method explicitly says shap.
- Keep it to 2-3 sentences, plain English.
- Mention uncertainty when the method is not a local additive explanation.

Structured facts:
- Model type: {prediction.model_type}
- Explanation method: {prediction.explanation_method}
- Explanation summary: {prediction.explanation_summary}
- Predicted price: {_format_currency(prediction.predicted_price)}
- Actual/appraised price: {actual_price_text}
- District: {prediction.district or "unknown"}
- District average price: {district_avg_text}
- Percent vs district average: {price_vs_district_text}
- Cold start area: {"yes" if prediction.is_cold_start else "no"}
- Disclaimer: {prediction.explanation_disclaimer}

Top signals:
{chr(10).join(signal_lines) if signal_lines else "- none"}

Write the explanation text only.
"""


def generate_natural_language_explanation(
    prediction: PricePrediction,
    actual_price: float | None = None,
) -> str | None:
    """Generate grounded narration using the default agent model provider."""
    try:
        resolved = resolve_runtime_config()
        if not resolved.is_configured:
            return None

        provider = get_model_provider(resolved.provider)
        llm = provider.create_chat_model(
            resolved,
            temperature=0.2,
            max_tokens=220,
        )
        response = llm.invoke(build_narration_prompt(prediction, actual_price))
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content.strip() or None
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            joined = " ".join(part for part in text_parts if part).strip()
            return joined or None
    except Exception as exc:
        logger.warning("Failed to generate explanation narration: %s", exc)
    return None
