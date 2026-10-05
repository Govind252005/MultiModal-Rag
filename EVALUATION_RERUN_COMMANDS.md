# Metrics Evaluation Rerun Commands

These commands target the existing annotated dataset and the existing indexed corpus.
They do not contain or print API keys.

## 1. Open the project

```powershell
Set-Location 'C:\Users\Govind\Downloads\files\minor-main'
$env:PYTHONIOENCODING = 'utf-8'
$py = 'c:/Users/Govind/Downloads/files/minor-main/.venv/Scripts/python.exe'
```

## 2. Verify Ollama

```powershell
ollama list
Invoke-RestMethod 'http://localhost:11434/api/tags' | ConvertTo-Json -Depth 4
```

The configured model is `qwen3:4b`.

## 3. Start the backend in offline model-cache mode

Use a separate PowerShell window and leave it running:

```powershell
Set-Location 'C:\Users\Govind\Downloads\files\minor-main'
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:WARMUP_ON_STARTUP = '1'
$env:PROVIDER_FAILOVER_TO_LOCAL = '0'
& 'c:/Users/Govind/Downloads/files/minor-main/.venv/Scripts/python.exe' -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Verify it:

```powershell
Invoke-RestMethod 'http://localhost:8000/api/health' | ConvertTo-Json -Depth 4
```

## 4. Create a short-lived evaluation token without printing a secret

The existing evaluation session belongs to user id `4835cdde1416`:

```powershell
$token = (& $py -c "from backend.auth import issue_token; print(issue_token('4835cdde1416'))").Trim()
```

If the session ownership changes, replace that user id with the owner of the selected session.

## 5. Run the full Ollama evaluation

```powershell
& $py evaluation/run_eval.py --provider ollama --all --dataset evaluation/datasets/rag_test_dataset.json --session-id unified-metrics-v1-20261001 --base-url http://localhost:8000 --token $token --top-k 5
```

Results are written below `reports/evaluation/ollama/<run-id>/`.

## 6. Run the full Groq evaluation

The Groq key must first be configured for user `4835cdde1416` through the project’s provider settings. Do not paste the key into this file or into shell history.

After the key is configured, keep `$env:PROVIDER_FAILOVER_TO_LOCAL = '0'` in the backend window, restart the backend if needed, then run:

```powershell
& $py evaluation/run_eval.py --provider groq --all --dataset evaluation/datasets/rag_test_dataset.json --session-id unified-metrics-v1-20261001 --base-url http://localhost:8000 --token $token --top-k 5
```

Results are written below `reports/evaluation/groq/<run-id>/`.

## 7. Stop the backend after evaluation

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force }
```

## Dataset and run contract

- Dataset: `evaluation/datasets/rag_test_dataset.json`
- Questions: 250
- Session: `unified-metrics-v1-20261001`
- Top-K: 5
- Ollama model: `qwen3:4b`
- Groq model configured by the backend: `llama-3.3-70b-versatile`
