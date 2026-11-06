"""
Language Intelligence and Query Language Detection Engine (Phase 4.5 & Phase 6.9).
Fast, zero-heavy-dependency language and script identification for English, Hindi,
Hinglish, Arabic, Spanish, French, German, and Chinese.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# Common Hinglish phonetic tokens (Latin script used for Hindi communication)
_HINGLISH_STOPWORDS = {
    "kya", "hai", "hain", "kaise", "samjhao", "chalta", "chal", "raha", "rahe",
    "batao", "karo", "karna", "hoga", "hogi", "liye", "hota", "hoti", "wale",
    "wala", "wali", "kon", "kaun", "konse", "kaunse", "kis", "kisi", "jisme",
    "isme", "usme", "par", "pe", "se", "ko", "aur", "ya", "nahi", "nahin", "mat",
}

# Distinguishing stopwords for major Latin European languages
_SPANISH_WORDS = {"de", "la", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", "con", "no", "una", "su", "al", "es"}
_FRENCH_WORDS = {"de", "la", "le", "et", "les", "des", "en", "un", "du", "une", "que", "est", "pour", "qui", "dans", "ce", "il", "pas"}
_GERMAN_WORDS = {"der", "die", "und", "in", "den", "von", "zu", "das", "mit", "sich", "des", "auf", "für", "ist", "im", "dem", "nicht"}


def detect_script(text: str) -> str:
    """Identify the dominant script of a text string."""
    if not text:
        return "Latin"

    counts = {
        "Devanagari": len(re.findall(r"[\u0900-\u097F]", text)),
        "Arabic": len(re.findall(r"[\u0600-\u06FF\u0750-\u077F]", text)),
        "CJK": len(re.findall(r"[\u4E00-\u9FFF\u3400-\u4DBF]", text)),
        "Latin": len(re.findall(r"[A-Za-z\u00C0-\u024F]", text)),
    }

    dominant_script = max(counts, key=counts.get)
    if counts[dominant_script] == 0:
        return "Latin"
    return dominant_script


def detect_language(text: str) -> Dict[str, Any]:
    """Detect language, script, and confidence from a text passage or query."""
    clean = (text or "").strip()
    if not clean:
        return {"language": "en", "script": "Latin", "confidence": 1.0}

    script = detect_script(clean)

    if script == "Devanagari":
        return {"language": "hi", "script": "Devanagari", "confidence": 0.99}

    if script == "Arabic":
        return {"language": "ar", "script": "Arabic", "confidence": 0.99}

    if script == "CJK":
        return {"language": "zh", "script": "CJK", "confidence": 0.98}

    # Latin script: disambiguate English, Hinglish, Spanish, French, German
    words = [w.strip().lower() for w in re.findall(r"\b\w+\b", clean)]
    total_words = len(words)
    if total_words == 0:
        return {"language": "en", "script": "Latin", "confidence": 1.0}

    # Check for Hinglish
    hinglish_matches = sum(1 for w in words if w in _HINGLISH_STOPWORDS)
    if hinglish_matches >= 2 or (total_words <= 5 and hinglish_matches >= 1):
        return {
            "language": "hinglish",
            "script": "Latin",
            "confidence": min(1.0, 0.7 + (hinglish_matches / total_words)),
        }

    # Check European languages by stopword density
    sp_matches = sum(1 for w in words if w in _SPANISH_WORDS)
    fr_matches = sum(1 for w in words if w in _FRENCH_WORDS)
    de_matches = sum(1 for w in words if w in _GERMAN_WORDS)

    scores = {
        "es": sp_matches,
        "fr": fr_matches,
        "de": de_matches,
    }
    best_lang, best_score = max(scores.items(), key=lambda x: x[1])
    if best_score >= 2 and (best_score / total_words) > 0.15:
        return {
            "language": best_lang,
            "script": "Latin",
            "confidence": min(0.95, 0.6 + (best_score / total_words)),
        }

    return {"language": "en", "script": "Latin", "confidence": 0.95}


def is_cross_lingual(query_lang: str, doc_lang: str) -> bool:
    """Determine if a query-document pair is cross-lingual."""
    q = (query_lang or "en").lower()
    d = (doc_lang or "en").lower()
    if q == d:
        return False
    # Hinglish against Hindi is considered same language family
    if (q == "hinglish" and d == "hi") or (q == "hi" and d == "hinglish"):
        return False
    return True
