# Sheetwise V2: outcome readiness and evaluation

Approved direction: implement data readiness and model evaluation before enabling prediction output. The user confirmed false is not converted at export time. This is a snapshot-status pilot, not future forecasting.

## Experience
An Evaluate tab offers a boolean outcome, a written definition of true and false, up to 12 permitted categorical/boolean inputs, and confirmations about label meaning and input timing. A readiness report shows known/unknown outcomes, class counts, column issues, and category naming collisions without returning raw categories. Future-outcome selection is explicitly blocked with guidance to obtain dated historical observations and an outcome horizon.

Users must acknowledge category distinctions flagged by normalization checks. Actual categories are never silently merged. Protected, identifier, free-text and obvious outcome/status fields cannot be features. Unknown targets remain excluded. Data owners confirm feature timing; the app cannot infer historical availability from a snapshot.

For eligible data, Run evaluation compares a training-prevalence reference with a Laplace-smoothed categorical naive Bayes model using a fixed stratified 75/25 holdout. Only aggregate ROC AUC, average precision and Brier error are returned. These are pilot metrics, never permission to score unknown rows. No TabFM weights or production prediction endpoint are included.

## Architecture and limits
New backend evaluation module and credential-free worker. Readiness and evaluation run in a killable subprocess (30 seconds, DuckDB 128 MB, one thread); input at most 20,000 labelled rows, 12 features, 100 distinct non-null values per feature, at least 100 known outcomes and 20 in each class. No added runtime dependencies or external model service. Existing authenticated session and origin boundaries apply; a per-instance gate admits one evaluation operation. Server recomputes readiness when evaluation is submitted.

Persist immutable successful runs with their definitions, checked readiness, aggregate metrics, split counts, algorithm version and creation timestamp. SQLite locally; private Blob objects in cloud. Saved runs are browsable after reload. Rejected readiness checks do not persist a run. Database paths, row values and individual scores never appear in responses.

## Validation
Synthetic fixtures verify unknown exclusion, source-name collisions, protected/target/outcome fields, insufficient classes, unsupported future intent, no test-set leakage, tied-score metrics, independent persistence, authenticated API boundaries and rerun determinism. Frontend checks cover setup validation and result rendering. Existing Python/TS suites, contract validation, lint, typecheck and production build must pass.
