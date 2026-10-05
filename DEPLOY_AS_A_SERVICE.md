# Deploy as a Service — All-in-One Image (Docker + Kubernetes)

This guide runs the whole project as **one self-contained image** that bundles
the FastAPI backend, the compiled React UI, every ML model weight, **and** the
Ollama server with the Qwen LLM baked in. You get a container that runs fully
offline on a single port — `docker run` it, or deploy it to Kubernetes "as a
service".

> Everything here is **additive**. The retrieval / embedding / rerank pipeline
> and all `config` defaults are untouched. These files only *package and deploy*
> the app: `Dockerfile.allinone`, `docker/prefetch_models.py`,
> `docker/entrypoint-allinone.sh`, and `k8s/multimodal-rag.yaml`.

> **Which guide do I want?**
> - **This guide** — one big image, zero external services, ships anywhere. Best
>   for air-gapped / offline installs and simple "one thing to deploy" ops.
> - **`DEPLOYMENT_GUIDE.md`** — free public hosting (Oracle A1 + Cloudflare) and
>   the lean multi-container `docker-compose.yml` (separate Ollama / backend /
>   frontend). Best for cost-free always-on hosting.

---

## 0. What's in the image (and the trade-off)

| Baked in (offline-ready) | Notes |
|--------------------------|-------|
| FastAPI backend + retrieval pipeline | unchanged from source |
| Compiled React UI | served by the backend on the same port |
| PyTorch (CPU) + all Python ML libs | swap to a CUDA wheel for GPU (§7) |
| HF weights: MiniLM, CLIP, BLIP, cross-encoder | via `docker/prefetch_models.py` |
| Whisper (faster-whisper, int8) + PaddleOCR | pre-downloaded at build |
| **Ollama server + Qwen `qwen3:8b`** | pulled at build, stored in the image |

The cost of "runs anywhere, fully offline" is **size** — the image is well over
10 GB. That's expected. For a lean split-service setup, use `docker-compose.yml`
instead.

---

## 1. Build the image

Build from the **project root** (the Dockerfile copies `backend/`, `frontend/`,
and `docker/`):

```bash
docker build -f Dockerfile.allinone -t multimodal-rag:allinone .
```

What happens during the build:

1. **Frontend stage** (`node:20-alpine`) runs `npm install` + `npm run build`.
2. **Runtime stage** (`python:3.11-slim`) installs OS deps (tesseract, ffmpeg,
   poppler, OpenCV libs), installs Ollama, installs CPU PyTorch + `requirements.txt`.
3. Copies `backend/` → `/app` and the built UI → `/frontend/dist`.
4. Runs `prefetch_models.py` to download every HF / Whisper / PaddleOCR weight.
5. Starts Ollama briefly and `ollama pull`s the Qwen model into the image.

> The build needs network access (to fetch models). The **result** does not.
> The build can take a while and needs plenty of disk (tens of GB free).

To also bake the optional ColBERT reranker, add `--build-arg` isn't enough —
set the env in the prefetch step by editing the Dockerfile, or accept that
ColBERT (opt-in) downloads on first use. To pin a different LLM:

```bash
docker build -f Dockerfile.allinone \
  --build-arg LLM_MODEL=qwen3:8b \
  -t multimodal-rag:allinone .
```

(Also set `LLM_MODEL` at runtime to match — see below.)

---

## 2. Run with Docker

```bash
docker run -d --name multimodal-rag \
  -p 8000:8000 \
  -v rag-data:/data \
  multimodal-rag:allinone
```

Then open <http://localhost:8000>. The entrypoint starts Ollama, waits for it,
confirms the Qwen model is present, and launches the backend (which also serves
the UI) on port 8000.

- `-v rag-data:/data` persists **all** writable state — the Chroma vector DB,
  uploaded files, sessions, `users.json`, and the secret key — via
  `RAG_DATA_HOME=/data`. Drop it and data is lost when the container is removed.
- First boot is slow: models warm up (`WARMUP_ON_STARTUP=1`). The container's
  `HEALTHCHECK` has a 180s start-period; wait for `healthy` in `docker ps`.

**Do NOT** mount a volume over `/opt/models` (or `/opt/models/ollama`). That's
where the baked weights and Qwen model live — a volume there hides them and the
app will think the model is "missing" (the entrypoint would then try to re-pull,
which fails offline).

