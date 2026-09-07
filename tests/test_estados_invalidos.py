"""Una transicion desde un estado que no la permite se rechaza con 409
(spec_backend.md, seccion 6: "maquina de estados como defensa")."""

from tests.helpers import png_bytes


def test_transiciones_invalidas_dan_409(client, tabular_payload):
    r = client.post("/sesiones", json={"id_paciente": "PAC-003"})
    id_sesion = r.json()["id_sesion"]

    r = client.post(f"/sesiones/{id_sesion}/derivacion", json={"motivo_derivacion": "sin clasificar aun"})
    assert r.status_code == 409

    r = client.post(
        f"/sesiones/{id_sesion}/clasificacion-imagen",
        files={"file": ("scan.png", png_bytes(), "image/png")},
    )
    assert r.status_code == 409

    client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tabular_payload)
    r = client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tabular_payload)
    assert r.status_code == 409

    r = client.post(f"/sesiones/{id_sesion}/cierre", json={"decision_final": "alta"})
    assert r.status_code == 200

    r = client.post(f"/sesiones/{id_sesion}/cierre", json={"decision_final": "alta"})
    assert r.status_code == 409
