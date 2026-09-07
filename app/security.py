"""Filtros de subida de imagen (spec_backend.md, seccion 6).

Cuatro filtros, en orden, y el archivo debe pasar los cuatro:
1. Limite de tamano (413), cortando antes de leer el archivo entero.
2. Tipo declarado (422): content-type dentro de una lista cerrada.
3. Contenido real (422): los bytes decodifican como una imagen de verdad,
   y el formato real detectado tambien esta dentro de la lista cerrada
   (un content-type declarado no es prueba de nada, es solo una etiqueta).
4. Nombre seguro: la API genera el nombre del archivo temporal, nunca usa
   el nombre que trae el upload.

La imagen nunca se persiste: se escribe a un archivo temporal solo para
pasarle la ruta a `predict_image`, y se borra siempre al terminar (exito
o error).
"""

from __future__ import annotations

import io
import os
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB, confirmado por Ari

# Filtro 2: lista cerrada de content-types declarados que se aceptan.
CONTENT_TYPES_PERMITIDOS = {"image/png", "image/jpeg"}

# Filtro 3: lista cerrada de formatos reales (los que Pillow detecta en los
# bytes), con la extension segura que le corresponde a cada uno.
FORMATOS_PERMITIDOS = {"PNG": ".png", "JPEG": ".jpg"}

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


async def leer_imagen_validada(file: UploadFile) -> tuple[bytes, str]:
    """Aplica los filtros 1 a 3. Devuelve (bytes validados, formato real)."""
    # Filtro 2: tipo declarado. Chequeo barato antes de leer nada del cuerpo.
    if file.content_type not in CONTENT_TYPES_PERMITIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo de imagen no permitido: {file.content_type!r}. Solo se acepta PNG o JPEG.",
        )

    # Filtro 1: limite de tamano, leyendo en bloques y cortando apenas se
    # supera el maximo, sin acumular el archivo entero en memoria antes.
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"La imagen supera el tamano maximo permitido ({MAX_IMAGE_BYTES // (1024 * 1024)} MB).",
            )
        chunks.append(chunk)
    contenido = b"".join(chunks)

    if not contenido:
        raise HTTPException(status_code=422, detail="El archivo de imagen esta vacio.")

    # Filtro 3: contenido real, no solo la etiqueta declarada.
    try:
        with Image.open(io.BytesIO(contenido)) as img:
            formato = img.format
            img.verify()
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="El archivo no es una imagen valida: los bytes no se corresponden con el tipo declarado.",
        ) from exc

    if formato not in FORMATOS_PERMITIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"El contenido real del archivo ({formato}) no es PNG ni JPEG.",
        )

    return contenido, formato


@contextmanager
def archivo_temporal(contenido: bytes, formato: str) -> Iterator[str]:
    """Filtro 4 (nombre seguro) + ciclo de vida del archivo temporal.

    Escribe `contenido` en un archivo con nombre generado por la API (nunca
    el nombre que trajo el upload). Se borra siempre al salir del bloque,
    la clasificacion haya salido bien o mal.
    """
    extension = FORMATOS_PERMITIDOS[formato]
    nombre_seguro = f"{uuid.uuid4().hex}{extension}"
    ruta = os.path.join(tempfile.gettempdir(), nombre_seguro)
    try:
        with open(ruta, "wb") as f:
            f.write(contenido)
        yield ruta
    finally:
        if os.path.exists(ruta):
            os.remove(ruta)
