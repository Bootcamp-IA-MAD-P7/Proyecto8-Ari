"""Conexion a PostgreSQL.

La cadena de conexion se lee siempre de la variable de entorno DATABASE_URL.
Las credenciales nunca se escriben en el codigo (spec_backend.md, secciones 2 y 6).

Formato esperado de DATABASE_URL:
    postgresql+psycopg://usuario:password@host:puerto/nombre_bd

PENDIENTE (criterio de aceptacion, spec_backend.md seccion 7): "los datos de
la sesion persisten en Postgres y sobreviven a un reinicio" no esta verificado
todavia. Este entorno de desarrollo no tiene Postgres ni Docker instalados; esa
verificacion en vivo queda para la fase de despliegue (spec_deploy.md).
"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Falta la variable de entorno DATABASE_URL con la cadena de conexion a Postgres."
        )
    return url


engine = create_engine(_get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesion de DB y la cierra siempre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea las tablas declaradas (si no existen) contra la base conectada."""
    from app import models_db  # noqa: F401  registra Sesion en Base.metadata

    Base.metadata.create_all(bind=engine)
