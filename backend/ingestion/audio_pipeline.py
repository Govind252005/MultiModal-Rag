"""
Audio ingestion -> transcript records with TIMECODES.  MULTILINGUAL.

faster-whisper auto-detects the spoken language (90+ languages) and
transcribes offline with per-segment timestamps. Set config.WHISPER_LANGUAGE
to force a language, or config.WHISPER_TASK="translate" to get English out of
any language. Segments are grouped into ~20s windows so each retrievable
chunk maps to a clickable timecode.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend import config

# Compatibility fix: Modern PyAV (av >= 12) removed the 'metadata_errors' parameter in av.open.
# faster-whisper passes metadata_errors="ignore", which causes TypeError on modern PyAV.
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        try:
            return _orig_av_open(*args, **kwargs)
        except TypeError as e:
            if "metadata_errors" in str(e):
                kwargs.pop("metadata_errors", None)
                return _orig_av_open(*args, **kwargs)
            raise

    av.open = _safe_av_open
except Exception:
    pass

_whisper = None
_whisper_lock = threading.Lock()  # brief §100 — same double-checked-locking fix as embeddings.py


def _load_whisper():
    global _whisper
    if _whisper is None:
        with _whisper_lock:
            if _whisper is None:
                import os
                from faster_whisper import WhisperModel

                model_name = config.WHISPER_MODEL or "medium"
                device = config.DEVICE
                compute_type = config.WHISPER_COMPUTE_TYPE

                def _instantiate(m_name, dev, c_type):
                    try:
                        return WhisperModel(m_name, device=dev, compute_type=c_type)
                    except Exception as exc:
                        exc_msg = str(exc)
                        # If blocked by HF_HUB_OFFLINE or cache missing, enable online snapshot download
                        if "HF_HUB_OFFLINE" in exc_msg or "cached snapshot" in exc_msg or "offline" in exc_msg.lower():
                            print(f"[audio] Whisper '{m_name}' not in local HF cache. Temporarily enabling download...")
                            try:
                                import huggingface_hub.constants
                                huggingface_hub.constants.HF_HUB_OFFLINE = False
                            except Exception:
                                pass
                            orig_offline = os.environ.get("HF_HUB_OFFLINE")
                            orig_tf_offline = os.environ.get("TRANSFORMERS_OFFLINE")
                            try:
                                os.environ["HF_HUB_OFFLINE"] = "0"
                                os.environ["TRANSFORMERS_OFFLINE"] = "0"
                                return WhisperModel(m_name, device=dev, compute_type=c_type)
                            finally:
                                if orig_offline is not None:
                                    os.environ["HF_HUB_OFFLINE"] = orig_offline
                                else:
                                    os.environ.pop("HF_HUB_OFFLINE", None)
                                if orig_tf_offline is not None:
                                    os.environ["TRANSFORMERS_OFFLINE"] = orig_tf_offline
                                else:
                                    os.environ.pop("TRANSFORMERS_OFFLINE", None)
                        raise

                # Candidate models to try (prefer cached base/small if medium takes long)
                candidates = [model_name]
                for fb in ("base", "small", "tiny"):
                    if fb not in candidates:
                        candidates.append(fb)

                last_exc = None
                for candidate in candidates:
                    try:
                        print(f"[audio] loading Whisper '{candidate}' ({compute_type}) on {device} ...")
                        _whisper = _instantiate(candidate, device, compute_type)
                        print(f"[audio] Whisper '{candidate}' successfully loaded on {device}.")
                        break
                    except Exception as exc:
                        print(f"[audio] Failed to load Whisper '{candidate}' on {device}: {exc}")
                        last_exc = exc
                        if device == "cuda":
                            try:
                                print(f"[audio] Falling back to CPU (int8) for Whisper '{candidate}'...")
                                _whisper = _instantiate(candidate, "cpu", "int8")
                                print(f"[audio] Whisper '{candidate}' successfully loaded on CPU.")
                                break
                            except Exception as cpu_exc:
                                print(f"[audio] CPU fallback also failed for '{candidate}': {cpu_exc}")
                                last_exc = cpu_exc

                if _whisper is None:
                    raise ValueError(
                        f"Whisper model could not be loaded. Please ensure internet access is available "
                        f"for the initial one-time model download. Detail: {last_exc}"
                    )
    return _whisper


def _fmt_ts(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


def transcribe(path: str) -> Tuple[List[Dict[str, Any]], str]:
    """Return (segments, detected_language). segments: [{start,end,text}]."""
    model = _load_whisper()
    segments, info = model.transcribe(
        path,
        vad_filter=config.WHISPER_VAD_FILTER,
        beam_size=config.WHISPER_BEAM_SIZE,
        language=config.WHISPER_LANGUAGE or None,
        task=config.WHISPER_TASK,
        condition_on_previous_text=config.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
        initial_prompt=config.WHISPER_INITIAL_PROMPT or None,
        temperature=0.0,
    )
    # brief §32: reject before doing the (expensive) transcription work.
    # faster-whisper probes the file's duration up front as part of
    # `info` — available immediately, before the lazy `segments` generator
    # is consumed — so this check costs nothing extra.
    duration = getattr(info, "duration", None)
    if duration is not None and duration > config.MAX_AUDIO_DURATION_SECONDS:
        raise ValueError(
            f"Audio duration {duration:.0f}s exceeds the configured limit of "
            f"{config.MAX_AUDIO_DURATION_SECONDS}s (MAX_AUDIO_DURATION_SECONDS)."
        )
    segs = [
        {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
        for s in segments
        if any(c.isalnum() for c in s.text)
    ]
    lang = getattr(info, "language", "") or ""

    # If VAD filter was active and produced no speech, retry without VAD
    if not segs and config.WHISPER_VAD_FILTER:
        try:
            segments_no_vad, info_no_vad = model.transcribe(
                path,
                vad_filter=False,
                beam_size=config.WHISPER_BEAM_SIZE,
                language=config.WHISPER_LANGUAGE or None,
                task=config.WHISPER_TASK,
                condition_on_previous_text=config.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
                initial_prompt=config.WHISPER_INITIAL_PROMPT or None,
                temperature=0.0,
            )
            segs = [
                {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
                for s in segments_no_vad
                if any(c.isalnum() for c in s.text)
            ]
            if not lang:
                lang = getattr(info_no_vad, "language", "") or ""
        except Exception:
            pass

    return segs, lang


def parse_audio(path: str) -> List[Dict[str, Any]]:
    file = Path(path).name
    segments, lang = transcribe(path)

    records: List[Dict[str, Any]] = []
    if not segments:
        return records

    win_start = segments[0]["start"]
    win_text: List[str] = []
    win_end = win_start

    def _flush(start, end, parts):
        text = " ".join(parts).strip()
        if not text:
            return
        records.append({
            "target": "text", "text": text,
            "metadata": {
                "file": file, "modality": "audio", "source_type": "transcript",
                "start": round(start, 2), "end": round(end, 2),
                "timestamp": _fmt_ts(start), "language": lang,
            },
        })

    for seg in segments:
        if seg["end"] - win_start > config.AUDIO_CHUNK_SECONDS and win_text:
            _flush(win_start, win_end, win_text)
            win_start = seg["start"]
            win_text = []
        win_text.append(seg["text"])
        win_end = seg["end"]

    _flush(win_start, win_end, win_text)
    return records
