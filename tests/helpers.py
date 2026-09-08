"""Helpers de tests que no son fixtures de pytest."""

import io

from PIL import Image


def png_bytes(color: tuple[int, int, int] = (10, 20, 30), size: tuple[int, int] = (64, 64)) -> bytes:
    """Bytes de un PNG real y valido, para los tests que suben una imagen."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()
