# Reconocimiento de despliegue — insumos reales para spec_deploy.md

Documento de solo lectura. Generado inspeccionando el código y el entorno
real del repo (rama `data`, tras el commit `269e8f1`, cierre de
`spec_front.md`). No se modificó, creó ni corrió nada más allá de este
reporte — no se instaló nada, no se tocó Docker.

---

## 1 · MODELOS

Listado real de `models/`:

```
-rw-r--r-- 1 arii_ 197609 94365959 Sep  5 14:35 cnn_resnet50_stroke.pth
-rw-r--r-- 1 arii_ 197609     3265 Sep  5 14:39 logistic_stroke.joblib
-rw-r--r-- 1 arii_ 197609     1595 Sep  5 14:39 smoking_encoder.joblib
```

En MB: `cnn_resnet50_stroke.pth` ≈ 90.0 MB (94 365 959 bytes), `logistic_stroke.joblib` ≈ 3.2 KB, `smoking_encoder.joblib` ≈ 1.6 KB. El peso real de la imagen lo domina por completo el `.pth`.

`.gitignore`, línea relevante (línea 228 del archivo):

```
models/
```

Confirmado: **`models/` no viaja con el repo.** La imagen Docker va a necesitar copiar estos tres archivos desde el disco de build (no desde `git clone`), con la precondición explícita de que existan ahí en el momento del build — esto ya está anotado como pendiente en `specs/spec_backend.md` sección 0.

---

## 2 · DEPENDENCIAS

No existe `requirements.txt`. El gestor es `uv`, con `pyproject.toml` como fuente de verdad. Contenido completo:

```toml
[project]
name = "proyecto8-ari"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = [
    "fastapi>=0.141.1",
    "ipykernel>=7.3.0",
    "jupyter>=1.1.1",
    "matplotlib>=3.11.1",
    "numpy>=2.5.2",
    "optuna>=4.9.0",
    "pandas>=3.0.5",
    "psycopg[binary]>=3.3.5",
    "python-multipart>=0.0.32",
    "scikit-learn>=1.9.0",
    "seaborn>=0.13.2",
    "sqlalchemy>=2.0.52",
    "sweetviz>=2.3.3",
    "torch>=2.14.0",
    "torchvision>=0.29.0",
    "uvicorn[standard]>=0.52.4",
    "xgboost>=3.4.1",
]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = [{ index = "pytorch-cpu" }]
torchvision = [{ index = "pytorch-cpu" }]

[dependency-groups]
dev = [
    "httpx>=0.28.1",
    "pytest>=9.1.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Python declarado: `requires-python = ">=3.12,<3.14"`. `.python-version` (no pegado arriba, es un archivo aparte de una sola línea) dice `3.12`.

**`torch` y `torchvision` sí están pineados a la variante `+cpu`**, explícitamente: el bloque `[[tool.uv.index]]` apunta al índice `https://download.pytorch.org/whl/cpu` con `explicit = true`, y `[tool.uv.sources]` fuerza a que tanto `torch` como `torchvision` resuelvan contra ese índice. Esto es relevante para el Dockerfile: si se arma el `pip install`/`uv sync` a mano sin respetar `pyproject.toml` + `uv.lock`, hay que replicar ese índice o se va a bajar la build CUDA (mucho más pesada) por defecto.

El grupo `dev` (`httpx`, `pytest`) es solo para los tests locales (`tests/`, corren contra SQLite en memoria) — no hace falta en la imagen de producción, pero tampoco está separado de forma que `uv sync --no-dev` sea automático sin decírselo explícitamente (es justamente lo que hace ese flag).

---

## 3 · DOCKER EXISTENTE

Busqué `Dockerfile*`, `.dockerignore`, `docker-compose*`, `compose.y*ml` en todo el repo (excluyendo `.git`, `node_modules`, `.venv`). **No existe ninguno.** Cero archivos de Docker en el repo a día de hoy.

---

## 4 · ARRANQUE DE LA API

**Comando: no está definido en el repo.** No hay `Procfile`, no hay `uvicorn.run(...)` en ningún `.py`, no hay script en `pyproject.toml`, no hay instrucción en `README.md` (que solo documenta el comando de tests). `uvicorn[standard]` está declarado como dependencia pero nada más. El comando que vengo usando para probar manualmente en las últimas sesiones es una convención mía, no algo escrito en el repo:

```
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Sin ese `--host`/`--port` explícitos, uvicorn cae en su propio default (`127.0.0.1:8000`) — pero eso es comportamiento de uvicorn, no una decisión tomada en este repo.

**Variables de entorno que exige.** Grep de `os.environ`/`os.getenv` en todo `app/`: solo estas dos, ninguna más.

`app/database.py` — lectura de `DATABASE_URL` y fail-fast:

```python
def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Falta la variable de entorno DATABASE_URL con la cadena de conexion a Postgres."
        )
    return url


engine = create_engine(_get_database_url(), pool_pre_ping=True)
```

`_get_database_url()` se ejecuta al importar el módulo (`create_engine(_get_database_url())` está a nivel de módulo, no dentro de una función que se llame más tarde) — es decir, el proceso revienta al arrancar si falta `DATABASE_URL`, antes de levantar ningún endpoint.

`app/main.py` — lectura de `CORS_ORIGINS`:

```python
# Origenes permitidos por variable de entorno (config, no codigo), lista
# separada por comas. Mismo criterio que DATABASE_URL en app/database.py.
_CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

