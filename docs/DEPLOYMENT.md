# Discovery Agent — Free Demo Deployment Runbook

This runbook deploys Discovery Agent as a public portfolio/demo application with a single Render web service and Supabase PostgreSQL.

## Target architecture

```text
Browser
  |
  | HTTPS
  v
Render Free Web Service
  |- React production build (same origin)
  |- FastAPI API
  |- signed anonymous workspace cookie
  |- per-workspace rate limits
  |- static-only connector validation
  |
  +----> Supabase PostgreSQL
  |       durable application state
  |
  +----> Gemini API
  |        |
  |        +-- failure/quota --> Groq
  |                              |
  |                              +-- failure --> deterministic fallback
  |
  +----> temporary upload processing
          original deleted after redacted extraction
```

The public demo intentionally does **not** retain original uploaded documents. Redacted extracted text, discovered systems, use cases, gap reports, generated artifact JSON, and validation results are persisted in PostgreSQL.

## Why Supabase PostgreSQL instead of MongoDB

Discovery Agent already uses SQLModel/SQLAlchemy and relational records with foreign-key relationships. Supabase PostgreSQL therefore preserves the existing persistence architecture and requires only a database connection change. Moving to MongoDB would require replacing the ORM/session/query layer and does not provide a material benefit for this project.

## About the Supabase MCP in VS Code

The Supabase MCP is useful for inspecting the project, running SQL, and managing Supabase while developing. Discovery Agent does **not** depend on the MCP at runtime. The deployed application connects to Supabase through the PostgreSQL connection string stored only in Render's secret environment variables.

This separation is intentional: developer tooling should not be a production runtime dependency.

## 1. Prepare Supabase

1. Open the Supabase project you want to use for Discovery Agent.
2. Open **Connect** for the database.
3. Choose the **Transaction pooler** connection string.
4. Copy the complete PostgreSQL URL exactly as Supabase provides it.
5. Do not commit the URL to GitHub, `render.yaml`, source code, screenshots, or documentation.

The application accepts the normal Supabase `postgresql://...` URL and internally selects the Psycopg driver. Prepared statements are disabled for compatibility with transaction pooling.

No manual schema SQL is required for the demo. On first successful startup, SQLModel creates the application tables if they do not already exist.

Expected logical tables include:

- `documentrecord`
- `inventorysystem`
- `usecase`
- `gapreportrecord`
- `generatedartifact`
- `validationrun`

Every persisted application record includes a `workspace_id` used for anonymous demo isolation.

## 2. Rotate exposed credentials before deployment

Any API key or database password that has been pasted into chat, committed, included in a screenshot, or shared elsewhere must be treated as exposed.

Before deployment:

- rotate the Gemini API key previously used during development if it was shared;
- rotate any MongoDB password or URI previously shared;
- rotate Groq credentials if they were exposed;
- use a fresh Supabase database password if an earlier one was disclosed.

Only the replacement credentials should be entered into Render.

## 3. Push the deployment files to GitHub

The repository includes `render.yaml`. Render uses it as a Blueprint.

Important deployment files:

```text
render.yaml
backend/Dockerfile
requirements.txt
backend/settings.py
backend/main.py
backend/core/security.py
backend/core/sandbox.py
frontend/src/services/api.ts
```

The backend Dockerfile is multi-stage: it builds the React frontend first and then copies the production frontend into the FastAPI image. This gives the demo one public origin and one Render service.

## 4. Create the Render Blueprint

1. Sign in to Render.
2. Create a new **Blueprint**.
3. Connect the GitHub repository containing Discovery Agent.
4. Render will detect `render.yaml`.
5. Choose/create the `discovery-agent-demo` service.
6. Keep the Free plan for portfolio/demo use.

The Blueprint is configured to deploy only after repository CI checks pass.

## 5. Enter secret environment variables

Render will request values for variables marked `sync: false`.

### Required

```text
DISCOVERY_DATABASE_URL
GEMINI_API_KEY
```

Set `DISCOVERY_DATABASE_URL` to the exact Supabase transaction-pooler PostgreSQL URL.

Set `GEMINI_API_KEY` to a fresh Gemini API key.

### Optional fallback

```text
DISCOVERY_GROQ_API_KEY
```

If Groq is omitted or rate limited, the application can still use Gemini and ultimately deterministic fallback behavior.

### Automatically configured by the Blueprint

The repository already configures these safe production values:

```text
DISCOVERY_ENVIRONMENT=production
DISCOVERY_WORKSPACE_ISOLATION=true
DISCOVERY_RATE_LIMIT_ENABLED=true
DISCOVERY_RETAIN_UPLOADS=false
DISCOVERY_VALIDATION_MODE=static
DISCOVERY_MAX_UPLOAD_BYTES=10485760
DISCOVERY_LLM_PROVIDER_ORDER=gemini,groq
```

`DISCOVERY_SESSION_SECRET` is generated by Render rather than stored in Git.

