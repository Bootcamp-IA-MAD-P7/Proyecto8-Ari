"""API del servicio de riesgo de ictus (spec_backend.md, seccion 5).

Seis endpoints. Cada uno custodia su propia precondicion de estado del lado
del servidor (seccion 6, "maquina de estados como defensa"): una transicion
desde un estado invalido responde 409, nunca se confia en que el cliente ya
valido antes de llamar.

Los dos modelos se llaman por separado, `predict_tabular` en el endpoint
tabular y `predict_image` en el de imagen -- nunca via el `predict_patient`
conjunto de src/predict.py -- porque las dos clasificaciones ocurren en
momentos distintos de la sesion (nota de la seccion 5).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models_db import Sesion
from app.schemas import (
    AbrirSesionIn,
    AbrirSesionOut,
    CierreIn,
    CierreOut,
    ClasificacionImagenOut,
    ClasificacionTabularIn,
    ClasificacionTabularOut,
    DerivacionIn,
    DerivacionOut,
    SesionOut,
)
from app.security import archivo_temporal, leer_imagen_validada
from src.image import predict_image
from src.tabular import predict_tabular


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Servicio de riesgo de ictus", lifespan=lifespan)


def _obtener_sesion(db: Session, id_sesion: uuid.UUID) -> Sesion:
    sesion = db.get(Sesion, id_sesion)
    if sesion is None:
        raise HTTPException(status_code=404, detail="La sesion no existe.")
    return sesion


def _exigir_estado(sesion: Sesion, *estados_validos: str) -> None:
    if sesion.estado not in estados_validos:
        raise HTTPException(
            status_code=409,
            detail=(
                f"La sesion esta en estado '{sesion.estado}'; "
                f"se esperaba {' o '.join(estados_validos)}."
            ),
        )


@app.post("/sesiones", response_model=AbrirSesionOut, status_code=201)
def abrir_sesion(body: AbrirSesionIn, db: Session = Depends(get_db)) -> dict:
    """Abre una sesion. Sin precondicion de estado."""
    sesion = Sesion(id_paciente=body.id_paciente, estado="abierta")
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return {"id_sesion": sesion.id_sesion, "estado": sesion.estado}


@app.post(
    "/sesiones/{id_sesion}/clasificacion-tabular",
    response_model=ClasificacionTabularOut,
)
def clasificar_tabular(
    id_sesion: uuid.UUID,
    body: ClasificacionTabularIn,
    db: Session = Depends(get_db),
) -> dict:
    """Precondicion: estado 'abierta'."""
    sesion = _obtener_sesion(db, id_sesion)
    _exigir_estado(sesion, "abierta")

    paciente = body.model_dump(mode="json")
    resultado = predict_tabular(paciente)

    sesion.features_tabular = paciente
    sesion.resultado_tabular = resultado
    sesion.estado = "clasificada_tabular"
    db.commit()

    return {**resultado, "estado": sesion.estado}


@app.post("/sesiones/{id_sesion}/derivacion", response_model=DerivacionOut)
def derivar(
    id_sesion: uuid.UUID,
    body: DerivacionIn,
    db: Session = Depends(get_db),
) -> dict:
    """Precondicion: estado 'clasificada_tabular'."""
    sesion = _obtener_sesion(db, id_sesion)
    _exigir_estado(sesion, "clasificada_tabular")

    sesion.motivo_derivacion = body.motivo_derivacion
    sesion.estado = "derivada_imagen"
    db.commit()

    return {"estado": sesion.estado}


@app.post(
    "/sesiones/{id_sesion}/clasificacion-imagen",
    response_model=ClasificacionImagenOut,
)
async def clasificar_imagen(
    id_sesion: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
) -> dict:
    """Precondicion: estado 'derivada_imagen'.

    Se valida sesion y estado antes de tocar el archivo subido: cargar
    imagen fuera de 'derivada_imagen' se rechaza sin gastar en procesar
    un upload no autorizado.
    """
    sesion = _obtener_sesion(db, id_sesion)
    _exigir_estado(sesion, "derivada_imagen")

    contenido, formato = await leer_imagen_validada(file)

    with archivo_temporal(contenido, formato) as ruta:
        # predict_image es CPU-bound (inferencia de la CNN); se corre en
        # threadpool para no bloquear el event loop mientras dura.
        resultado = await run_in_threadpool(predict_image, ruta)
    # `archivo_temporal` borra el archivo siempre al salir del `with`,
    # incluso si `predict_image` lanza una excepcion.

    sesion.resultado_imagen = resultado
    sesion.estado = "clasificada_imagen"
    await run_in_threadpool(db.commit)

    return {**resultado, "estado": sesion.estado}


@app.post("/sesiones/{id_sesion}/cierre", response_model=CierreOut)
def cerrar(
    id_sesion: uuid.UUID,
    body: CierreIn,
    db: Session = Depends(get_db),
) -> dict:
    """Precondicion: estado 'clasificada_tabular' o 'clasificada_imagen'."""
    sesion = _obtener_sesion(db, id_sesion)
    _exigir_estado(sesion, "clasificada_tabular", "clasificada_imagen")

    sesion.decision_final = body.decision_final.value
    sesion.estado = "cerrada"
    db.commit()

    return {"estado": sesion.estado}


@app.get("/sesiones/{id_sesion}", response_model=SesionOut)
def obtener_sesion(id_sesion: uuid.UUID, db: Session = Depends(get_db)) -> Sesion:
    """Sin precondicion de estado. No cambia nada."""
    return _obtener_sesion(db, id_sesion)