Useful env overrides (`-e NAME=value`):

| Env | Default | Purpose |
|-----|---------|---------|
| `RAG_DATA_HOME` | `/data` | where writable data lives (keep it on the mount) |
| `RAG_PORT` | `8000` | listen port inside the container |
| `LLM_MODEL` | `qwen3:8b` | must match what was baked in |
| `WARMUP_ON_STARTUP` | `1` | set `0` for a faster boot, slower first query |
| `OCR_ENGINE` | `paddleocr` | OCR backend |

Watch logs / check health:

```bash
docker logs -f multimodal-rag
curl -sf http://localhost:8000/api/health
```

### 2a. Compose variant (same image, one service)

If you prefer compose but still want the single all-in-one image, add a service
alongside the existing `docker-compose.yml` (which is the *multi-container*
setup). A minimal standalone file:

```yaml
# docker-compose.allinone.yml
services:
  rag:
    build:
      context: .
      dockerfile: Dockerfile.allinone
    image: multimodal-rag:allinone
    ports:
      - "8000:8000"
    volumes:
      - rag-data:/data
    restart: unless-stopped
volumes:
  rag-data:
```

```bash
docker compose -f docker-compose.allinone.yml up -d
```

---

## 3. Push to a registry

Kubernetes nodes pull the image from a registry, so tag and push it:

```bash
# example: GitHub Container Registry (any registry works)
docker tag multimodal-rag:allinone ghcr.io/<you>/multimodal-rag:allinone
docker push ghcr.io/<you>/multimodal-rag:allinone
```

> The image is large (>10 GB). The first push and the first pull on each node
> take a while. For air-gapped clusters, `docker save`/`docker load` the tarball
> onto the nodes instead of using a registry.

If your registry is private, create a pull secret and reference it:

```bash
kubectl -n multimodal-rag create secret docker-registry regcred \
  --docker-server=ghcr.io --docker-username=<you> --docker-password=<token>
```

Then add under the pod spec in `k8s/multimodal-rag.yaml`:

```yaml
      imagePullSecrets:
        - name: regcred
```

---

## 4. Deploy to Kubernetes

The manifests live in `k8s/multimodal-rag.yaml` — one file with a Namespace,
PVC, Deployment, Service, and Ingress.

**Before applying, edit these placeholders:**

1. `image:` → your pushed reference (e.g. `ghcr.io/<you>/multimodal-rag:allinone`).
2. Ingress `host:` → your hostname (e.g. `rag.example.com`).
3. `ingressClassName` / annotations → match your ingress controller.
4. PVC `storage:` size and the Deployment `resources` → your cluster's capacity.

Apply:

```bash
kubectl apply -f k8s/multimodal-rag.yaml
kubectl -n multimodal-rag get pods -w
```

The pod passes through `startupProbe` first (up to ~10 min for model warm-up),
then becomes Ready. Check:

```bash
kubectl -n multimodal-rag logs deploy/multimodal-rag -f
kubectl -n multimodal-rag get ingress
```

No ingress controller? Port-forward to test:

```bash
kubectl -n multimodal-rag port-forward svc/multimodal-rag 8000:80
# open http://localhost:8000
```

### What the manifests do

- **PVC `rag-data`** (`ReadWriteOnce`, 20Gi default) mounted at `/data` — the
  single home for all writable data.
- **Deployment** — `replicas: 1`, `strategy: Recreate`, container port 8000,
  probes on `/api/health` (a long-tolerance startup probe plus readiness and
  liveness), CPU/memory requests+limits. It mounts **only** `/data`; it never
  mounts over the baked model dir.
- **Service** — `ClusterIP` on port 80 → container 8000.
- **Ingress** — routes your host to the service with
  `proxy-body-size: 200m` and generous timeouts so large PDF/audio uploads and
  long-running answers aren't cut off.

---

## 5. First-run behavior

On the very first start (fresh `/data`):

1. Ollama starts and the entrypoint confirms the baked Qwen model is present.
2. The backend boots; with `WARMUP_ON_STARTUP=1` it loads the embedding/CLIP/
   rerank models into memory. This is the slow part — be patient.
3. `/api/health` starts returning healthy; the probe/health-check flips to ready.
4. The app creates its storage layout under `/data` (chroma dir, sessions,
   `users.json`, `secret.key`). Because that's on the PVC/volume, it survives
   restarts and re-creates.