Diferencia importante entre las dos: `DATABASE_URL` no tiene default y hace fail-fast si falta; `CORS_ORIGINS` sí tiene default (`http://localhost:5173`, el puerto de Vite en dev) y **no** revienta si falta — en producción, si no se setea `CORS_ORIGINS` con el origen real del front desplegado, el CORS va a seguir apuntando al `localhost:5173` de desarrollo, silenciosamente.

---

## 5 · CREACIÓN DE TABLA

Se crea vía `lifespan` de FastAPI, en `app/main.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Servicio de riesgo de ictus", lifespan=lifespan)
```

`init_db()`, en `app/database.py`:

```python
def init_db() -> None:
    """Crea las tablas declaradas (si no existen) contra la base conectada."""
    from app import models_db  # noqa: F401  registra Sesion en Base.metadata

    Base.metadata.create_all(bind=engine)
```

Es un `Base.metadata.create_all(bind=engine)` disparado automáticamente en cada arranque del proceso (evento `startup` del lifespan), **no** un paso de init separado ni una migración con Alembic (no hay Alembic en las dependencias, confirmado en la sección 2). `create_all` es idempotente — no falla si la tabla ya existe, solo crea lo que falte. Contra una base Postgres vacía, la tabla `sesiones` (con sus `CHECK CONSTRAINT`, ver `app/models_db.py`) queda creada la primera vez que el proceso arranca con éxito contra esa base, sin necesidad de un contenedor de init aparte ni de correr nada a mano. Sí implica que el usuario de `DATABASE_URL` necesita permiso de `CREATE TABLE` en esa base.

---

## 6 · PESO DE PYTORCH

Medido de verdad en `.venv/Lib/site-packages` de esta máquina (Windows, build `+cpu`), no estimado de memoria:

```
474 MB torch
7 MB torchvision
```

**Aviso de validez:** esto es la instalación real en Windows. La imagen Docker va a ser Linux (asumo, no está decidido en ningún archivo del repo), y el wheel Linux `+cpu` de `torch` no pesa exactamente lo mismo que el de Windows — históricamente el wheel Linux CPU de PyTorch anda en un orden de magnitud similar (varios cientos de MB), pero no tengo el número exacto de Linux porque no puedo descargar nada en este modo de solo lectura. No inflo esto con una cifra inventada: **el número de Linux queda pendiente de medir en la fase de build real.**

**Dependencias de sistema.** Repo no usa `opencv-python`/`cv2` (grep sobre `uv.lock`: cero resultados), así que `libGL` casi con certeza no hace falta — esa es la razón típica por la que un proyecto Python con imágenes necesita `libGL`, y acá no está esa pieza. No puedo confirmar con el mismo nivel de certeza qué más haría falta en una imagen Linux slim (por ejemplo `libgomp1`, un requisito común y documentado de PyTorch en imágenes Debian/Ubuntu minimalistas, para el runtime OpenMP) porque este entorno de reconocimiento es Windows y no hay forma de verificarlo sin construir la imagen — que es justamente lo que este modo prohíbe. Recomendación para la fase de build: probar el arranque en la imagen real y agregar paquetes de sistema recién si el import de `torch`/`torchvision` falla, en vez de instalar de más a ciegas.

---

## 7 · FRONT

`frontend/package.json` (completo, ya pegado en su forma real):

```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "oxlint",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.2.8",
    "react-dom": "^19.2.8"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^6.1.0",
    "oxlint": "^1.79.0",
    "vite": "^8.2.2"
  }
}
```

Confirmado: `npm run build` → `vite build`, que ya corrí en sesiones anteriores de este mismo front y produce estáticos reales en `frontend/dist/` (`index.html` + `assets/*.js` + `assets/*.css`). Es un build 100% estático, sin servidor Node propio en producción (no hay Express ni SSR en las dependencias) — se sirve como archivos planos desde cualquier servidor web o CDN.

Base URL de la API, `frontend/src/config/api.js`:

```javascript
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
```

Confirmado: lee `VITE_API_BASE_URL` (variable de entorno de build de Vite, se resuelve en build-time, no en runtime del navegador) con fallback a `http://localhost:8000`.

**Consecuencia para la spec de despliegue:** el front no tiene ninguna dependencia de Python, uv, ni Postgres — es un proyecto Node/Vite completamente aparte del backend, con su propio `package.json`. Se dockeriza (si se dockeriza) por separado del backend, y como `VITE_API_BASE_URL` se hornea en el build estático, la URL real de la API en producción tiene que conocerse *antes* de correr `npm run build`, no se puede inyectar después como variable de entorno de un contenedor ya corriendo (a menos que se arme un paso extra de sustitución en runtime, que hoy no existe en el repo).

---

Esto fue solo lectura: no se modificó, creó ni corrió nada del repo más allá
de este reporte, y no se instaló ni se dockerizó nada. La spec de
despliegue y el build de las imágenes van en pasos aparte.
