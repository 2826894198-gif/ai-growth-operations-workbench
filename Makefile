UV ?= uv
COMPOSE ?= docker compose
DASHBOARD_PORT ?= 15173

.PHONY: bootstrap install-backend install-worker install-frontend up up-safe seed-safe verify-local down migrate test test-all test-integration smoke-browser smoke-data smoke-rules smoke-ai lint demo-seed seed-demo-data seed-ai-demo sync-meta sync-google sync-shopify backfill-meta backfill-google backfill-shopify rules-load rules-evaluate rules-evaluate-meta rules-evaluate-google rules-shadow rules-replay rules-simulate rules-test-scenarios ai-run-daily ai-run-weekly ai-query ai-analyze-creative ai-evals ai-evals-agent seed-social-demo smoke-social smoke-execution execution-worker execution-dry-run execution-shadow screenshot-0601 fix-schema-0008 config-check instagram-preflight production-check migration-check backup-db-logical backup-db-base verify-backups restore-drill smoke-production-readonly

bootstrap: install-backend install-worker install-frontend

install-backend:
	$(UV) venv backend/.venv --python 3.12
	$(UV) pip install --python backend/.venv/bin/python -e "backend[dev,google]"

install-worker:
	$(UV) venv browser-worker/.venv --python 3.12
	$(UV) pip install --python browser-worker/.venv/bin/python -e "browser-worker[dev]"
	browser-worker/.venv/bin/playwright install chromium

install-frontend:
	cd frontend && npm ci

up:
	$(COMPOSE) up -d --build

up-safe:
	DASHBOARD_PORT=$(DASHBOARD_PORT) $(COMPOSE) -f compose.yaml -f compose.dev.yaml up -d --build

seed-safe:
	DASHBOARD_PORT=$(DASHBOARD_PORT) $(COMPOSE) -f compose.yaml -f compose.dev.yaml --profile tools run --build --rm seed-demo

verify-local:
	curl --fail --silent http://127.0.0.1:8000/readyz
	curl --fail --silent http://127.0.0.1:$(DASHBOARD_PORT)/ > /dev/null
	@echo "local stack ready: http://127.0.0.1:$(DASHBOARD_PORT)"

down:
	DASHBOARD_PORT=$(DASHBOARD_PORT) $(COMPOSE) -f compose.yaml -f compose.dev.yaml down

migrate:
	cd backend && .venv/bin/alembic upgrade head

migration-check:
	cd backend && .venv/bin/alembic upgrade head --sql > /dev/null && echo "migration check OK"

config-check:
	cd backend && .venv/bin/python ../scripts/validate_config.py

instagram-preflight:
	cd backend && .venv/bin/python ../scripts/instagram_live_preflight.py

production-check:
	cd backend && .venv/bin/python ../scripts/production_check.py

test:
	cd backend && .venv/bin/pytest ../tests/unit -q

test-all:
	cd backend && .venv/bin/pytest ../tests -q

test-integration:
	cd backend && .venv/bin/pytest ../tests/integration -q

smoke-browser:
	cd browser-worker && .venv/bin/python -m worker.main smoke

lint:
	cd backend && .venv/bin/ruff check app ../tests

demo-seed:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo.db .venv/bin/python ../scripts/seed_demo.py

seed-demo-data:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db .venv/bin/python ../scripts/seed_demo_data.py

smoke-data:
	cd backend && DATABASE_URL=sqlite+aiosqlite:////tmp/smoke_data.db REDIS_URL=redis://127.0.0.1:6379/0 DATA_PROVIDER_MODE=mock .venv/bin/python ../scripts/smoke_data.py

smoke-rules:
	cd backend && DATABASE_URL=sqlite+aiosqlite:////tmp/smoke_rules.db DATA_PROVIDER_MODE=mock RULE_ENGINE_MODE=active .venv/bin/python ../scripts/smoke_rules.py

sync-meta:
	cd backend && .venv/bin/python ../scripts/sync_one.py META_ADS

