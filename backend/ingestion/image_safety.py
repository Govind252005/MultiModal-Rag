"""
Shared image safety checks (transformation brief §30). Used by every
ingestion path that opens an image the user (indirectly) controls —
direct image uploads, and images embedded inside PDFs/DOCX files.

Pillow already has its own default decompression-bomb guard
(`Image.MAX_IMAGE_PIXELS`, ~89 megapixels, raising `DecompressionBombError`
above 2x that). This module makes the limit an explicit, app-configured
value instead of relying on PIL's default, and adds a width/height cap on
top of the raw pixel-count cap (a 1x1,000,000 image passes a pixel-count
check but is still an absurd aspect ratio worth rejecting).
"""

from __future__ import annotations

from PIL import Image

from backend import config

# Make our configured limit authoritative rather than relying on
# whatever PIL's own default happens to be.
Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS


class ImageTooLargeError(ValueError):
    pass


def enforce_image_limits(image: Image.Image, context: str = "") -> Image.Image:
    """Raise ImageTooLargeError if the image exceeds configured pixel/
    dimension limits; otherwise return it unchanged (so this can be used
    inline: `image = enforce_image_limits(Image.open(...))`)."""
    w, h = image.size
    if w > config.MAX_IMAGE_WIDTH or h > config.MAX_IMAGE_HEIGHT:
        raise ImageTooLargeError(
            f"Image{f' ({context})' if context else ''} is {w}x{h}, exceeding the "
            f"configured limit of {config.MAX_IMAGE_WIDTH}x{config.MAX_IMAGE_HEIGHT}."
        )
    if w * h > config.MAX_IMAGE_PIXELS:
        raise ImageTooLargeError(
            f"Image{f' ({context})' if context else ''} has {w * h:,} pixels, exceeding "
            f"the configured limit of {config.MAX_IMAGE_PIXELS:,}."
        )
    return image
