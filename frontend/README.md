# Discovery Agent Frontend

React + TypeScript operator console for the [Discovery Agent](../README.md) enterprise system-discovery and integration-intelligence platform.

**Live application:** https://discovery-agent-demo.onrender.com/

## Responsibilities

The frontend is an operator interface. It does not own discovery algorithms, persistence, secrets, or generated-code execution. Those responsibilities remain in the FastAPI backend.

The UI provides six primary workspaces:

- **Dashboard** - system counts, heuristic confidence, integration gaps, generated artifacts, provider/runtime trust state.
- **Documents** - upload enterprise documents and review processed-file state.
- **System Inventory** - search/filter discovered systems, inspect evidence, confidence, provenance and export data.
- **Gap Analysis** - create/discover automation use cases and compare required systems with the observed estate.
- **Code Generation** - configure, generate and validate Python/Node.js connector scaffolds.
- **Reports** - review documents, inventory, artifacts and validation history returned by the backend.

## Architecture

```text
src/
├── app/
│   ├── AppShell.tsx
│   └── navigation.ts
├── components/
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
├── services/api.ts
├── types/api.ts
├── App.tsx
└── main.tsx
```

`App.tsx` is the workflow/state coordinator. Page components receive explicit data and action props. `services/api.ts` centralizes browser-to-backend requests and `types/api.ts` defines the frontend API contracts.

## API behavior

Development defaults to:

```text
http://localhost:8000
```

when `VITE_API_URL` is not explicitly set.

The hosted build intentionally uses same-origin requests. React and FastAPI are packaged into the same Render service, so the production frontend does not need a separate public API URL.

## Development

From `frontend/`:

```bash
npm ci
npm run dev
```

Default local URL:

```text
http://127.0.0.1:5173
```

The backend should normally be available at `http://127.0.0.1:8000`.

## Quality gates

```bash
npm run lint
npm test
npm run build
```

Current verified state:

```text
ESLint                  pass
Vitest                  5 / 5 pass
TypeScript/Vite build   pass
```

The repository-level verifier runs these together with backend checks:

```bash
python ../scripts/verify.py
```

## Design principles

The interface deliberately avoids generic AI-dashboard styling. It uses a restrained enterprise-console design with:

- neutral surfaces and one primary accent;
- compact operational data presentation;
- explicit field labels and help text;
- semantic status colors only;
- no fake timestamps or simulated backend stages;
- real backend/provider/runtime state;
- responsive layouts without a heavy component framework.

## Production serving

The live Render deployment uses the multi-stage [`backend/Dockerfile`](../backend/Dockerfile):

1. Node 22 installs frontend dependencies.
2. Vite builds `frontend/dist/`.
3. The built files are copied into the Python/FastAPI image.
4. FastAPI serves the React application and API from one origin.

A separate [`frontend/Dockerfile`](./Dockerfile) + Nginx configuration remains available for the local/two-container Docker Compose profile.

## Related documentation

- [Project README](../README.md)
- [Technical Guide](../docs/TECHNICAL_GUIDE.md)
- [Deployment & Operations Runbook](../docs/DEPLOYMENT.md)
