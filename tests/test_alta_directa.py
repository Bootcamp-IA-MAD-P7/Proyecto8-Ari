"""Camino de alta directa: cierre tras la clasificacion tabular, sin pasar
por imagen (spec_backend.md, seccion 5: /cierre acepta clasificada_tabular
o clasificada_imagen como precondicion)."""


def test_cierre_directo_sin_imagen(client, tabular_payload):
    r = client.post("/sesiones", json={"id_paciente": "PAC-002"})
    id_sesion = r.json()["id_sesion"]

    client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tabular_payload)

    r = client.post(f"/sesiones/{id_sesion}/cierre", json={"decision_final": "alta"})
    assert r.status_code == 200
    assert r.json()["estado"] == "cerrada"
