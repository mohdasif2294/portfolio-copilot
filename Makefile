.PHONY: help install dev lint format test clean run web cli ingest

# Ensure poetry is in PATH (handles cases where ~/.local/bin isn't in make's PATH)
export PATH := $(HOME)/.local/bin:$(PATH)

# Default target
help:
	@echo "Portfolio Copilot - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install production dependencies"
	@echo "  make dev         Install all dependencies (including dev)"
	@echo ""
	@echo "Run:"
	@echo "  make cli         Run the CLI interface"
	@echo "  make web         Run the Streamlit web interface"
	@echo ""
	@echo "Development:"
	@echo "  make lint        Run linter (ruff)"
	@echo "  make format      Format code (black + ruff)"
	@echo "  make typecheck   Run type checker (mypy)"
	@echo "  make test        Run tests"
	@echo "  make check       Run all checks (lint + typecheck + test)"
	@echo ""
	@echo "Data:"
	@echo "  make ingest      Ingest news into vector store"
	@echo "  make qdrant      Start Qdrant vector database (Docker)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean       Remove cache and build files"
	@echo "  make lock        Update poetry.lock file"

# =============================================================================
# Setup
# =============================================================================

install:
	poetry install --no-root

dev:
	poetry install --no-root --with dev

lock:
	poetry lock

# =============================================================================
# Run
# =============================================================================

cli:
	PYTHONPATH=$(PWD) poetry run python -m src.ui.cli

web:
	PYTHONPATH=$(PWD) poetry run streamlit run src/ui/streamlit_app.py

# =============================================================================
# Development
# =============================================================================

lint:
	poetry run ruff check src/

format:
	poetry run black src/ tests/
	poetry run ruff check --fix src/

typecheck:
	poetry run mypy src/

test:
	poetry run pytest tests/ -v

check: lint typecheck test

# =============================================================================
# Data
# =============================================================================

ingest:
	poetry run python -c "import asyncio; from src.data.ingestion import ingest_news; asyncio.run(ingest_news())"

qdrant:
	docker run -p 6333:6333 -v $(PWD)/data/vector_store:/qdrant/storage qdrant/qdrant

# =============================================================================
# Utilities
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
