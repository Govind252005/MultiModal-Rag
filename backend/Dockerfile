# ---- Backend (FastAPI + ML pipelines) ----
FROM python:3.11-slim

# System deps: Tesseract OCR (+ Hindi), FFmpeg (audio), Poppler (pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-hin ffmpeg poppler-utils curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU PyTorch (Docker image is CPU by default; see DEPLOYMENT.md for GPU).
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# brief §38: run as a non-root user. storage/ and data/ must stay
# writable by this user — created and chowned here rather than left for
# a bind mount to sort out, so the container works even with no volumes
# attached (e.g. a quick local test run). Also redirect the HuggingFace
# cache to a path this user can actually write to — /root/.cache is no
# longer reachable once we're not root, and docker-compose.yml's volume
# mount is updated to match this path.
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/storage /app/data /app/hf_cache \
    && chown -R appuser:appuser /app
ENV HF_HOME=/app/hf_cache
USER appuser

# Tesseract lives on PATH inside the container.
ENV TESSERACT_CMD=tesseract
ENV OLLAMA_HOST=http://ollama:11434
ENV WARMUP_ON_STARTUP=1

EXPOSE 8000

# brief §38: container-level health check, independent of whatever
# orchestrator-level check (k8s readinessProbe, compose healthcheck) is
# layered on top — this one has no external dependencies (§56/§57's
# liveness, not readiness) so it can't itself become a source of
# flapping restarts if Ollama/Redis happen to be slow.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
