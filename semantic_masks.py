"""Helpers for externally supplied black/white PNG masks.

This is a separate manual workflow: it must not be described as semantic AI.
"""
import io
import numpy as np
from PIL import Image, UnidentifiedImageError


def mask_from_png(image_bytes: bytes, target_size: tuple[int, int], threshold: int = 128) -> np.ndarray:
    """Map white (>=threshold) to True at processing resolution (width, height)."""
    if not image_bytes:
        raise ValueError('Upload a non-empty PNG mask.')
    width, height = target_size
    if width < 1 or height < 1:
        raise ValueError('Target image dimensions must be positive.')
    try:
        with Image.open(io.BytesIO(image_bytes)) as src:
            if src.format != 'PNG':
                raise ValueError('Only PNG masks are supported.')
            src = src.convert('L')
            if src.size != (width, height):
                src = src.resize((width, height), Image.Resampling.NEAREST)
            return np.asarray(src, dtype=np.uint8) >= int(threshold)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('The file is not a readable PNG mask.') from exc
