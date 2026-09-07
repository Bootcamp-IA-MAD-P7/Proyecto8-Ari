"""Modelo ORM de la tabla `sesiones` (spec_backend.md, seccion 4).

Una sola tabla. Guarda el rastro de auditoria de la sesion, no historiales
clinicos. Los valores nulos codifican en que parte de la maquina de estados
va la sesion. No hay columna para la imagen: no se almacena, solo su
resultado en `resultado_imagen`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, CheckConstraint, DateTime, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ESTADOS_VALIDOS = (
    "abierta",
    "clasificada_tabular",
    "derivada_imagen",
    "clasificada_imagen",
    "cerrada",
)

DECISIONES_VALIDAS = ("alta", "derivar_especialista")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sql_in_list(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


class Sesion(Base):
    __tablename__ = "sesiones"

    id_sesion: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    id_paciente: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(Text, nullable=False)

    features_tabular: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resultado_tabular: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resultado_imagen: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    motivo_derivacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_final: Mapped[str | None] = mapped_column(Text, nullable=True)

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            f"estado IN ({_sql_in_list(ESTADOS_VALIDOS)})",
            name="ck_sesiones_estado_valido",
        ),
        CheckConstraint(
            f"decision_final IS NULL OR decision_final IN ({_sql_in_list(DECISIONES_VALIDAS)})",
            name="ck_sesiones_decision_final_valida",
        ),
        CheckConstraint(
            "motivo_derivacion IS NULL OR char_length(motivo_derivacion) <= 500",
            name="ck_sesiones_motivo_derivacion_tope",
        ),
    )
