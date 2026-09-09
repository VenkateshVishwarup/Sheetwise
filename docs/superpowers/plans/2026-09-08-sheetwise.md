# Sheetwise Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for sequential implementation. The Sites-owning agent owns all project edits; independent read-only research and review can use subagents.

**Goal:** Upload a sheet, inspect a trustworthy dashboard, and ask questions answered by validated SQL and rendered through A2UI.

**Architecture:** FastAPI owns import, SQLite metadata, isolated DuckDB query execution and the AI workflow. React consumes typed API responses and renders shared A2UI chart components. A single container serves built client assets and the API.

**Tech Stack:** Python, FastAPI, DuckDB, SQLGlot, OpenAI Responses, React, TypeScript, Recharts, A2UI.

**Spec:** docs/superpowers/specs/2026-09-08-sheetwise-design.md

## Global Constraints

- CSV/XLSX files up to 100 MB; one table per dataset.
- AI inputs contain metadata, never raw uploaded rows.
- At most two SQL repairs; execution timeout 10 seconds; maximum 200 result rows.
- Unknown values remain distinct from false and zero.
- Secret fields excluded from storage; personal/free-text fields blocked from agent queries.
- No sample customer data or credentials in Git or client bundles.
- Non-loopback deployment requires WORKSPACE_PASSWORD.

## Task 1: Dataset import and profiling

**Files:** backend/ingest.py, backend/store.py, backend/privacy.py, tests/test_ingest.py, requirements.txt.
**Interface:** ingest_file(path, filename, data_dir, sheet_name=None) returns a profile with id, name, rowCount, columns, warnings and databasePath. Store persists profiles and answers under generated UUIDs.

- [x] Add import tests for exact record counts, distinct users, blank/false semantics, rejected malformed headers, XLSX, secret exclusion and masked previews. A fixture with values `true`, `false`, blank must report one in each group.
- [x] Run `.venv/bin/pytest tests/test_ingest.py -q` and confirm missing-feature failures.
- [x] Stream files to an import directory; use read-only XLSX iteration; load all raw nonsecret values as VARCHAR; derive safe typed columns where every nonempty value converts. Compute exact column statistics. Remove source temporary files.
- [x] Run the import tests and verify the supplied CSV's 4,628 rows, 134 input columns, 193 true / 306 false / 4,129 unknown conversions.

## Task 2: Safe SQL and agent

**Files:** backend/query.py, backend/agent.py, backend/presentation.py, tests/test_query.py, tests/test_agent.py.
**Interface:** execute_query(database_path, columns, sql) returns columns, rows, truncated and elapsedMs. answer_question(profile, question, history) returns SQL, summary, A2UI messages and clarification when needed.

- [x] Test safe aggregate queries and rejection of multiple statements, DDL/DML, table functions, file/network access, other tables, protected columns and nonaggregate row extraction.
- [x] Test clarification for conflicting business fields and bounded correction with a controlled provider response.
- [x] Implement AST validation and execute in a spawned worker with disabled external access and time/memory limits. Validate every repaired query again.
- [x] Implement structured Responses API planning/generation using metadata only, bounded prior context and deterministic result summaries. Show a clear configuration error when AI is unavailable.
- [x] Emit createSurface / updateComponents / updateDataModel messages from a fixed catalog. Verify numeric chart values match SQL results.

## Task 3: API and working UI

**Files:** backend/main.py, backend/auth.py, app/page.tsx, app/globals.css, app/layout.tsx, components/analytics/*, lib/api.ts, lib/types.ts, tests/test_api.py.
**Interface:** /api/status, /api/session, /api/datasets, /api/datasets/{id}, /api/datasets/{id}/preview, /api/datasets/{id}/chat, /api/datasets/{id}/answers, /api/datasets/{id}/pins.

- [x] Test the upload → profile → answer → pin → reload flow, unauthorized requests, invalid IDs, malformed files and standardized errors.
- [x] Implement bounded upload handling, workspace sessions, persistence, profile/preview/dashboard endpoints and a synthetic demo import.
- [x] Build a responsive analytics workspace with navigation rail, dashboard cards, source annotations, searchable column explorer, masked preview, saved answers and an adjacent chat panel. Add import progress, clarification controls, SQL disclosure and empty/error states.
- [x] Show the first useful local preview after a successful route request. Build and type-check the final frontend.

## Task 4: Delivery and review

**Files:** README.md, Dockerfile, compose.yaml, scripts/dev.py, docs/openapi.yaml, .env.example, .gitignore.

- [x] Write the component-first OpenAPI 3.0 contract matching every endpoint, common error objects and realistic examples.
- [x] Add reproducible startup and container instructions, privacy behavior, resource limits, model setup and known limitations.
- [x] Run the full test suite, frontend build/typecheck, supplied-file verification and a live AI smoke test when credentials permit.
- [x] Obtain an independent read-only code review, fix material findings and rerun affected checks. Record actual validation outcomes here.

## Execution record

- Workspace began empty; initialized a dedicated feature branch in place. No existing checkout needed isolation.
- Preserved the approved Python/DuckDB design. Built-in Sites publication cannot host this runtime; local app and container delivery are the deployment target.

- Completed import, query isolation, bounded agent repair, API, React workspace and official A2UI rendering.
- Independent review findings were reproduced and fixed: whole-row SQL access, unused CTE aggregate bypass, host validation, chunked upload limits, unsampled phone detection and numeric precision guards.
- Validation: 33 backend tests and 3 client-side A2UI component tests pass; application lint, TypeScript and production build pass. Generated shadcn source is excluded from application lint.
- Docker image builds and passes HTTP checks for static app delivery, authentication, synthetic import and preview.
- The supplied CSV reconciles to 4,628 rows and 134 source columns. Live model-generated queries returned exactly 4,628 total records and conversion counts of 193 true, 306 false and 4,129 unknown. Only metadata and question context were sent to the provider.
- The official A2UI renderer is client-only; component tests use a DOM environment rather than unsupported server rendering.
- No browser interaction testing or remote deployment was performed. Local credentials and dataset files remain outside version control.
