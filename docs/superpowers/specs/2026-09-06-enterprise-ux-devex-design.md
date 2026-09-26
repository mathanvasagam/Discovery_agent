# Discovery Agent Enterprise UX and Developer Experience Design

**Date:** 2026-09-06
**Status:** Implemented - historical design record

> **Current state (11 September 2026):** The UX/dev-ex scope in this document has been implemented. Subsequent deployment hardening extended the original scope: Discovery Agent is now live at `https://discovery-agent-demo.onrender.com/` using a single Render service, Supabase PostgreSQL, Gemini/Groq provider failover, signed anonymous workspace isolation, rate limits, non-retained original uploads, security headers, and static-only hosted connector validation. The original "Excluded" list below is preserved to document the scope decision that existed when this design was approved; public-cloud deployment was added later as a separate implementation phase.

For the current architecture, use [`../../TECHNICAL_GUIDE.md`](../../TECHNICAL_GUIDE.md) and [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md) as the source of truth.

## Objective

Upgrade Discovery Agent from a functional prototype interface into a production-oriented enterprise operator console while preserving the existing backend workflows and API contracts. In parallel, make local development easier to run and verify, and add a technical guide that explains the architecture and terminology from first principles.

## Scope

### Included

- Refactor the React frontend so the application is no longer implemented as one monolithic `App.tsx`.
- Replace the current AI-template-like visual language with a restrained enterprise console design.
- Preserve all currently working workflows: upload/discovery, inventory, use-case creation, goal discovery, gap analysis, connector generation, validation, reports, and Groq status checks.
- Remove synthetic presentation content such as fake report timestamps and generic demo copy.
- Add reusable layout, status, table, feedback, form, and icon primitives without introducing a heavy UI framework.
- Add a cross-platform `scripts/dev.py` launcher for local development.
- Add a `scripts/verify.py` quality-gate runner.
- Add `docs/TECHNICAL_GUIDE.md` explaining architecture, terminology, data flow, code structure, security controls, CI, deployment, and troubleshooting.
- Update the root README to link to the technical guide and runnable scripts.
- Preserve secure Docker-first generated-code validation. Do not mount the host Docker socket into the main backend container.

### Excluded

- Authentication/authorization implementation.
- Database migration framework introduction.
- Backend API redesign.
- New business capabilities unrelated to the current discovery/gap/code-generation workflow.
- A new frontend framework, component library, global state library, or router unless required by an existing workflow.
- Public-cloud deployment automation.

## UX Direction

The interface should resemble a manually designed engineering/product console rather than an AI-generated dashboard.

### Principles

1. **Information before decoration** — dense but readable operational information takes priority over hero banners and ornamental cards.
2. **Restrained surfaces** — use borders, whitespace, typography, and hierarchy rather than gradients, glass effects, heavy shadows, or excessive rounded cards.
3. **Semantic color only** — one neutral blue accent plus success/warning/error states. Color must communicate meaning.
4. **Real system state** — never invent timestamps, progress, success, or operational status that the backend did not provide.
5. **Explicit forms** — fields use labels and helper text, not placeholder-only interaction design.
6. **Action hierarchy** — primary actions are visually distinct; destructive actions are separated and clearly marked.
7. **Enterprise density** — tables, toolbars, metadata, and status summaries should be compact and scannable.
8. **Responsive by composition** — navigation and content adapt cleanly from desktop to small screens without turning into an unstructured horizontal button strip.

## Frontend Architecture

Target structure:

```text
frontend/src/
├── app/
│   ├── AppShell.tsx
│   └── navigation.ts
├── components/
│   ├── DataTable.tsx
│   ├── EmptyState.tsx
│   ├── Field.tsx
│   ├── Icon.tsx
│   ├── PageHeader.tsx
│   ├── Section.tsx
│   ├── StatusBadge.tsx
│   └── WorkflowProgress.tsx
├── pages/
│   ├── DashboardPage.tsx
│   ├── DocumentsPage.tsx
│   ├── InventoryPage.tsx
│   ├── GapAnalysisPage.tsx
│   ├── GenerationPage.tsx
│   └── ReportsPage.tsx
├── services/
│   └── api.ts
├── types/
│   └── api.ts
├── App.tsx
├── index.css
└── main.tsx
```

`App.tsx` remains the workflow/state coordinator. Page components receive explicit data and action props. Pure presentation components do not call the API directly.

## Page Design

### Dashboard

- Page title and concise operational description; no marketing hero.
- Four compact key metrics: discovered systems, average heuristic confidence, open integration gaps, generated artifacts.
- Recent discovered systems in a compact table/list.
- Pipeline overview showing the three implemented stages and their actionable entry points.
- Environment/status panel showing backend availability and Groq configuration/connection state without exaggerating readiness.

### Documents

- Upload panel with supported file types and selected-file metadata.
- Explicit upload label/help text.
- Uploaded-document table with filename and size.
- Real workflow progress tied to the request lifecycle.

### Inventory

