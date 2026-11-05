# Verified Run and Evaluation Guide

Status: progressively maintained. Commands are classified by evidence.

## Verified in this audit

Working directory: repository root `minor-main`, Python environment with the repository's test dependencies.

```bash
python -m pytest tests/unit/test_provider_router.py evaluation/metrics/test_retrieval_metrics.py -q
```

Observed result on 2026-10-01: `20 passed`.

```bash
python -m py_compile evaluation/metrics/retrieval_metrics.py evaluation/evaluators/retrieval_evaluator.py
```

Observed result: completed successfully.

```bash
python -m compileall -q backend evaluation tests
python -m pytest -q
```

Observed results on 2026-10-01: compile check completed successfully; `45 passed`.

From `frontend/`:

```bash
npm run build
```

Observed result on 2026-10-01: TypeScript and Vite build passed and emitted production assets.

The dependency-light evaluation self-test was also executed:

```bash
python -m evaluation.runner.run_eval --self-test
```

Observed result: dataset validation, synthetic query execution (10/10), retrieval, generation, citation, performance, modality, and ablation stages passed. OCR/audio were explicitly `NOT RUN`, provider comparison was skipped because the self-test used one provider. Report output: `reports/evaluation/selftest/selftest_2026-10-01_124644`.

## Implemented but not yet verified here

### Backend and frontend

From `minor-main/backend/`, install the repository requirements in the intended virtual environment, then start the API with the command used by the deployment docs. The frontend build is verified above; starting the dev server and browser workflow remain unverified.

### Ollama

Verify the running service and configured model using the installed Ollama CLI, then start the backend and issue a small authenticated query. Record the exact model returned by the service and the response metadata. Do not substitute a model silently.

### Evaluation self-test

The repository documents these entry points, but they still require execution in the current environment before being labelled verified:

```bash
python -m evaluation.runner.run_eval --self-test
python evaluation/run_eval.py --self-test
```

Use the CLI help output as the source of truth if the two runners differ.

### Real dataset evaluation

After authentication, ingestion, and dataset validation:

```bash
python -m evaluation.runner.run_eval --base-url http://localhost:8000 --token <token> --session-id <session-id> --dataset <dataset.json>
```

The exact supported flags must be confirmed with `--help` before use. Preserve the generated run directory and raw per-question results.

### Groq

Supply the key through the existing provider settings UI or secure backend configuration. Validate the key, list models, explicitly activate one returned model, run a query, and confirm response metadata says Groq and that model. No live Groq command or result is claimed here.

## Required evidence for completion

Record environment versions, dataset ID/version, provider, actual model, run ID, start/end timestamps, successful/failed counts, metric applicability, report paths, and warnings. Keep Ollama and Groq runs in separate output directories and compare only overlapping sample IDs and compatible configurations.

## Blocked pending local services or data

- Real ingestion and retrieval quality: requires source documents and a running backend/vector store.
- Ollama smoke test: requires Ollama and the configured model.
- Groq smoke test: requires a valid user credential, network access, and model permission.
- Frontend login/provider-switch E2E: requires backend and frontend services plus a test account.
- Session quality evaluation: requires reference answers and relevance/citation annotations.

## Troubleshooting notes

- A missing module usually means the selected Python interpreter is not the environment where backend requirements were installed.
- An empty retrieval result is not a zero quality score; check session ownership, ingestion completion, modality filters, and vector-store paths.
- A provider shown in the frontend banner is not sufficient evidence; inspect backend request logs and stored assistant-message metadata.
- Do not clear the vector store or overwrite prior reports to repair a test. Use a new isolated session/run ID.