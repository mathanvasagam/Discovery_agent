# Discovery Agent

Discovery Agent is an enterprise-system discovery and integration-planning application. It ingests operational documents, extracts a system inventory with evidence, maps automation goals to integration gaps, generates connector scaffolds, and validates generated artifacts.

## Architecture

1. **Document ingestion** — PDF, DOCX, XLSX, CSV, text, Markdown, and image OCR.
2. **System discovery** — deterministic enterprise catalog plus optional LLM-assisted extraction.
3. **Gap analysis** — required/available/missing systems, data-flow tracing, dependencies, and prioritization.
4. **Connector generation** — Python or Node.js integration scaffolds plus agent definitions.
5. **Validation** — Docker-isolated syntax, static, and runtime checks with network disabled and bounded resources.
6. **Dashboard** — React 19 + TypeScript frontend.

## Quick start

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cd backend
python -m uvicorn main:app --reload
```

Backend API: `http://localhost:8000`

For secure connector validation, start Docker and build the Python sandbox image once:

```bash
docker build -t discovery-agent-python-sandbox:3.12 -f backend/sandbox/python/Dockerfile .
```

Docker validation is the default. For trusted local development only, host execution can be explicitly enabled with `DISCOVERY_VALIDATION_MODE=local`.

### Frontend

Node.js 22+ is recommended.

```bash
cd frontend
npm ci
npm run dev
```

Frontend dev server: `http://localhost:5173`

### Docker Compose

```bash
docker compose up --build
```

Frontend: `http://localhost:8080`
Backend: `http://localhost:8000`

## Configuration

The backend reads `DISCOVERY_*` environment variables. Important options include `DISCOVERY_CORS_ORIGINS`, `DISCOVERY_MAX_UPLOAD_BYTES`, and `DISCOVERY_GROQ_API_KEY`. LLM access is optional; without a Groq key, the system operates in deterministic fallback mode.

## Quality gates

Backend:

```bash
cd backend
python -m pytest core -q
python -m compileall -q .
```

Frontend:

```bash
cd frontend
npm run lint
npm test
npm run build
```

## Security and deployment status

- Upload filenames are normalized, file types are allow-listed, and upload size is bounded.
- CORS origins are configurable rather than globally open.
- Containers run the API as a non-root user and the frontend as a production Nginx build.
- Generated-code validation defaults to a Docker container with networking disabled, memory/CPU/PID limits, a read-only root filesystem, dropped Linux capabilities, and execution timeouts.
- Development-only host validation requires explicit `DISCOVERY_VALIDATION_MODE=local` opt-in and must only be used with trusted code.
- Authentication/authorization should still be added before multi-user or public deployment.

## Accuracy notes

- Generated connectors are integration scaffolds; they are not guaranteed vendor-production connectors.
- Extraction confidence scores are heuristic scores, not statistically calibrated probabilities.
- LLM output is evidence-checked and the deterministic catalog provides fallback behavior when the model provider is unavailable.

## Project status

Functional, test-backed prototype suitable for local demonstrations and portfolio use. The main remaining production-hardening work is authentication/authorization, database migrations, structured observability, deployment monitoring, and a dedicated sandbox execution service for fully containerized deployments.
