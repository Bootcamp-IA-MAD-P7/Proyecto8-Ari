"""Camino completo de una sesion: abrir, clasificar tabular, derivar,
clasificar imagen, cerrar. Las dos predicciones deben volver separadas en
el GET, nunca fundidas en un veredicto unico (spec_backend.md, seccion 7).
"""

import uuid

from tests.helpers import png_bytes


def test_camino_feliz_completo(client, tabular_payload):
    r = client.post("/sesiones", json={"id_paciente": "PAC-001"})
    assert r.status_code == 201
    body = r.json()
    assert body["estado"] == "abierta"
    id_sesion = body["id_sesion"]
    uuid.UUID(id_sesion)  # debe ser un UUID valido, generado por la API

    r = client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tabular_payload)
    assert r.status_code == 200
    tj = r.json()
    assert {"probability", "prediction", "threshold", "estado"} <= tj.keys()
    assert tj["estado"] == "clasificada_tabular"

    r = client.post(
        f"/sesiones/{id_sesion}/derivacion",
        json={"motivo_derivacion": "Riesgo alto, deriva a imagen"},
    )
    assert r.status_code == 200
    assert r.json()["estado"] == "derivada_imagen"

    r = client.post(
        f"/sesiones/{id_sesion}/clasificacion-imagen",
        files={"file": ("scan.png", png_bytes(), "image/png")},
    )
    assert r.status_code == 200
    ij = r.json()
    assert {"probability", "prediction", "threshold", "estado"} <= ij.keys()
    assert ij["estado"] == "clasificada_imagen"

    r = client.post(f"/sesiones/{id_sesion}/cierre", json={"decision_final": "derivar_especialista"})
    assert r.status_code == 200
    assert r.json()["estado"] == "cerrada"

    r = client.get(f"/sesiones/{id_sesion}")
    assert r.status_code == 200
    gj = r.json()
    assert "tabular" not in gj  # nunca fundidas en un solo veredicto
    assert gj["resultado_tabular"] and gj["resultado_imagen"]
    assert gj["motivo_derivacion"] and gj["decision_final"] == "derivar_especialista"
