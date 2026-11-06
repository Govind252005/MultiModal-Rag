"""
GeminiProvider — Google Gemini via the google-genai SDK.

The user's API key is fetched from keystore at call time so it is never
cached in memory longer than a single request.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from backend import config
from backend.generation.providers.base import BaseProvider


class GeminiProvider(BaseProvider):
    name = "gemini"

    DEFAULT_MODELS = [
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (Next-Gen Multimodal)", "context_window": 1048576},
        {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "context_window": 1048576},
        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "context_window": 1048576},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro (Complex Reasoning)", "context_window": 2097152},
        {"id": "gemini-flash-latest", "name": "Gemini Flash Latest", "context_window": 1048576},
    ]

    def _client(self, key: str):
        from google import genai  # type: ignore
        return genai.Client(api_key=key)

    def _get_key(self, user_id: Optional[str]) -> str:
        if not user_id:
            raise ValueError("Gemini requires an API key. Set one in the provider panel.")
        from backend import keystore
        key = keystore.get_key(user_id, "gemini")
        if not key:
            raise ValueError("No Gemini API key found for this account.")
        return key

    def get_model_list(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            key = self._get_key(user_id)
        except Exception:
            return list(self.DEFAULT_MODELS)

        try:
            client = self._client(key)
            models = []
            for m in client.models.list():
                mid = getattr(m, "name", "") or ""
                clean_id = mid.split("/")[-1] if "/" in mid else mid
                if "gemini" in clean_id.lower() and not any(
                    x in clean_id.lower() for x in ("embedding", "aqa", "vision-preview")
                ):
                    display_name = getattr(m, "display_name", clean_id) or clean_id
                    models.append({"id": clean_id, "name": display_name})
            if models:
                def _sort_key(item: dict) -> int:
                    mid = item["id"]
                    if "2.0-flash" in mid:
                        return 0
                    if "1.5-flash" in mid:
                        return 1
                    if "1.5-pro" in mid:
                        return 2
                    return 3
                models.sort(key=_sort_key)
                return models
        except Exception:
            pass
        return list(self.DEFAULT_MODELS)

    def _build_contents(
        self,
        user: str,
        history: Optional[List[dict]] = None,
        image_paths: Optional[List[str]] = None,
    ):
        from google.genai import types  # type: ignore

        contents: List = []
        for turn in history or []:
            role = "user" if turn.get("role") == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))

        user_parts = [types.Part(text=user)]
        for img_path in (image_paths or []):
            try:
                path = Path(img_path)
                if path.exists():
                    from PIL import Image as PILImage  # type: ignore
                    import io
                    pil = PILImage.open(path).convert("RGB")
                    buf = io.BytesIO()
                    pil.save(buf, format="JPEG", quality=85)
                    user_parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=buf.getvalue(),
                            )
                        )
                    )
            except Exception as exc:
                print(f"[gemini] could not attach image {img_path}: {exc}")

        contents.append(types.Content(role="user", parts=user_parts))
        return contents

    def generate_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> str:
        from google.genai import types  # type: ignore

        key = self._get_key(user_id)
        client = self._client(key)
        contents = self._build_contents(user, history, image_paths)
        target_model = model or config.GEMINI_MODEL

        response = client.models.generate_content(
            model=target_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=config.CLOUD_TEMPERATURE,
                max_output_tokens=config.CLOUD_MAX_TOKENS,
            ),
        )
        return response.text or ""

    def stream_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        from google.genai import types  # type: ignore

        key = self._get_key(user_id)
        client = self._client(key)
        contents = self._build_contents(user, history, image_paths)
        target_model = model or config.GEMINI_MODEL

        start = time.perf_counter()
        first_token_at = None
        parts: List[str] = []

        response = client.models.generate_content_stream(
            model=target_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=config.CLOUD_TEMPERATURE,
                max_output_tokens=config.CLOUD_MAX_TOKENS,
            ),
        )

        for chunk in response:
            text = getattr(chunk, "text", None)
            if text:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                parts.append(text)
                yield {"delta": text}

        end = time.perf_counter()
        ttft_ms = (first_token_at - start) * 1000 if first_token_at else None
        gen_ms = (end - first_token_at) * 1000 if first_token_at else None
        yield {
            "done": True,
            "text": "".join(parts),
            "metrics": {
                "provider": "gemini",
                "model": target_model,
                "streaming_enabled": True,
                "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                "generation_time_ms": round(gen_ms, 1) if gen_ms is not None else None,
                "total_llm_time_ms": round((end - start) * 1000, 1),
            },
        }

    def validate_api_key(self, key: str) -> bool:
        try:
            from google import genai  # type: ignore
            client = genai.Client(api_key=key)
            for _ in client.models.list():
                break
            return True
        except Exception:
            return False

    def supports_images(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True
