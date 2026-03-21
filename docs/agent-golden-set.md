# Agent Golden Test Set

This file tracks the golden benchmark prompts and how to run quality evaluation.

## Source

The canonical 10-case benchmark is user-provided and encoded in:

- `gis-server/scripts/evaluate_agent_orchestration_quality.py`

## Run Evaluation

Prerequisites:

- backend running at `http://localhost:8000`
- valid auth token for `/api/v1/chat/agent`

Run without judge:

```bash
cd gis-server
uv run python -m scripts.evaluate_agent_orchestration_quality \
  --base-url http://localhost:8000 \
  --token "$EVAL_AUTH_TOKEN"
```

Run with LLM-as-judge:

```bash
cd gis-server
uv run python -m scripts.evaluate_agent_orchestration_quality \
  --base-url http://localhost:8000 \
  --token "$EVAL_AUTH_TOKEN" \
  --judge \
  --judge-model "$JUDGE_MODEL" \
  --judge-api-key "$JUDGE_API_KEY" \
  --judge-base-url "$JUDGE_BASE_URL" \
  --runtime-provider openai_compatible \
  --runtime-model deepseek-chat \
  --runtime-api-key "$JUDGE_API_KEY" \
  --runtime-base-url "$JUDGE_BASE_URL"
```

Default output report:

- `gis-server/reports/agent_orchestration_quality.json`

Quality gate checker:

```bash
cd gis-server
uv run python -m scripts.check_agent_quality_gate \
  --report reports/agent_orchestration_quality.json \
  --min-median-score 7.0 \
  --require-tool-first
```

## Recommended Gates

- Tool-first compliance: 100% for factual queries
- Clarification correctness: no missing-constraint false negatives
- Judge score median >= 7.0
- No runtime errors across all 10 cases
