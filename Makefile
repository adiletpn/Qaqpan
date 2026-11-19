PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup samples eval demo dev api web test types e2e lint warm video

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
	QAQPAN_DEMO=1 $(PY) -m uvicorn api.main:app --host 0.0.0.0 --port 8000

api:            ## API with reload on :8000
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:            ## vite dev server on :5173 (proxies /api to :8000)
	cd web && npm run dev

test:
	$(PY) -m pytest -q

types:          ## OpenAPI -> web/src/api/types.ts
	$(PY) -c "import json; from api.main import app; print(json.dumps(app.openapi()))" > web/openapi.json
	cd web && npx openapi-typescript openapi.json -o src/api/types.ts

e2e:            ## click through the whole demo in headless Chrome (server must run on :8000)
	$(PY) scripts/e2e_stage.py http://localhost:8000 e2e_shots

lint:
	cd web && npx eslint src

warm:           ## fill data/llm_cache with AI answers for the demo screenshots (needs XKIRO_API_KEY in .env)
	$(PY) scripts/warm_llm_cache.py

video:          ## record the narrated demo video (server must run on :8000) -> video/qaqpan_demo.mp4
	$(PY) scripts/record_demo.py http://localhost:8000 video/qaqpan_demo.mp4
