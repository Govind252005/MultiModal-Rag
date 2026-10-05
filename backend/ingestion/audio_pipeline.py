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

_whisper = None
_whisper_lock = threading.Lock()  # brief §100 — same double-checked-locking fix as embeddings.py


def _load_whisper():
    global _whisper
    if _whisper is None:
        with _whisper_lock:
            if _whisper is None:
                from faster_whisper import WhisperModel
                print(f"[audio] loading Whisper '{config.WHISPER_MODEL}' "
                      f"({config.WHISPER_COMPUTE_TYPE}) on {config.DEVICE} ...")
                _whisper = WhisperModel(
                    config.WHISPER_MODEL, device=config.DEVICE,
                    compute_type=config.WHISPER_COMPUTE_TYPE)
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
    ]
    lang = getattr(info, "language", "") or ""
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
