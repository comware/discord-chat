.PHONY: help lint format test version hooks clean all check tne-activity tne-digest

# Suppress command echoing
MAKEFLAGS += --silent

# Configurable hours for Discord commands (default: 24)
HOURS ?= 24
# Optional channel filter for digest (default: all channels)
CHANNEL ?=

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

lint: ## Run linter with auto-fix
	uv run ruff check . --fix

format: ## Run formatter
	uv run black .
	uv run ruff check . --fix --select I

test: ## Run tests
	uv run pytest -v

version: ## Display project version
	uv run python cli.py version

check: lint format test ## Run all checks (lint, format, test)

clean: ## Remove build artifacts and cache
	rm -rf __pycache__ .pytest_cache .ruff_cache
	rm -rf discord_chat/__pycache__ discord_chat/**/__pycache__
	rm -rf tests/__pycache__
	rm -rf dist build *.egg-info
	find . -type f -name "*.pyc" -delete

# Git hooks installation
hooks: .git/hooks/pre-commit ## Install git hooks

.git/hooks/pre-commit: hooks/pre-commit
	@echo "Installing git hooks..."
	@cp $< $@
	@chmod +x $@
	@echo "✓ Pre-commit hook installed"

all: hooks check ## Install hooks and run all checks

tne-activity: ## Show message counts per channel for tne.ai (HOURS=24)
	uv run python cli.py activity "tne.ai" --hours $(HOURS)

tne-digest: ## Generate digest for tne.ai Discord server (HOURS=24, CHANNEL=optional)
ifdef CHANNEL
	uv run python cli.py digest "tne.ai" --hours $(HOURS) --channel "$(CHANNEL)"
else
	uv run python cli.py digest "tne.ai" --hours $(HOURS)
endif
