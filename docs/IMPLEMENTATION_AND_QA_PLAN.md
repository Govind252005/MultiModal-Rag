# Implementation and QA Plan

Statuses: `[ ]` not started, `[~]` in progress, `[x]` completed and verified, `[!]` blocked or requires user input.

| Status | ID | Objective | Files/modules | Evidence and next action |
|---|---|---|---|---|
| [x] | DISC-01 | Establish repository shape and execution paths | `backend/`, `frontend/`, `evaluation/`, `tests/` | Source inspection completed. Git metadata is unavailable in the supplied tree. |
| [x] | DOC-01 | Create architecture map | `docs/PROJECT_ARCHITECTURE_MAP.md` | Created from source inspection; live claims marked unverified. |
| [x] | DOC-02 | Create persistent checklist and issue log | This file and `docs/KNOWN_ISSUES_AND_DECISIONS.md` | Created and will be updated after each repair. |
| [x] | EVAL-01 | Repair provider-router regression fixture | `tests/unit/test_provider_router.py` | Focused suite: 8 passed. |
| [x] | EVAL-02 | Restore metric API compatibility and evaluator import | `evaluation/metrics/retrieval_metrics.py`, `evaluation/evaluators/retrieval_evaluator.py` | Metric suite: 12 passed; combined focused run: 20 passed; py_compile passed. |
| [x] | STATIC-01 | Run complete Python syntax/import checks | `backend/`, `evaluation/`, `tests/` | `python -m compileall -q backend evaluation tests` completed successfully. |
| [x] | FRONT-01 | Verify TypeScript/Vite build | `frontend/` | `npm run build` passed; Vite emitted production assets. |
| [x] | TEST-01 | Run complete unit/security suite | `tests/`, `evaluation/` | Project `.venv`: `python -m pytest -q`: 51 passed. |
| [x] | PROVIDER-01 | Verify Ollama reachability and actual model | `scripts/provider_smoke.py`, Ollama | Live smoke passed with configured `qwen3:4b`; nonempty response, 24.17s latency. |
| [!] | PROVIDER-02 | Verify Groq discovery, validation, activation, and generation | Groq credentials, frontend/backend | Requires user-provided key and network access; never record the key. |
| [ ] | DATA-01 | Validate a real annotated evaluation corpus | `evaluation/datasets/` | Existing files need audit against source-document IDs and references. |
| [~] | EVAL-03 | Run offline and provider-specific reports | `evaluation/run_eval.py`, `evaluation/regenerate_report.py` | Synthetic self-test and saved-result regeneration passed; real provider comparison needs Groq and annotated data. |
| [x] | SESSION-01 | Evaluate frontend chat sessions | `evaluation/session_report.py` | Read-only report passed against 20 stored sessions; quality remains partial without persisted retrieval IDs/references. |
| [~] | E2E-01 | Verify upload -> retrieval -> answer -> provider switch | `frontend/e2e/`, Playwright | Deterministic login/rendering E2E passed 2/2; live upload/provider switch remains service-gated. |
| [~] | DOC-03 | Complete verified runbook and dataset requirements | `docs/VERIFIED_RUN_AND_EVALUATION_GUIDE.md`, `docs/EVALUATION_DATASET_REQUIREMENTS.md` | Initial documents created; baseline commands and blockers recorded. |
| [x] | DOC-04 | Create complete end-to-end handbook | `docs/COMPLETE_END_TO_END_RUN_AND_EVALUATION_HANDBOOK.md` | All 18 handbook sections checked; commands classified by evidence. |
| [x] | DATA-02 | Validate the migrated 250-question dataset | `evaluation/datasets/rag_test_dataset.json` | Both project loaders passed: 250 records, 226 answerable, 24 unanswerable, no schema errors. |
| [x] | DATA-03 | Install unified ZIP corpus and modality benchmarks | `evaluation/corpus/`, `evaluation/datasets/ocr/`, `evaluation/datasets/audio/` | Migration completed with timestamped backup; 20 PDFs, 9 DOCX, 23 images, 12 audio clips. OCR/audio references remain unverified. |
| [x] | DEP-01 | Repair project-local Python environment | `.venv`, `backend/requirements.txt` | `.venv` contains `cryptography`; `python -m backend.verify_backend` passed. System Python remains incomplete. |
| [x] | DOC-05 | Produce final execution report | `docs/FINAL_EXECUTION_REPORT.md` | Created from observed commands and artifacts; live Groq remains blocked by missing credential. |