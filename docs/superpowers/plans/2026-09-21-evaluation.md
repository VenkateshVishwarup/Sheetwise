# Outcome Evaluation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a safe, saved snapshot-outcome evaluation workflow.
**Architecture:** A deterministic readiness service and credential-free subprocess return aggregate reports; immutable runs use the existing storage adapters. A dedicated React panel handles setup, checks, results and history.
**Tech Stack:** Existing FastAPI, DuckDB, Python standard library, React and TypeScript. No new runtime dependency.
**Spec:** docs/superpowers/specs/2026-09-21-evaluation.md

## Global Constraints
- Snapshot boolean outcomes only; future intent blocked.
- No raw rows or personal fields sent to external AI.
- At most 20,000 labelled rows, 12 features, 100 categories per feature.
- At least 100 known outcomes and 20 in each class.
- Worker timeout 30 seconds, DuckDB memory 128 MB, one thread.
- Model evaluation never enables individual scoring automatically.

### Task 1: Readiness and bounded evaluation
Files: backend/evaluation.py, backend/evaluation_worker.py, tests/test_evaluation.py.
Interfaces: run_evaluation(profile, definition, evaluate=False) returns a readiness object or completed run; worker recomputes checks. definition includes targetKey, featureKeys, purpose, positiveMeaning, negativeMeaning, labelsConfirmed, featuresConfirmed, categoriesReviewed.
- [x] Add failing tests: synthetic true/false/null counts; invalid personal/target fields; category collision blocking; future request blocking; tied-score metrics; repeatable held-out results with unknown exclusion.
- [x] Implement validation, fixed split, categorical Bayes and reference metrics, isolated subprocess transport.
- [x] Run `.venv/bin/pytest tests/test_evaluation.py -q`.

### Task 2: API and persistence
Files: backend/main.py, backend/store.py, backend/cloud_store.py, tests/test_evaluation_api.py, scripts/generate_openapi.py, docs/openapi.yaml.
Interfaces: POST /api/datasets/{dataset_id}/readiness; POST /api/datasets/{dataset_id}/evaluations (201); GET /api/datasets/{dataset_id}/evaluations. All use existing session boundaries.
- [x] Add failing upload/check/evaluate/reload tests and private Blob roundtrip coverage.
- [x] Implement local evaluations table and immutable Blob runs, one-per-instance operation gate, request constraints and response handling.
- [x] Define every API field in components with examples; regenerate and validate contract.

### Task 3: Workspace workflow
Files: components/analytics/evaluation-panel.tsx, lib/evaluation.ts, lib/types.ts, app/page.tsx, app/globals.css, tests/evaluation.test.ts.
- [x] Add tests for setup eligibility and known-versus-unknown report rendering.
- [x] Implement Evaluate navigation, labelled form, selectable inputs, readiness issues, confirmations, metric comparison and saved-run history.
- [x] Invalidate old checks on form edits; disable duplicate submissions; show request failures; prevent stale results after dataset switches.
- [x] Run Python and TS suites, typecheck, lint and build. Validate a representative local dataset readiness without sending rows externally.
- [x] Document boundaries in README and record verification. Keep implementation on the feature branch until integration.

## Verification record — September 22, 2026

54 Python tests and 7 frontend tests passed; type checking, lint, API contract validation, diff whitespace check and production build passed. The build retains the existing large-chunk advisory; Python emits an upstream TestClient deprecation warning.

Browser verification on the separate local synthetic workspace: 1,120 known outcomes, 160 unknown excluded; 840 training and 280 withheld records. Evaluation completed, persisted and was visible after reload. Future intent displayed HISTORY_REQUIRED and disabled execution. Screens inspected at the existing desktop viewport.

Read-only readiness on the supplied local dataset reconciled 499 known outcomes (193 true, 306 false) and 4,129 unknown. Input confirmation and category collision checks blocked evaluation as intended; no real source rows were uploaded.

Independent review identified normalized-category loss and camelCase outcome-name gaps. Both were reproduced with failing tests and corrected. Evaluation now projects selected permitted fields from preserved original values; case/spacing distinctions survive unless a value is blank. Follow-up review found no remaining significant issue in the fixes.

Implementation is on codex/v2-evaluation, with a separate synthetic preview at http://127.0.0.1:8002/. No production deployment is part of this verification record.
