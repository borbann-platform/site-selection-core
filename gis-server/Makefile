.PHONY: test test-unit test-integration test-cov lint format install sync \
	mlflow-up mlflow-down mlflow-logs mlflow-ui \
	promote-baseline promote-hgt mlflow-leaderboard \
	sync-images-minio sync-images-minio-pipeline

# Default target
all: test

# Install dependencies including dev
install:
	uv sync --extra dev

# Sync dependencies
sync:
	uv sync

# Run all tests
test:
	uv run pytest tests/ -v

# Run only unit tests
test-unit:
	uv run pytest tests/unit -v

# Run only integration tests
test-integration:
	uv run pytest tests/integration -v

# Run tests with coverage
test-cov:
	uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Run linting
lint:
	uv run ruff check src/ tests/

# Format code
format:
	uv run ruff format src/ tests/

# Run type checking (if pyright is installed)
typecheck:
	uv run pyright src/

# Clean cache files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true

# MLflow services (Postgres backend + local artifact volume)
mlflow-up:
	docker compose up -d --build mlflow-db mlflow

mlflow-down:
	docker compose stop mlflow mlflow-db

mlflow-logs:
	docker compose logs -f mlflow

# MLflow UI URL helper
mlflow-ui:
	@echo "MLflow UI: http://localhost:5001"

# Train baseline model with MLflow tracking
train-baseline:
	uv run python -m scripts.train_baseline_mlflow --output models/baseline

# Train and compare all 4 baseline models (Mean, Linear, RF, LightGBM)
train-baseline-all:
	uv run python -m scripts.train_baseline_mlflow --output models/baseline --compare-all

# Train HGT model with MLflow tracking
train-hgt:
	uv run python -m scripts.train_hgt_mlflow --output models/hgt_valuator

# Promote baseline run via strict gate
promote-baseline:
	@if [ -z "$(RUN_ID)" ]; then echo "Usage: make promote-baseline RUN_ID=<mlflow_run_id>"; exit 1; fi
	uv run python -m scripts.promote_model --run-id $(RUN_ID) --model-family baseline

# Promote HGT run via strict gate
promote-hgt:
	@if [ -z "$(RUN_ID)" ]; then echo "Usage: make promote-hgt RUN_ID=<mlflow_run_id>"; exit 1; fi
	uv run python -m scripts.promote_model --run-id $(RUN_ID) --model-family hgt

# Export MLflow leaderboard for experiment comparison
mlflow-leaderboard:
	uv run python -m scripts.export_experiment_leaderboard --all-experiments --metric $(or $(METRIC),cv_mape_mean) --mode $(or $(MODE),min)

# Run one image sync batch to MinIO
sync-images-minio:
	uv run --with minio python -m scripts.etl.sync_images_to_minio --limit $(or $(LIMIT),1000) --commit-batch $(or $(COMMIT_BATCH),50)

# Run repeated image sync batches to MinIO
sync-images-minio-pipeline:
	uv run python -m scripts.etl.sync_images_to_minio_pipeline --with-minio-dep --batch-limit $(or $(BATCH_LIMIT),1000) --max-rounds $(or $(MAX_ROUNDS),20) --commit-batch $(or $(COMMIT_BATCH),50) --target-pending $(or $(TARGET_PENDING),0)