- Search/filter toolbar.
- Export actions grouped separately from destructive inventory clearing.
- Dense evidence-focused table.
- Confidence labeled as heuristic confidence, not calibrated probability.
- Human-review state presented semantically.
- Useful empty state.

### Gap Analysis

- Structured use-case form with labels and business context fields.
- Separate manual and auto-discovery actions.
- Use-case selector and recommendation summary.
- Gap table with missing/available status, priority, effort, and generation action.
- Data-flow table with blocked/flowing state.

### Code Generation

- Structured connector configuration form.
- Artifact workspace with code/tests/readme tabs.
- Validation summary separated from code preview.
- Dependencies and sandbox outcome visible as metadata.

### Reports

- Operation/validation history based only on real returned data.
- Do not render fake timestamps when none are provided; show an em dash or omit the column instead.
- Status, filename/resource, output summary, warning/error counts.

## Design System

- Font stack: system UI stack (`Inter` only when installed locally; no remote font dependency).
- Base background: neutral gray.
- Sidebar: near-black/slate, no gradient.
- Content panels: white with subtle 1px borders.
- Radius: moderate (6–10px), not pill-heavy.
- Shadows: minimal or none.
- Accent: restrained blue.
- Status colors: green / amber / red with accessible contrast.
- Spacing scale based on 4px increments.
- Buttons: primary, secondary, ghost, destructive.
- Status badges: only when data has semantic status.

## Developer Experience

### `scripts/dev.py`

Responsibilities:

- Resolve repository root.
- Check Python runtime.
- Check Node and npm availability.
- Check required frontend installation (`frontend/node_modules`) and emit actionable installation instructions when missing.
- Create backend runtime directories if needed.
- Start backend using the current Python executable and `uvicorn backend.main:app --reload` from repository root.
- Start frontend using `npm run dev` in `frontend`.
- Forward termination and cleanly stop both child processes on Ctrl+C.
- Exit non-zero when either child exits unexpectedly.
- Provide clear local URLs.

It must not silently install packages or modify developer machines.

### `scripts/verify.py`

Run deterministic quality gates:

1. backend pytest suite;
2. backend compileall;
3. frontend lint;
4. frontend tests;
5. frontend production build;
6. Compose config validation when Docker Compose is available.

The script should print each command and stop/report clearly on failure. Docker Compose validation may be skipped with a clear reason when Docker/Compose is unavailable; core backend/frontend checks remain required.

## Technical Guide

Create `docs/TECHNICAL_GUIDE.md` as a study/reference document. It must explain not only *what* the code does but *why* each concept exists and where it appears in this repository.

Required sections:

1. Product/problem statement.
2. System architecture and end-to-end request lifecycle.
3. Repository map.
4. Backend stack: FastAPI, routes, HTTP, JSON, multipart uploads, Pydantic, SQLModel, SQLite, persistence.
5. Document ingestion/extraction pipeline and supported formats.
6. Redaction and evidence handling.
7. Deterministic discovery and optional Groq-assisted LLM mode.
8. Heuristic confidence semantics.
9. Use cases, data-flow modeling, dependency graphs, and gap analysis.
10. Connector generation and generated artifact structure.
11. Sandbox validation and every Docker hardening flag used.
12. Frontend architecture: React, TypeScript, state, effects, callbacks, deferred values, API client, components.
13. Build/runtime distinction: Vite development, TypeScript build, Nginx production serving.
14. Dockerfiles and Docker Compose.
15. Environment variables with defaults and examples.
16. CI/GitHub Actions flow.
17. Local developer workflow using `scripts/dev.py` and `scripts/verify.py`.
18. Security boundaries and current production limitations.
19. Troubleshooting.
20. Interview/project-review questions with concise answers.
21. Glossary of technical keywords.

## Security Boundaries

- Generated-code validation remains Docker-first.
- Local validation is development-only and explicit.
- Do not mount `/var/run/docker.sock` or Windows Docker named pipes into the main API container as a convenience fix.
- Public/multi-user deployment still requires authentication/authorization, rate limiting, migrations, observability, and dedicated sandbox execution infrastructure.
- README and guide must label generated connectors as scaffolds and confidence as heuristic.

## Testing and Acceptance Criteria

Implementation is accepted when:

- Existing backend tests pass.
- Frontend lint passes.
- Frontend tests pass.
- Frontend production build passes.
- `python scripts/verify.py` succeeds on the available local toolchain, with Docker checks explicitly reported if unavailable.
- `python scripts/dev.py --check` (or equivalent non-starting preflight mode) verifies prerequisites without launching long-running servers.
- Current application workflows remain wired to the same APIs.
- `App.tsx` is materially reduced and page responsibilities are separated.
- No fake timestamps or simulated progress delays remain.
- No gradients or decorative AI-dashboard hero remain in the primary interface.
- `docs/TECHNICAL_GUIDE.md` exists and covers all required sections.
- Root README links to the technical guide and developer scripts.
- Git diff contains no runtime DB, uploaded documents, generated connector output, credentials, or `.env` secrets.
