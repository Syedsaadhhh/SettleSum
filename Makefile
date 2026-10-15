.PHONY: install build test serve dev
install:
	python -m pip install -r backend/requirements.txt
	npm --prefix frontend ci
build:
	npm --prefix frontend run build
test:
	python scripts/audit_static.py
	python -m pytest -q backend
	npm --prefix frontend test
serve:
	python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
dev:
	bash scripts/dev.sh
