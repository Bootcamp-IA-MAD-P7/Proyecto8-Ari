"""Los cuatro filtros de subida de imagen (spec_backend.md, seccion 6), y
que la imagen nunca queda persistida tras clasificar."""

import os
import re
import tempfile

from tests.helpers import png_bytes

_PATRON_ARCHIVO_TEMPORAL = re.compile(r"^[0-9a-f]{32}\.(png|jpg)$")


def test_filtros_subida_imagen(client, tabular_payload):
    r = client.post("/sesiones", json={"id_paciente": "PAC-005"})
    id_sesion = r.json()["id_sesion"]
    client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tabular_payload)
    client.post(f"/sesiones/{id_sesion}/derivacion", json={"motivo_derivacion": "motivo"})

    r = client.post(
        f"/sesiones/{id_sesion}/clasificacion-imagen",
        files={"file": ("evil.txt", b"esto no es una imagen", "text/plain")},
    )
    assert r.status_code == 422  # filtro 2: tipo declarado no permitido

    r = client.post(
        f"/sesiones/{id_sesion}/clasificacion-imagen",
        files={"file": ("fake.png", b"esto no es una imagen de verdad", "image/png")},
    )
    assert r.status_code == 422  # filtro 3: content-type miente sobre el contenido real

    oversized = b"\x00" * (11 * 1024 * 1024)
    r = client.post(
        f"/sesiones/{id_sesion}/clasificacion-imagen",
        files={"file": ("big.png", oversized, "image/png")},
    )
    assert r.status_code == 413  # filtro 1: supera el tamano maximo (10 MB)

    r = client.post(
        f"/sesiones/{id_sesion}/clasificacion-imagen",
        files={"file": ("real.png", png_bytes(), "image/png")},
    )
    assert r.status_code == 200  # PNG real y valido, pasa los cuatro filtros


def test_no_quedan_archivos_temporales_tras_clasificar_imagen(client, tabular_payload):
    tmp_dir = tempfile.gettempdir()
    antes = {f for f in os.listdir(tmp_dir) if _PATRON_ARCHIVO_TEMPORAL.match(f)}

    r = client.post("/sesiones", json={"id_paciente": "PAC-006"})
    id_sesion = r.json()["id_sesion"]
    client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tabular_payload)
    client.post(f"/sesiones/{id_sesion}/derivacion", json={"motivo_derivacion": "motivo"})

    r = client.post(
        f"/sesiones/{id_sesion}/clasificacion-imagen",
        files={"file": ("scan.png", png_bytes(), "image/png")},
    )
    assert r.status_code == 200

    despues = {f for f in os.listdir(tmp_dir) if _PATRON_ARCHIVO_TEMPORAL.match(f)}
    assert despues == antes  # el archivo temporal se borro, no se persiste
