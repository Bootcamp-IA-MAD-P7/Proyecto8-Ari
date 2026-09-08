"""404 sobre una sesion que no existe, tanto en el GET como en un POST
(spec_backend.md, seccion 5)."""

import uuid


def test_404_en_sesion_inexistente(client, tabular_payload):
    fake_id = str(uuid.uuid4())

    r = client.get(f"/sesiones/{fake_id}")
    assert r.status_code == 404

    r = client.post(f"/sesiones/{fake_id}/clasificacion-tabular", json=tabular_payload)
    assert r.status_code == 404
