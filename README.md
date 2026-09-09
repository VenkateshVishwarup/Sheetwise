# Sheetwise

A private spreadsheet analytics workspace. Upload CSV/XLSX, get a dashboard, ask natural-language questions, inspect the SQL and save useful answers.

## Run locally

Requires Python 3.12+ and Node 22.13+.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm ci
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env` to a funded OpenAI API key, then:

```sh
.venv/bin/python scripts/dev.py
```

Open the local URL printed by the frontend (usually http://127.0.0.1:3000). The Python API runs on http://127.0.0.1:8000. The `.env` file is read by the Python startup and remains outside version control. Existing shell environment values take precedence.

Uploads and automatic dashboards work without an AI key. Chat uses the OpenAI Responses API, defaults to `gpt-5.6-sol`, and never substitutes hardcoded answers. Set `OPENAI_MODEL` to a compatible model available to your account.

For a production-style local run:

```sh
npm run build
.venv/bin/python -m backend
```

The Python server then serves both the app and API on port 8000.

## Team deployment

```sh
# Set a strong WORKSPACE_PASSWORD and OPENAI_API_KEY in .env first.
docker compose up --build -d
```

The container refuses to start without a password. Compose binds to loopback; expose it to your internal team through a private HTTPS reverse proxy and set `COOKIE_SECURE=true`. A named volume preserves datasets, questions and saved insights. This MVP has one shared workspace/password, not separate user roles or customer tenants. Use one Python process per workspace; upload and chat admission limits are process-local.

The approved Python/DuckDB backend requires a conventional server. The built-in Sites Cloudflare runtime cannot host it; no disconnected frontend has been published there. The React client uses the Sites starter and can be served by this container.

## What happens to a spreadsheet

- Maximum upload: 100 MB, 500 columns, 2 million rows. UTF-8 CSV supports comma, semicolon, tab and pipe delimiters. XLSX reads the first worksheet or the supplied worksheet name. XLSX cached formula values are imported; formulas are not recalculated. Expanded XLSX is capped at 512 MB.
- Every dataset has an immutable DuckDB database. Original nonsecret values and conservative typed values are separate. Blank means unknown; it never silently becomes false or zero. Date parsing supports ISO and day-first values; ambiguous date conventions are flagged.
- Secret-named columns are omitted from the analytical copy. Recognized personal, identifier, free-text and nested JSON fields are protected from chat; previews mask personal values. Privacy classification is conservative and rule-based, not a comprehensive DLP classifier. Ambiguous plain-text names can require additional organization-specific rules before wider deployment.
- The AI receives filtered column metadata and question/history context. No uploaded rows, category samples, distributions or result values are sent to the model. Header names and user questions still reach the model, with obvious contact values screened. The backend generates answer summaries and chart bindings from actual SQL results.
- Query generation uses schema planning, clarification, SQL generation, AST validation and execution-guided repair (maximum two repairs). A worker copies only queryable columns into a separate in-memory database before executing generated SQL. External access and extension loading are disabled. Execution is killable after 10 seconds, with 256 MB DuckDB memory and 200 result rows. Joins, windows, nested subqueries, row extraction and arbitrary functions are deliberately outside the first version.
- Average coverage uses retained columns, excluding discarded secret fields. Default charts use all records, show up to 12 categories, preserve unknowns, and disclose source fields. Rates and journey funnels require explicit definitions; conflicting status fields remain separate.
- Raw upload temporary files are removed after import. Local workspace files remain in `.data/`; team storage uses `/app/data`. There is no automatic retention deletion. Back up or remove a workspace only while its server is stopped.

## A2UI

Both default dashboards and chat answers use the official `@a2ui/react/v0_9` renderer with v0.9.1 messages. The fixed analytics catalog contains Metric, BarChart, LineChart, DataTable and Notice. The server generates `createSurface`, `updateComponents` and `updateDataModel` messages with executed values. The renderer validates these messages and contains no arbitrary HTML, remote media, scripts or model-defined actions.

## API and checks

The component-first OpenAPI 3.0 contract is in [docs/openapi.yaml](docs/openapi.yaml), also available at `/api/openapi.yaml` after authentication. Rebuild it with `.venv/bin/python scripts/generate_openapi.py`.

```sh
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
npm test
npm run typecheck
npm run lint
npm run build
```

Tests cover exact CSV/XLSX import, unknown/boolean handling, phone and secret protection, safe SQL and attempted bypasses, bounded repair, authentication, chunked body limits, persistence and client-side A2UI rendering with real value bindings. Lint covers application code; generated shadcn starter components and its unused mobile hook retain their upstream lint conventions. Private customer data and API keys are never fixtures or committed assets. The optional demo is synthetic.

## Validation in this workspace

The supplied CSV was imported locally and reconciled to 4,628 records, 134 input columns and `lead.is_converted` counts of 193 true, 306 false and 4,129 unknown. Live OpenAI requests using the configured local key successfully generated SQL for the total count and for conversion status groups; executed results exactly matched these counts. Controlled-provider tests verify the complete planning → repair → SQL → A2UI path. All 33 backend tests and 3 A2UI component tests pass, along with application lint, type checking and the production build. The Docker image builds, and its runtime passed password protection, login, synthetic import, profile and preview checks. No browser interaction testing or remote deployment has been performed.
