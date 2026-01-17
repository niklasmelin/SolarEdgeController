# --------------------------------------------------------------------
# Makefile for Solar Controller Project (src layout aware)
# --------------------------------------------------------------------

PYTHON := python3
VENV_DIR := .venv
PIP := $(VENV_DIR)/bin/pip
PY := $(VENV_DIR)/bin/python
PYTEST := $(PY) -m pytest
COVERAGE := $(PY) -m coverage
RUFF := $(PY) -m ruff

# Directories
SRC_DIR := src/solar_controller
TEST_DIR := tests

# --------------------------------------------------------------------
# Docker image settings
# --------------------------------------------------------------------
IMAGE_NAME := solar_controller
PYPROJECT := pyproject.toml

# Retrieve version from pyproject.toml
VERSION := $(shell $(PY) -c "import tomllib; print(tomllib.load(open('$(PYPROJECT)','rb'))['project']['version'])")


# --------------------------------------------------------------------
# Default target
# --------------------------------------------------------------------
.PHONY: all
all: help

# --------------------------------------------------------------------
# Virtual environment
# --------------------------------------------------------------------
.PHONY: venv
venv:
	@echo "Creating virtual environment in $(VENV_DIR)..."
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Upgrading pip..."
	$(PIP) install --upgrade pip

.PHONY: dev
dev: venv
	@echo "Installing development requirements..."
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	@echo "Development environment ready. Activate with: source $(VENV_DIR)/bin/activate"

# --------------------------------------------------------------------
# Run tests
# --------------------------------------------------------------------
.PHONY: test
test:
	PYTHONPATH=src $(PYTEST) -v --tb=short $(TEST_DIR)

.PHONY: test-async
test-async:
	PYTHONPATH=src $(PYTEST) -v --tb=short --asyncio-mode=auto $(TEST_DIR)

# --------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------
.PHONY: coverage
coverage:
	PYTHONPATH=src $(COVERAGE) run --source=$(SRC_DIR) -m pytest $(TEST_DIR)
	PYTHONPATH=src $(COVERAGE) report -m
	PYTHONPATH=src $(COVERAGE) html

# --------------------------------------------------------------------
# Linting / Formatting
# --------------------------------------------------------------------
.PHONY: lint
lint:
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)

.PHONY: lint-fix
lint-fix:
	$(RUFF) check $(SRC_DIR) $(TEST_DIR) --fix

# --------------------------------------------------------------------
# Run main application
# --------------------------------------------------------------------
.PHONY: run
run:
	PYTHONPATH=src $(PY) -m solar_controller.main

# --------------------------------------------------------------------
# Clean temporary files
# --------------------------------------------------------------------
.PHONY: clean
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf coverage.xml
	rm -rf $(VENV_DIR)

# --------------------------------------------------------------------
# Build Docker image
# --------------------------------------------------------------------

.PHONY: docker-build
docker-build:
	@echo "Building Docker image $(IMAGE_NAME) with tags: latest and $(VERSION)..."
	docker build -t $(IMAGE_NAME):latest -t $(IMAGE_NAME):$(VERSION) .

IMAGE_PATTERN := solaredgecontroller-solar-controller

.PHONY: docker-clean
docker-clean:
	@echo "Stopping and removing all containers for images matching $(IMAGE_PATTERN)..."
	-docker ps -a --filter "ancestor=$(IMAGE_PATTERN)" -q | xargs -r docker rm -f

	@echo "Removing all images matching $(IMAGE_PATTERN)..."
	-docker images --format "{{.Repository}}:{{.Tag}}" | grep "$(IMAGE_PATTERN)" | xargs -r docker rmi -f

	@echo "Docker cleanup complete."


# --------------------------------------------------------------------
# Help
# --------------------------------------------------------------------
.PHONY: help
help:
	@echo "Usage:"
	@echo "  make venv             # Create virtual environment"
	@echo "  make dev              # Create venv + install dev requirements"
	@echo "  make test             # Run all tests (PYTHONPATH=src)"
	@echo "  make test-async       # Run async tests (PYTHONPATH=src)"
	@echo "  make coverage         # Run tests with coverage (PYTHONPATH=src)"
	@echo "  make lint             # Check code style with ruff"
	@echo "  make lint-fix         # Auto-fix linting issues with ruff"
	@echo "  make run              # Run main application (PYTHONPATH=src)"
	@echo "  make clean            # Remove temporary files and venv"
