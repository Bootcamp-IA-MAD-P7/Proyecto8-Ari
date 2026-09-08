"""Fixtures compartidas de los tests de integracion (spec_backend.md, seccion 7).

SQLite en memoria reemplaza a Postgres SOLO ACA, detras de un
`dependency_override` de `get_db`, igual que en la verificacion manual del
Bloque 2. No se toca `app/database.py` ni `app/models_db.py`: ese codigo
sigue exigiendo `DATABASE_URL` apuntando a una Postgres real para correr
fuera de los tests. Nada de esto agrega Postgres ni Docker al entorno.
"""

import os

# Debe fijarse antes de importar app.database / app.main, porque leen la
# variable de entorno al definirse el engine a nivel de modulo. El valor no
# se usa nunca: el engine real de la app no se toca en los tests.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/stroke_db_test"
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    """Cliente de test con una base SQLite en memoria propia y aislada.

    Motor y tablas se crean de cero en cada test (funcion), asi que los
    tests no comparten estado entre si sin importar el orden en que corran.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        # Sin esto, cada thread del threadpool de FastAPI abriria su propia
        # base ":memory:" vacia en vez de compartir una sola.
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _shim_char_length(dbapi_conn, _):
        # char_length() es especifico de Postgres (lo usan los CHECK
        # constraint de app/models_db.py); SQLite no lo trae de fabrica.
        dbapi_conn.create_function(
            "char_length", 1, lambda s: len(s) if s is not None else None
        )

    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    # Sin el `with`, TestClient no dispara el lifespan de la app (que llama
    # a init_db() contra el engine real de Postgres en app/database.py). Las
    # tablas ya se crearon arriba, contra el engine SQLite de este fixture.
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture
def tabular_payload():
    """Un paciente valido para el endpoint de clasificacion tabular."""
    return {
        "age": 67,
        "hypertension": 0,
        "heart_disease": 1,
        "avg_glucose_level": 228.7,
        "bmi": 36.6,
        "smoking_status": "smokes",
    }
