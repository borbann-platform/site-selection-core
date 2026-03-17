"""Unit tests for explanation narration helpers."""

from src.services.explanation_narration import build_narration_prompt
from src.services.price_prediction import FeatureContribution, PricePrediction


def test_build_narration_prompt_includes_grounded_fields():
    prediction = PricePrediction(
        predicted_price=5_500_000,
        confidence=0.82,
        model_type="baseline",
        h3_index="89283082837ffff",
        district="วัฒนา",
        price_vs_district=4.5,
        district_avg_price=5_100_000,
        explanation_method="global_gain",
        explanation_summary="Top factors that most influenced the model output.",
        explanation_disclaimer="Signals are not additive THB components.",
        feature_contributions=[
            FeatureContribution(
                feature="building_area",
                feature_display="Building Area (sqm)",
                value=180.0,
                direction="positive",
                contribution=12.4,
                contribution_kind="global_gain",
                contribution_display="Gain 12.40",
            )
        ],
    )

    prompt = build_narration_prompt(prediction, actual_price=5_200_000)

    assert "Predicted price: THB 5,500,000" in prompt
    assert "Actual/appraised price: THB 5,200,000" in prompt
    assert "Explanation method: global_gain" in prompt
    assert "Building Area (sqm)" in prompt
    assert "Signals are not additive THB components." in prompt
