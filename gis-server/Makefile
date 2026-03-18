.PHONY: test test-unit test-integration test-cov lint format install sync \
	mlflow-up mlflow-down mlflow-logs mlflow-ui \
	promote-baseline promote-hgt mlflow-leaderboard \
	sync-images-minio sync-images-minio-pipeline \
	playwright-install scrape-baania-bkk scrape-hipflat-bkk \
	load-scraped-bkk sync-scraped-images rebuild-combined-benchmark \
	build-listing-only-benchmark \
	audit-listing-images build-image-embedding-manifest \
	build-listing-image-embeddings

DATE_TAG ?= $(shell date +%Y%m%d)
START_PAGE ?= 1
MAX_PAGES ?= 10
MAX_DETAILS ?=
INPUT_GLOB ?= data/scraped/*$(DATE_TAG)*.jsonl
IMAGE_LIMIT ?= 5000
IMAGE_STATUSES ?= pending,failed
IMAGE_COMMIT_BATCH ?= 100
IMAGE_TIMEOUT_SECONDS ?= 30

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

# Install Playwright Chromium for Hipflat scraping
playwright-install:
	uv run --with playwright playwright install chromium

# Scrape a chunk of Bangkok Baania house projects
scrape-baania-bkk:
	uv run --with scrapy scrapy runspider scripts/scrapers/baania_house_spider.py \
		-a start_page=$(START_PAGE) \
		-a max_pages=$(MAX_PAGES) \
		$(if $(MAX_DETAILS),-a max_details=$(MAX_DETAILS),) \
		-a include_raw=0 \
		-O data/scraped/baania_bangkok_houses_page_$(START_PAGE)_$$(( $(START_PAGE) + $(MAX_PAGES) - 1 ))_$(DATE_TAG).jsonl

# Scrape a chunk of Bangkok Hipflat house projects
scrape-hipflat-bkk:
	uv run --with scrapy --with scrapy-playwright --with playwright scrapy runspider scripts/scrapers/hipflat_bangkok_house_spider.py \
		-a start_page=$(START_PAGE) \
		-a max_pages=$(MAX_PAGES) \
		$(if $(MAX_DETAILS),-a max_details=$(MAX_DETAILS),) \
		-O data/scraped/hipflat_bangkok_houses_page_$(START_PAGE)_$$(( $(START_PAGE) + $(MAX_PAGES) - 1 ))_$(DATE_TAG).jsonl

# Load scraped Bangkok JSONL files into normalized tables
load-scraped-bkk:
	uv run python -m scripts.etl.load_scraped_projects --input-glob "$(INPUT_GLOB)" --include-raw

# Download and sync scraped listing images into object storage
sync-scraped-images:
	uv run --with minio python -m scripts.etl.sync_images_to_minio \
		--statuses $(IMAGE_STATUSES) \
		--limit $(IMAGE_LIMIT) \
		--commit-batch $(IMAGE_COMMIT_BATCH) \
		--timeout-seconds $(IMAGE_TIMEOUT_SECONDS)

# Rebuild combined benchmark artifacts after new listing data lands
rebuild-combined-benchmark:
	uv run python -m scripts.build_combined_price_dataset

# Build listing-only benchmark from combined artifact
build-listing-only-benchmark:
	uv run python -m scripts.build_listing_only_dataset

# Audit listing image quality for benchmark rows
audit-listing-images:
	uv run python -m scripts.audit_listing_images_quality

# Build benchmark-aligned top-k listing image manifest
build-image-embedding-manifest:
	uv run python -m scripts.extract_listing_image_embeddings --top-k 3 --prefer-uploaded

# Build listing-level image embeddings from manifest
build-listing-image-embeddings:
	uv run python -m scripts.build_listing_image_embeddings