sync-google:
	cd backend && .venv/bin/python ../scripts/sync_one.py GOOGLE_ADS

sync-shopify:
	cd backend && .venv/bin/python ../scripts/sync_one.py SHOPIFY

backfill-meta:
	cd backend && .venv/bin/python ../scripts/backfill_one.py META_ADS $(DAYS)

backfill-google:
	cd backend && .venv/bin/python ../scripts/backfill_one.py GOOGLE_ADS $(DAYS)

backfill-shopify:
	cd backend && .venv/bin/python ../scripts/backfill_one.py SHOPIFY $(DAYS)

rules-load:
	cd backend && .venv/bin/python ../scripts/rules_load.py

rules-shadow:
	cd backend && RULE_STATUS=SHADOW RULE_FORCE_STATUS=1 .venv/bin/python ../scripts/rules_load.py

rules-evaluate:
	cd backend && .venv/bin/python ../scripts/rules_evaluate.py

rules-evaluate-meta:
	cd backend && .venv/bin/python ../scripts/rules_evaluate.py META_*

rules-evaluate-google:
	cd backend && .venv/bin/python ../scripts/rules_evaluate.py GOOGLE_*

rules-replay:
	cd backend && .venv/bin/python ../scripts/rules_replay.py META_NO_PURCHASE_BURN $(DAYS)

rules-simulate:
	cd backend && .venv/bin/python ../scripts/rules_simulate.py $(RULE)

rules-test-scenarios:
	cd backend && .venv/bin/pytest ../tests/rules -q

seed-ai-demo:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/seed_ai_demo.py

ai-run-daily:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/ai_cli.py daily

ai-run-weekly:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/ai_cli.py weekly

ai-query:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/ai_cli.py query "$(QUERY)"

ai-analyze-creative:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/ai_cli.py creative $(CREATIVE_ID)

ai-evals:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/ai_cli.py evals

ai-evals-agent:
	cd backend && DATABASE_URL=sqlite+aiosqlite:///./demo_data.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/ai_cli.py evals --suite $(AGENT)

smoke-ai:
	cd backend && DATABASE_URL=sqlite+aiosqlite:////tmp/smoke_ai.db AI_PROVIDER_MODE=mock .venv/bin/python ../scripts/smoke_ai.py

seed-social-demo:
	cd backend && .venv/bin/python ../scripts/seed_social_demo.py

smoke-social:
	cd backend && .venv/bin/python ../scripts/smoke_social.py

smoke-execution:
	cd backend && EXECUTION_ENABLED=true EXECUTION_MODE=manual .venv/bin/python ../scripts/smoke_execution.py

execution-worker:
	cd backend && .venv/bin/python -m app.execution.worker --queue $(QUEUE) --concurrency $(CONCURRENCY)

execution-dry-run:
	cd backend && EXECUTION_ENABLED=true .venv/bin/python ../scripts/execution_cli.py dry-run $(INTENT_ID)

execution-shadow:
	cd backend && EXECUTION_ENABLED=true .venv/bin/python ../scripts/execution_cli.py shadow $(INTENT_ID)

screenshot-0601:
	browser-worker/.venv/bin/python scripts/screenshot_part0601.py

fix-schema-0008:
	cd backend && .venv/bin/python ../scripts/fix_schema_0008.py ../demo_data.db

seed-governance:
	cd backend && .venv/bin/python ../scripts/seed_governance.py

backup-db-logical:
	bash scripts/backup.sh logical

backup-db-base:
	bash scripts/backup.sh base

verify-backups:
	bash scripts/backup.sh verify

restore-drill:
	bash scripts/backup.sh restore-drill

smoke-production-readonly:
	cd backend && APP_ENV=production EXECUTION_MODE=manual EXECUTION_ENABLED=true .venv/bin/python -c "import asyncio; from app.core.database import async_session_factory; from app.execution.engine import dry_run_intent; print('read-only production smoke ready; run with INTENT_ID')"