## 6. Security behavior in the public demo

### Anonymous workspace isolation

Each browser receives an HTTP-only signed workspace cookie. Database queries are scoped to the workspace ID, so visitors do not share inventory, documents, use cases, gap reports, artifacts, or validation history.

This is demo isolation, not full user authentication. A future production SaaS version should replace or supplement it with authenticated identities and database-level tenant controls.

### Security headers

Responses include controls such as:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- restrictive referrer policy
- restricted browser permissions
- HSTS in production
- Content Security Policy in production

### Upload privacy

Public demo behavior is:

```text
upload -> temporary local file -> parse/OCR -> redact -> extract -> persist redacted text -> delete original
```

This avoids depending on Render's ephemeral filesystem for durable uploads and reduces retention of user-provided source documents.

### Rate limits

Expensive/mutating routes have per-workspace request limits, including document upload, goal discovery, gap analysis, connector generation, validation, and provider verification.

The current limiter is process-memory based and is appropriate for the single-instance free demo. A scaled production deployment should use Redis or another shared rate-limit store.

### Generated connector safety

The public service runs with:

```text
DISCOVERY_VALIDATION_MODE=static
```

Generated connector code is syntax-checked but never executed by the hosted demo.

Local development can continue to use the hardened Docker validation mode. Do not enable host execution on a public service.

## 7. First deployment smoke test

After Render reports a successful deploy, check these in order.

### Readiness

Open:

```text
https://<your-render-service>.onrender.com/ready
```

Expected:

```json
{"status":"ready"}
```

### Application

Open the root Render URL. The React application should load from the same FastAPI service.

### Trust & Runtime panel

The dashboard should report approximately:

```text
Persistence             Managed PostgreSQL
Workspace boundary      Isolated workspace
AI execution            GEMINI configured/connected
Generated validation    Static-only hosted mode
Privacy                  Original uploads removed after extraction
```

### Functional demo

Use the professional sample enterprise document and verify:

1. upload succeeds;
2. system inventory is populated;
3. evidence and confidence are visible;
4. an Invoice Automation use case can be created;
5. Salesforce and NetSuite map as available when discovered;
6. Stripe maps as missing when not present in the source estate;
7. a connector scaffold can be generated;
8. validation reports static-only hosted validation;
9. reports remain visible after a Render restart because records live in Supabase PostgreSQL.

## 8. Recommended demo script

For interviews or portfolio demonstrations:

```text
1. Upload enterprise architecture document
2. Show discovered systems + source evidence
3. Explain confidence / human-review indicators
4. Auto-discover or create an automation goal
5. Run gap analysis
6. Show missing integration and dependency path
7. Generate connector scaffold
8. Show static validation result
9. Open Trust & Runtime panel
10. Explain Gemini -> Groq -> deterministic failover
```

This sequence demonstrates the project's differentiators: evidence-backed discovery, hybrid AI/deterministic reasoning, integration planning, safe code generation, and explicit trust controls.

## 9. Troubleshooting

### Database connection fails

- Re-copy the **Transaction pooler** URL from Supabase.
- Do not manually add angle brackets around the password.
- Prefer the exact URL generated by Supabase instead of constructing it yourself.
- Confirm the Supabase project is active.

### Render says production cannot use SQLite

`DISCOVERY_DATABASE_URL` is missing or incorrect. Production intentionally refuses to start on local SQLite because Render's free filesystem is ephemeral.

### Workspace isolation configuration error

Ensure Render generated `DISCOVERY_SESSION_SECRET`. The service intentionally refuses to start with workspace isolation enabled and no signing secret.

### Connector validation says static-only

That is expected in the hosted demo. It is a security property, not an error.

### Gemini quota exceeded

The provider router attempts the next configured provider. If all external providers fail, deterministic extraction/mapping remains available where supported.

### First request is slow

Free Render web services may spin down when inactive. A cold-start delay is expected for a free portfolio deployment.

## 10. Production evolution beyond the free demo

A real multi-user enterprise deployment should add:

- authenticated users and organizations;
- Supabase Auth or another OIDC provider;
- database-level tenant/RLS enforcement where appropriate;
- Alembic-managed migrations;
- Redis-backed distributed rate limiting;
- managed object storage with explicit retention policies when original document retention is required;
- centralized structured logs and tracing;
- a separate isolated sandbox worker for runtime connector execution;
- malware scanning and deeper document security controls;
- calibrated extraction evaluation and monitoring;
- paid/enterprise LLM data-processing arrangements for confidential documents.

## Official references

- Supabase database connections: https://supabase.com/docs/guides/database/connecting-to-postgres
- Render Blueprints: https://render.com/docs/infrastructure-as-code
- Render Blueprint specification: https://render.com/docs/blueprint-spec
- Render environment variables and secrets: https://render.com/docs/configure-environment-variables
- Render free services: https://render.com/docs/free
