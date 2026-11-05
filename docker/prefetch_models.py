#!/usr/bin/env python3
"""
Build-time model prefetch for the all-in-one Docker image.

Runs ONCE during `docker build` so every ML weight the app touches at runtime
is already sitting in the image's Hugging Face /PaddleOCR PP-OCRv5  caches. The result is a
container that needs no network at run time (Ollama model is baked separately in
the Dockerfile).

This script is ADDITIVE. It imports the app's own `config` so the model names it
downloads are exactly the ones the retrieval / ingestion pipeline will load —
nothing here changes retrieval behaviour. If a download fails (e.g. an optional
model), we log and continue rather than break the build; that model will simply
download on first use instead.

Covered:
  * text embeddings   : config.TEXT_EMBED_MODEL   (SentenceTransformer)
  * CLIP cross-modal  : config.CLIP_MODEL         (SentenceTransformer)
  * cross-encoder     : config.RERANK_MODEL       (CrossEncoder)
  * BLIP caption      : config.BLIP_CAPTION_MODEL (transformers)
  * Whisper STT       : config.WHISPER_MODEL      (faster-whisper / CTranslate2)
  * PaddleOCR PP-OCRv5 : config.PADDLEOCR_LANG     (detector + recognizer)

NOT covered on purpose:
  * ColBERT (config.COLBERT_MODEL) is opt-in and heavy; set PREFETCH_COLBERT=1
    to include it.
  * The Ollama LLM (Qwen) — baked by the Dockerfile via `ollama pull`.
"""

import os
import sys
import traceback

# Force CPU during the build; the build host has no GPU and we only need the
# weights on disk, not an accelerator.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

# The backend dir is the import root (same convention as main.py / launcher.py).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../backend")
sys.path.insert(0, "/app")  # in-image location

import config  # noqa: E402  (app config drives which models we fetch)


def _step(name):
    print(f"\n[prefetch] === {name} ===", flush=True)


def _ok(name):
    print(f"[prefetch] OK: {name}", flush=True)


def _fail(name, exc):
    print(f"[prefetch] WARN: {name} failed -> {exc}", flush=True)
    traceback.print_exc()


def prefetch_sentence_transformer(model_name, label):
    _step(f"SentenceTransformer: {label} ({model_name})")
    try:
        from sentence_transformers import SentenceTransformer

        SentenceTransformer(model_name, device="cpu")
        _ok(label)
    except Exception as exc:  # noqa: BLE001
        _fail(label, exc)


def prefetch_cross_encoder(model_name):
    _step(f"CrossEncoder reranker ({model_name})")
    try:
        from sentence_transformers import CrossEncoder

        CrossEncoder(model_name, device="cpu")
        _ok("cross-encoder")
    except Exception as exc:  # noqa: BLE001
        _fail("cross-encoder", exc)


def prefetch_blip(model_name):
    _step(f"BLIP caption model ({model_name})")
    try:
        from transformers import BlipForConditionalGeneration, BlipProcessor

        BlipProcessor.from_pretrained(model_name)
        BlipForConditionalGeneration.from_pretrained(model_name)
        _ok("blip")
    except Exception as exc:  # noqa: BLE001
        _fail("blip", exc)


def prefetch_whisper(model_name, compute_type):
    _step(f"faster-whisper ({model_name}, {compute_type})")
    try:
        from faster_whisper import WhisperModel

        # Instantiating downloads + converts the CTranslate2 weights into cache.
        WhisperModel(model_name, device="cpu", compute_type=compute_type)
        _ok("whisper")
    except Exception as exc:  # noqa: BLE001
        _fail("whisper", exc)


def prefetch_paddleocr(lang):
    _step(f"PaddleOCR PP-OCRv5 ({lang})")

    try:
        from paddleocr import PaddleOCR

        # Instantiating the pipeline downloads the required OCR models
        PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

        _ok("paddleocr")

    except Exception as exc:
        _fail("paddleocr", exc)


def prefetch_colbert(model_name):
    _step(f"ColBERT (opt-in) ({model_name})")
    try:
        from ragatouille import RAGPretrainedModel

        RAGPretrainedModel.from_pretrained(model_name)
        _ok("colbert")
    except Exception as exc:  # noqa: BLE001
        _fail("colbert", exc)


def main():
    print("[prefetch] starting build-time model download", flush=True)
    print(f"[prefetch] HF_HOME={os.getenv('HF_HOME', '(default)')}", flush=True)

    prefetch_sentence_transformer(config.TEXT_EMBED_MODEL, "text-embed")
    prefetch_sentence_transformer(config.CLIP_MODEL, "clip")
    prefetch_cross_encoder(config.RERANK_MODEL)
    prefetch_blip(config.BLIP_CAPTION_MODEL)
    # Whisper on the build host is always CPU -> int8 is the right cache variant.
    prefetch_whisper(config.WHISPER_MODEL, "int8")
    prefetch_paddleocr(config.PADDLEOCR_LANG)

    if os.getenv("PREFETCH_COLBERT", "0") == "1":
        prefetch_colbert(config.COLBERT_MODEL)

    print("\n[prefetch] done. Models are cached in the image.", flush=True)


if __name__ == "__main__":
    main()
