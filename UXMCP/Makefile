.PHONY: help build up down logs test clean import-examples

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## Show logs
	docker-compose logs -f

test: ## Run tests
	docker-compose exec api pytest

clean: ## Clean up volumes and images
	docker-compose down -v
	docker system prune -f

import-examples: ## Import example services
	cd examples && python import_examples.py

shell-api: ## Open shell in API container
	docker-compose exec api bash

shell-mongo: ## Open MongoDB shell
	docker-compose exec mongo mongosh uxmcp

status: ## Show service status
	@echo "Services status:"
	@docker-compose ps