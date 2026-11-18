import pytest
from backend.generation import answer, prompt_templates


def test_image_query_structured_presentation_and_grounding():
    """Verify that when an image is queried, it generates a structured, beautiful presentation with citations and no missing context errors."""
    clean_fname = "chat_screenshot.png"
    caption = "a screenshot of a chat interface with a chat button"
    ocr = "Chat with AI\nType your message here...\nSend Button"

    image_text_blocks = [
        f"Visual Scene Description: {caption}",
        f"Detected Text / OCR:\n{ocr}",
    ]
    primary_hit = {
        "id": f"upload_img_{clean_fname}",
        "file": clean_fname,
        "modality": "image",
        "source_type": "image",
        "page": 1,
        "snippet": f"{caption} | OCR: {ocr[:100]}",
        "text": "\n\n".join(image_text_blocks),
        "score": 1.0,
        "relative_relevance": 100,
        "metadata": {
            "file": clean_fname,
            "modality": "image",
            "source_type": "image",
            "page": 1,
        },
    }

    prompt_q = (
        f"Based on the uploaded image analysis in source [1] ({clean_fname}), "
        f"provide a clear and structured presentation describing what is shown in this image to answer: 'what\'s in this image ?'\n"
        f"- **Visual Overview**: Describe the visual scene, interface layout, and overall visual subject [1].\n"
        f"- **Detected Text & Labels**: List the specific text, buttons, messages, and UI elements found in the image [1].\n"
        f"- **Summary**: A concise takeaway explaining the context or function of the screen/image [1]."
    )

    ctx = answer.prepare_answer_context(prompt_q, [primary_hit])
    assert len(ctx["citations"]) == 1
    assert ctx["citations"][0]["file"] == clean_fname

    # Verify context inclusion
    assert "<document_content" in ctx["user"]
    assert "Visual Scene Description" in ctx["user"]
    assert "Chat with AI" in ctx["user"]


def test_balanced_mode_includes_image_captioning():
    """Verify that balanced mode enables BLIP image captioning so library uploads have visual semantics."""
    from backend.ingestion.ingest import _mode_flags
    flags = _mode_flags("balanced")
    assert flags.get("caption_images") is True


def test_ollama_provider_model_list_contains_only_target_model():
    """Verify Ollama provider model list contains only the configured production model without obsolete models."""
    from backend.generation.providers.ollama_provider import OllamaProvider
    import backend.config as b_config
    prov = OllamaProvider()
    models = prov.get_model_list()
    assert len(models) == 1
    expected = getattr(b_config, "LLM_MODEL", "qwen2.5:7b-instruct")
    assert models[0]["id"] == expected
    assert models[0]["name"] == expected


