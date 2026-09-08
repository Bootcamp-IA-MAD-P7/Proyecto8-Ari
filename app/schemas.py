"""Esquemas Pydantic de entrada y salida (spec_backend.md, secciones 5 y 6).

Toda entrada se valida aca, del lado del servidor, antes de tocar el modelo
o la base. `extra="forbid"` en los cuerpos de request hace cumplir "no se
aceptan campos extra" sin depender de que el front se porte bien.

Rangos clinicos de `age`, `avg_glucose_level` y `bmi` confirmados por Ari:
0-110, 40-400 y 10-100 respectivamente. Las categorias de `smoking_status`
son exactamente las que reconoce el encoder entrenado en
models/smoking_encoder.joblib (verificado contra el objeto real): otro valor
haria que el encoder fallara puertas adentro, por eso se restringe con un enum.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SmokingStatus(str, Enum):
    never_smoked = "never smoked"
    smokes = "smokes"
    formerly_smoked = "formerly smoked"
    unknown = "Unknown"


class DecisionFinal(str, Enum):
    alta = "alta"
    derivar_especialista = "derivar_especialista"


# --- POST /sesiones -------------------------------------------------------

class AbrirSesionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_paciente: str = Field(min_length=1)


class AbrirSesionOut(BaseModel):
    id_sesion: uuid.UUID
    estado: str


# --- POST /sesiones/{id}/clasificacion-tabular ----------------------------

class ClasificacionTabularIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: float = Field(ge=0, le=110)
    hypertension: Literal[0, 1]
    heart_disease: Literal[0, 1]
    avg_glucose_level: float = Field(ge=40, le=400)
    bmi: float = Field(ge=10, le=100)
    smoking_status: SmokingStatus


class ResultadoModeloOut(BaseModel):
    probability: float
    prediction: int
    threshold: float


class ClasificacionTabularOut(ResultadoModeloOut):
    estado: str


# --- POST /sesiones/{id}/derivacion ----------------------------------------

class DerivacionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo_derivacion: str = Field(min_length=1, max_length=500)


class DerivacionOut(BaseModel):
    estado: str


# --- POST /sesiones/{id}/clasificacion-imagen ------------------------------
# El archivo llega como multipart/form-data (UploadFile), no como JSON;
# no tiene esquema Pydantic de entrada. La salida es igual a la tabular.

class ClasificacionImagenOut(ResultadoModeloOut):
    estado: str


# --- POST /sesiones/{id}/cierre --------------------------------------------

class CierreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_final: DecisionFinal


class CierreOut(BaseModel):
    estado: str


# --- GET /sesiones/{id} -----------------------------------------------------

class SesionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_sesion: uuid.UUID
    id_paciente: str
    estado: str
    features_tabular: dict | None
    resultado_tabular: dict | None
    resultado_imagen: dict | None
    motivo_derivacion: str | None
    decision_final: str | None
    creada_en: datetime
    actualizada_en: datetime