5. Open the UI, register the first account, and start ingesting.

Everything after that runs offline — no model downloads at query time.

---

## 6. Scaling caveats (read this)

**Run exactly one replica.** The vector store (ChromaDB) is **embedded** and
writes to a local directory on the PVC. It is not multi-writer safe. Two pods
against the same `/data` will corrupt the index. That's why the Deployment pins
`replicas: 1` and uses `strategy: Recreate` (so a rollout never briefly runs two
pods on the same volume).

To scale **horizontally**, you'd need to move Chroma out of the pod into an
external Chroma server (or another vector DB) that all replicas share — which
means changing the retrieval layer. That is **out of scope** here and would
break the "additive, pipeline-untouched" guarantee. For now, scale **vertically**
(more CPU/RAM, or a GPU) instead.

Also: `ReadWriteOnce` PVCs bind to one node. On multi-node clusters the pod is
pinned to wherever the volume attaches; that's fine for a single replica.

---

## 7. GPU (optional)

The default image is CPU-only and portable. For GPU acceleration:

1. In `Dockerfile.allinone`, swap the CPU torch install for a CUDA wheel, e.g.
   `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121`.
2. Rebuild and push.
3. Ensure the cluster has the NVIDIA device plugin and a GPU node pool.
4. In `k8s/multimodal-rag.yaml`, under `resources.limits` add:
   ```yaml
   nvidia.com/gpu: "1"
   ```
   and add a `nodeSelector`/`tolerations` for your GPU nodes as needed.

Ollama auto-detects the GPU inside the container; the ML models pick it up via
torch. Nothing in the app code changes.

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Pod stuck `0/1`, restarts after a few minutes | Model warm-up hadn't finished. The `startupProbe` allows ~10 min; raise its `failureThreshold` if your node is slow, or set `WARMUP_ON_STARTUP=0`. |
| `Answer says "LLM unavailable"` | Ollama or the model isn't ready. `kubectl exec` in and run `ollama list`; confirm the entrypoint logged "model present". Don't mount over `/opt/models`. |
| Model re-pull attempts / fails at boot | A volume was mounted over `/opt/models` or `/root/.ollama` and hid the baked model. Remove that mount — only `/data` should be a volume. |
| Uploads fail / 413 for large PDFs or audio | Ingress body size too small. Confirm `nginx.ingress.kubernetes.io/proxy-body-size: "200m"` (or your controller's equivalent). |
| Long answers time out at the proxy | Raise `proxy-read-timeout`/`proxy-send-timeout` on the Ingress. |
| `ImagePullBackOff` | Wrong image ref or missing pull secret. Fix `image:` and add `imagePullSecrets` (§3). Remember the image is huge — the first pull is slow, not failed. |
| Data lost after restart | You didn't persist `/data`. Use the PVC (k8s) or a named volume (docker). |
| Out-of-memory / OOMKilled | 7B LLM + models on CPU is heavy. Raise memory limits, use a smaller LLM, or move to a GPU node. |
| Two pods briefly ran and Chroma looks corrupt | You scaled >1 or used a rolling update. Keep `replicas: 1` + `strategy: Recreate`. |

Handy commands:

```bash
kubectl -n multimodal-rag describe pod -l app=multimodal-rag   # events / probe failures
kubectl -n multimodal-rag exec -it deploy/multimodal-rag -- ollama list
kubectl -n multimodal-rag exec -it deploy/multimodal-rag -- ls -la /data
```

---

## 9. Files added for "as a service" (all additive)

| File | Purpose |
|------|---------|
| `Dockerfile.allinone` | One image: frontend build → Python runtime with Ollama, all ML weights, and Qwen baked in. |
| `docker/prefetch_models.py` | Build-time download of every HF / Whisper / PaddleOCR weight, using the app's own `config` for model names. |
| `docker/entrypoint-allinone.sh` | Starts Ollama, waits for it, verifies the model, then runs the backend (API + UI) on one port. |
| `k8s/multimodal-rag.yaml` | Namespace, PVC, single-replica Deployment (Recreate, `/api/health` probes), ClusterIP Service, Ingress (large-upload annotation). |
| `DEPLOY_AS_A_SERVICE.md` | This guide. |

None of these touch `retrieval/search.py` or the retrieval / embedding / rerank
logic — the pipeline is identical to the source app. They only package and
deploy it.




