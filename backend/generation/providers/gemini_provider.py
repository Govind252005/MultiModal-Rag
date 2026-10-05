"""
GeminiProvider — Google Gemini via the google-genai SDK.

The user's API key is fetched from keystore at call time so it is never
cached in memory longer than a single request.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from backend import config
from backend.generation.providers.base import BaseProvider

class GeminiProvider(BaseProvider):
    name = "gemini"

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

    def generate_answer(
        self,
        system: str,
        user: str,
        history: Optional[List[dict]] = None,
        user_id: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> str:
        from google.genai import types  # type: ignore

        key = self._get_key(user_id)
        client = self._client(key)

        contents: List = []
        for turn in history or []:
            role = "user" if turn.get("role") == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))

        # Build the final user turn — text + optional inline images
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

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=config.CLOUD_TEMPERATURE,
                max_output_tokens=config.CLOUD_MAX_TOKENS,
            ),
        )
        return response.text or ""

    def validate_api_key(self, key: str) -> bool:
        """
        Validate ONLY that the key authenticates — not that a specific model
        exists. We call models.list(), which requires a valid key but does not
        depend on any particular model being available to the project.
        """
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
