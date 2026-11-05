"""
Image ingestion -> records for BOTH channels, with STRONG OCR.

Per image we produce:
  1. CLIP image vector  -> IMAGE collection   (visual / text->image search)
  2. OCR text, CHUNKED  -> TEXT collection    (each chunk separately citable)
  3. BLIP caption       -> TEXT collection    (semantic "what is this about")

OCR engine (config.OCR_ENGINE):
  * "paddleocr" : PP-OCRv5   : deep-learning OCR, far more accurate on screenshots/photos,
                  multilingual, GPU-accelerated. Falls back to Tesseract if it
                  can't load.
  * "tesseract" : classic engine with heavy image preprocessing.

Large/text-heavy images are split into several OCR chunks so the answer can
cite the exact part it used, and each chunk shows up (with the image) when you
open its citation.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageOps, ImageFilter

from backend import config
from backend.ingestion.chunker import chunk_text
from backend.ingestion.image_safety import ImageTooLargeError, enforce_image_limits
# Lazy singletons
_blip_processor = None
_blip_model = None
_paddleocr_reader = None
# brief §100: same double-checked-locking fix as embeddings.py/search.py/
# audio_pipeline.py — two concurrent first-requests could otherwise both
# load these (multi-hundred-MB) models at once.
_blip_lock = threading.Lock()
_paddleocr_lock = threading.Lock()


# ------------------------------------------------------------------ captioning
def _load_blip():
    global _blip_processor, _blip_model
    if _blip_model is None:
        with _blip_lock:
            if _blip_model is None:
                from transformers import BlipForConditionalGeneration, BlipProcessor
                print(f"[image] loading BLIP {config.BLIP_CAPTION_MODEL} on {config.DEVICE} ...")
                _blip_processor = BlipProcessor.from_pretrained(config.BLIP_CAPTION_MODEL)
                _blip_model = BlipForConditionalGeneration.from_pretrained(
                    config.BLIP_CAPTION_MODEL).to(config.DEVICE)
    return _blip_processor, _blip_model


def caption_image(image: Image.Image) -> str:
    processor, model = _load_blip()
    inputs = processor(image.convert("RGB"), return_tensors="pt").to(config.DEVICE)
    out = model.generate(**inputs, max_new_tokens=40)
    return processor.decode(out[0], skip_special_tokens=True).strip()


# ------------------------------------------------------------------ OCR
def _upscale(image: Image.Image) -> Image.Image:
    """Upscale small images — the single biggest OCR accuracy win."""
    if image.width < config.OCR_MIN_WIDTH:
        scale = config.OCR_MIN_WIDTH / max(1, image.width)
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.LANCZOS)
    return image


def _load_paddleocr():
    global _paddleocr_reader

    if _paddleocr_reader is None:
        with _paddleocr_lock:
            if _paddleocr_reader is None:
                from paddleocr import PaddleOCR

                _paddleocr_reader = PaddleOCR(
                    lang=config.PADDLEOCR_LANG,
                    device="cpu",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )

    return _paddleocr_reader


def _ocr_paddleocr(image: Image.Image) -> str:
    ocr = _load_paddleocr()

    img = _upscale(image.convert("RGB"))

    result = ocr.predict(np.array(img))

    texts = []

    for page in result:
        if isinstance(page, dict) and "rec_texts" in page:
            texts.extend(
                str(text).strip()
                for text in page["rec_texts"]
                if str(text).strip()
            )

    return "\n".join(texts).strip()


def _ocr_tesseract(image: Image.Image) -> str:
    import pytesseract

    # Always use the configured executable path.
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    img = _upscale(image.convert("L"))
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)

    text = pytesseract.image_to_string(
        img,
        lang=config.OCR_LANG,
        config=config.OCR_CONFIG,
    )

    return " ".join(text.split()).strip()


def ocr_image(image: Image.Image) -> str:
    """
    Extract text using the configured OCR engine.

    PaddleOCR is the primary engine.
    Tesseract is the silent fallback.

    OCR failures never propagate to the ingestion pipeline.
    """

    engine = str(getattr(config, "OCR_ENGINE", "paddleocr")).lower().strip()

    # --------------------------------------------------------------
    # PRIMARY: PaddleOCR
    # --------------------------------------------------------------
    if engine == "paddleocr":
        try:
            text = _ocr_paddleocr(image)

            if text:
                return text

        except Exception:
            # Silent fallback to Tesseract.
            pass

    # --------------------------------------------------------------
    # FALLBACK: Tesseract
    # --------------------------------------------------------------
    try:
        text = _ocr_tesseract(image)

        if text:
            return text

    except Exception:
        # OCR failure should never break document ingestion.
        pass

    return ""


# ------------------------------------------------------------------ ingest
def build_image_records(
    image: "Image.Image",
    file: str,
    media_file: Optional[str] = None,
    page: Optional[int] = None,
    caption_images: bool = True,
) -> List[Dict[str, Any]]:
    """
    Turn a single PIL image into the standard 3-part record set:
      1) CLIP visual vector -> IMAGE collection
      2) OCR text -> TEXT collection
      3) BLIP caption -> TEXT collection (skippable — brief §44, outside MAX_QUALITY)
    """

    if caption_images:
        try:
            caption = caption_image(image)
        except Exception:
            caption = ""
    else:
        caption = ""

    try:
        ocr_text = ocr_image(image)
    except Exception:
        ocr_text = ""

    records: List[Dict[str, Any]] = []

    def _meta(extra: Dict[str, Any]) -> Dict[str, Any]:
        m: Dict[str, Any] = {"file": file, "modality": "image"}
        if media_file:
            m["media_file"] = media_file
        if page is not None:
            m["page"] = page
        m.update(extra)
        return m

    # 1) CLIP visual vector (documents=caption preview)
    records.append({
        "target": "image", "text": caption, "image": image,
        "metadata": _meta({"source_type": "image", "caption": caption}),
    })

    # 2) OCR text -> CHUNKS (each independently citable)
    ocr_chunks = chunk_text(ocr_text, size=config.OCR_CHUNK_WORDS, overlap=20) if ocr_text else []
    for i, ch in enumerate(ocr_chunks):
        if len(ch.strip()) < 3:
            continue
        records.append({
            "target": "text", "text": ch,
            "metadata": _meta({"source_type": "ocr", "chunk": i,
                               "chunk_total": len(ocr_chunks)}),
        })

    # 3) Caption as searchable text
    records.append({
        "target": "text", "text": caption,
        "metadata": _meta({"source_type": "caption"}),
    })
    return records


def parse_image(path: str, caption_images: bool = True) -> List[Dict[str, Any]]:
    file = Path(path).name
    image = enforce_image_limits(Image.open(path).convert("RGB"), context=file)
    return build_image_records(image, file, caption_images=caption_images)
