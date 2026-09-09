# Sheetwise: approved product design

Approved in conversation on 2026-09-08. Build an internal team MVP that accepts CSV/XLSX files up to 100 MB, produces an evidence-based default dashboard, and answers natural-language questions through validated SQL with A2UI responses.

## Product

The main screen is a working dashboard with a dataset switcher, upload action, Overview / Data / Saved views, and an adjacent conversational analysis panel. An empty workspace offers upload and a clearly labeled synthetic demo. The supplied private CSV is used only in local verification, never committed or embedded in the frontend.

Each import becomes an independent dataset. XLSX imports the first worksheet unless a worksheet name is supplied. Preserve original non-secret values, map headers to safe SQL identifiers, infer data types conservatively, and keep unknown/blank values separate from false and zero. Detect personal, secret, free-text and JSON columns. Drop secrets from the analytical copy; mask personal values in previews and exclude protected columns from agent queries.

Default dashboards derive exact counts and useful distributions deterministically. Every chart records SQL and its source column. Suppress unsupported funnels, fabricated trends, and ambiguous business conversion rates. All computed conversion cards name their source field and show true, false, and unknown counts. Saved answers survive reloads.

## Query workflow

Select relevant schema metadata, make a concise analysis plan, generate DuckDB SQL with structured output, validate a single read-only query against the selected dataset and allowed functions, execute under time/memory/result limits, and permit at most two repairs. Resolve ambiguous business columns with an explicit clarification. Conversations preserve prior questions and validated SQL per dataset. No keyword-based substitute masquerades as an AI agent when credentials are absent.

AI inputs contain metadata, never raw uploaded rows. Personal and free-text query values are excluded. No result data needs to be sent to the model: the backend generates the factual result summary and A2UI data bindings directly from execution results. Treat every uploaded cell and header as untrusted data. Configure the model through an environment variable; use the OpenAI Responses API with storage disabled.

## Presentation

Use the A2UI 0.9 family protocol with an application-owned catalog for Metric, BarChart, DataTable and Notice. Validate messages before rendering, bind components to actual execution data, and expose no arbitrary executable markup or model-defined network actions. Default dashboards and chat answers share this renderer. Responsive layout, keyboard controls, loading, errors, empty results and accessible text alternatives are required.

## Deployment and privacy

React frontend from the Sites starter; Python FastAPI backend with DuckDB datasets and SQLite application metadata. The Python runtime is incompatible with the built-in Cloudflare Sites runtime, so preserve the approved stack and deliver local execution plus a Docker deployment. Do not publish a disconnected frontend. Loopback development can operate without a password; any non-loopback deployment requires WORKSPACE_PASSWORD. Sessions use HttpOnly cookies, origin checks protect writes, and secrets never enter client assets.

## Verification

Test CSV and XLSX imports, null/boolean semantics, credential exclusion, privacy filtering, SQL allowlisting and attempts to access files or other datasets, bounded execution, persisted conversations/pins, authentication, invalid uploads and query repair. Verify the supplied CSV locally against independent Python counts. Run a live AI query with safe metadata when a usable credential exists. Build and type-check the frontend. Provide startup instructions and a component-first OpenAPI 3.0 contract with realistic examples and common error responses.
