# Multimodal RAG Quality Audit

Date: 2026-10-02

## Scope

This audit preserves the historical evaluation reports and applies only
evaluation correctness, reporting, and regression-test fixes. No gold answers,
relevance labels, or historical report files were changed.

## Verified Findings

| Area | Evidence | Fix/status |
| --- | --- | --- |
| ROC/PR plots | Retrieval metrics stored curve data under `roc_pr_details`, but the graph generator passed the parent retrieval object. Graphs 03 and 04 were therefore skipped. | Fixed in `evaluation/reporting/graph_generator.py`. |
| Duplicate ranking results | Ranking functions counted repeated chunk IDs as separate ranks. | Fixed with stable ID de-duplication in `evaluation/metrics/retrieval_metrics.py`. |
| ROC ties | Curve points were added one candidate at a time, making tied-score AUC depend on input order. | Fixed by grouping equal scores before curve points. |
| Aggregate alignment | MRR/MAP silently used `zip()` and truncated mismatched query arrays. | Fixed with explicit equal-length validation. |
| Citation presence | The evaluator treated every citation returned by the backend as cited, even when the answer had no inline `[n]` marker. | Fixed to resolve inline markers against the returned citation map. |
| Abstention reporting | `abstention_accuracy` only measured correct rejection of unanswerable questions and did not expose false abstentions or precision/recall. | Added explicit abstention precision, recall, correct rejection, false-abstention rate, and overall accuracy. |
| Offline self-test | The answer judge attempted a Hugging Face download during self-test. | Fixed to use cached embedding models only, with deterministic fallback. OCR/ASR are explicitly skipped in self-test because they are external heavyweight engines. |
| Ablation latency | `run_all.py` uses synthetic/scaled retrieval lists for non-B5 ablations and passes no measured duration, so B4' latency cannot be truthfully reported. | Remains unresolved and is marked as a limitation; it requires executing each retrieval configuration with instrumentation. |
| Relevance labels | The dataset marks chunk annotations as candidate/human-review-required, and the runner adds same-file chunks as relevant when document IDs are present. | Remains a benchmark annotation limitation; no labels were changed. Chunk-level publication claims require reviewed annotations. |
| Stage timings | The runner previously reported fixed percentages of end-to-end latency as dense/BM25/CLIP/RRF/reranker timings. | Fixed the evaluator to use backend-emitted retrieval/generation timings when available and otherwise report only observed total latency. Uninstrumented sub-stages remain unavailable rather than fabricated. |

## Validation Results

- Python tests: **58 passed**
- Python compilation: **PASS**
- Frontend production build: **PASS** using `npm.cmd run build`
- Evaluation self-test: **PASS**, 10/10 synthetic queries, all 12 pipeline stages completed or explicitly skipped as expected
- Fresh 250-question provider runs: not launched in this audit because Ollama is a long-running local job and Groq requires the configured user API key. Historical reports remain the reference measurements.

## Historical Baseline

The preserved reports are:

- `reports/evaluation/ollama/2026-10-02_114157`
- `reports/evaluation/groq/2026-10-02_134011`

The Ollama baseline recorded 250/250 query success, Precision@5 `0.3319`,
Recall@5 `0.2950`, MRR `0.7145`, MAP `0.2390`, ROC-AUC `0.7310`, PR-AUC
`0.5541`, faithfulness `0.6811`, and source citation precision `0.3319`.
These values are historical and are not presented as post-fix improvements.

## New Report Artifacts

The missing plots were regenerated for the preserved Ollama report after the
plotting fix:

- `reports/evaluation/ollama/2026-10-02_114157/graphs/03_roc_curve.png`
- `reports/evaluation/ollama/2026-10-02_114157/graphs/04_pr_curve.png`

The regenerated plots use the existing recorded `roc_pr_details` values and do
not rerun the corpus evaluation.

## Exact Validation Commands

```powershell
Set-Location 'C:\Users\Govind\Downloads\files\minor-main'
$py = 'c:/Users/Govind/Downloads/files/minor-main/.venv/Scripts/python.exe'

& $py -m pytest -q
& $py -m compileall -q backend evaluation tests
Set-Location frontend
npm.cmd run build
Set-Location ..
& $py evaluation/run_eval.py --self-test
```

## Exact Live Evaluation Commands

Start the backend in a separate PowerShell window:

```powershell
Set-Location 'C:\Users\Govind\Downloads\files\minor-main'
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PROVIDER_FAILOVER_TO_LOCAL = '0'
& 'c:/Users/Govind/Downloads/files/minor-main/.venv/Scripts/python.exe' -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

After logging in and setting `$token` for the account that owns the sessions:

```powershell
Set-Location 'C:\Users\Govind\Downloads\files\minor-main'
$py = 'c:/Users/Govind/Downloads/files/minor-main/.venv/Scripts/python.exe'

& $py evaluation/run_eval.py --provider ollama --all `
  --dataset evaluation/datasets/rag_test_dataset.json `
  --session-id eval-ollama-20261002-v4 `
  --base-url http://localhost:8000 --token $token --top-k 5

& $py evaluation/run_eval.py --provider groq --all `
  --dataset evaluation/datasets/rag_test_dataset.json `
  --session-id eval-groq-20261002-v4 `
  --base-url http://localhost:8000 --token $token --top-k 5

& $py evaluation/run_eval.py --provider both --all `
  --dataset evaluation/datasets/rag_test_dataset.json `
  --session-id eval-ollama-20261002-v4 `
  --base-url http://localhost:8000 --token $token --top-k 5
```

The Groq key must be configured in the backend provider settings for the
logged-in user before the Groq command. Keep Ollama and Groq sessions separate.
