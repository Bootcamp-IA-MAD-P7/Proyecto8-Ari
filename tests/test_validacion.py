"""Una entrada mal formada devuelve 422, del lado del servidor, sin confiar
en que el cliente ya valido antes de llamar (spec_backend.md, seccion 6)."""


def test_validaciones_pydantic(client, tabular_payload):
    r = client.post("/sesiones", json={})
    assert r.status_code == 422  # falta id_paciente

    r = client.post("/sesiones", json={"id_paciente": "PAC-004"})
    id_sesion = r.json()["id_sesion"]

    incompleto = dict(tabular_payload)
    del incompleto["bmi"]
    r = client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=incompleto)
    assert r.status_code == 422  # falta un campo

    fuera_rango = dict(tabular_payload, age=200)
    r = client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=fuera_rango)
    assert r.status_code == 422  # age fuera del rango clinico (0-110)

    tipo_malo = dict(tabular_payload, hypertension=2)
    r = client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tipo_malo)
    assert r.status_code == 422  # hypertension solo admite 0 o 1

    smoking_malo = dict(tabular_payload, smoking_status="pipa ocasional")
    r = client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=smoking_malo)
    assert r.status_code == 422  # smoking_status fuera del enum permitido

    con_extra = dict(tabular_payload, gender="Male")
    r = client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=con_extra)
    assert r.status_code == 422  # campo extra no aceptado

    client.post(f"/sesiones/{id_sesion}/clasificacion-tabular", json=tabular_payload)

    r = client.post(f"/sesiones/{id_sesion}/derivacion", json={"motivo_derivacion": "x" * 501})
    assert r.status_code == 422  # motivo_derivacion supera el tope de 500

    client.post(f"/sesiones/{id_sesion}/derivacion", json={"motivo_derivacion": "motivo valido"})

    r = client.post(f"/sesiones/{id_sesion}/cierre", json={"decision_final": "curar_con_fe"})
    assert r.status_code == 422  # decision_final fuera de alta/derivar_especialista
