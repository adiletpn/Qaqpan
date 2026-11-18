PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup samples eval demo dev api web test types

setup:          ## venv (Python 3.12) + deps + web deps
	test -d .venv || python3.12 -m venv .venv
	$(PIP) install -q -r requirements.txt
	cd web && npm install

samples:        ## render demo SMS screenshots -> web/public/samples, data/samples.json
	$(PY) scripts/make_samples.py

eval:           ## accuracy of the message checker on data/messages_eval.jsonl
	$(PY) scripts/eval_messages.py

demo:           ## build web + serve everything on :8000 (LLM: cache only)
	cd web && npm run build
	QALQAN_DEMO=1 $(PY) -m uvicorn api.main:app --host 0.0.0.0 --port 8000

api:            ## API with reload on :8000
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:            ## vite dev server on :5173 (proxies /api to :8000)
	cd web && npm run dev

test:
	$(PY) -m pytest -q

types:          ## OpenAPI -> web/src/api/types.ts
	$(PY) -c "import json; from api.main import app; print(json.dumps(app.openapi()))" > web/openapi.json
	cd web && npx openapi-typescript openapi.json -o src/api/types.ts
