# Reconocimiento del backend — contrato real para el front

Documento de solo lectura. Generado inspeccionando el código real en
`app/` y `src/` tal como está commiteado (rama `data`, commits `599660b`,
`ff35090`, `262a6f2`). No se modificó ni ejecutó ningún servicio; el único
código que corrió fue `app.openapi()` en proceso (sin levantar un server,
sin tocar Postgres) para la sección 12.

---

## 1 · LA PREGUNTA CLAVE

**Ninguno de los cinco POST devuelve la sesión completa.** Cada uno
devuelve un acuse mínimo, específico de esa acción — nunca `id_paciente`,
nunca `features_tabular`, nunca timestamps, y solo `POST /sesiones`
devuelve `id_sesion`. Para tener el objeto completo, el front **siempre**
tiene que pegarle a `GET /sesiones/{id}` después de cada paso.

Los `response_model` de cada ruta, tal como están en [app/main.py](../app/main.py):

```python
@app.post("/sesiones", response_model=AbrirSesionOut, status_code=201)
def abrir_sesion(body: AbrirSesionIn, db: Session = Depends(get_db)) -> dict:
    ...
    return {"id_sesion": sesion.id_sesion, "estado": sesion.estado}


@app.post(
    "/sesiones/{id_sesion}/clasificacion-tabular",
    response_model=ClasificacionTabularOut,
)
def clasificar_tabular(...) -> dict:
    ...
    return {**resultado, "estado": sesion.estado}


@app.post("/sesiones/{id_sesion}/derivacion", response_model=DerivacionOut)
def derivar(...) -> dict:
    ...
    return {"estado": sesion.estado}


@app.post(
    "/sesiones/{id_sesion}/clasificacion-imagen",
    response_model=ClasificacionImagenOut,
)
async def clasificar_imagen(...) -> dict:
    ...
    return {**resultado, "estado": sesion.estado}


@app.post("/sesiones/{id_sesion}/cierre", response_model=CierreOut)
def cerrar(...) -> dict:
    ...
    return {"estado": sesion.estado}
```

Y los esquemas de salida que esos `response_model` referencian, de
[app/schemas.py](../app/schemas.py):

```python
class AbrirSesionOut(BaseModel):
    id_sesion: uuid.UUID
    estado: str


class ResultadoModeloOut(BaseModel):
    probability: float
    prediction: int
    threshold: float


class ClasificacionTabularOut(ResultadoModeloOut):
    estado: str


class DerivacionOut(BaseModel):
    estado: str


class ClasificacionImagenOut(ResultadoModeloOut):
    estado: str


class CierreOut(BaseModel):
    estado: str
```

Es decir: `POST /sesiones` → `{id_sesion, estado}`. Los otros cuatro POST
→ o bien `{estado}` solo (derivación, cierre) o `{probability, prediction,
threshold, estado}` (las dos clasificaciones). Ninguno trae `id_sesion` de
vuelta salvo el de apertura — el front tiene que guardarlo del primer
paso y reusarlo en la URL de los siguientes.

---

## 2 · INVENTARIO DE ENDPOINTS

| # | Método y ruta | Status éxito | Precondición (`estado` actual) | Estado resultante |
|---|---|---|---|---|
| 1 | `POST /sesiones` | 201 | ninguna | `abierta` |
| 2 | `POST /sesiones/{id_sesion}/clasificacion-tabular` | 200 | `abierta` | `clasificada_tabular` |
| 3 | `POST /sesiones/{id_sesion}/derivacion` | 200 | `clasificada_tabular` | `derivada_imagen` |
| 4 | `POST /sesiones/{id_sesion}/clasificacion-imagen` | 200 | `derivada_imagen` | `clasificada_imagen` |
| 5 | `POST /sesiones/{id_sesion}/cierre` | 200 | `clasificada_tabular` **o** `clasificada_imagen` | `cerrada` |
| 6 | `GET /sesiones/{id_sesion}` | 200 | ninguna (no cambia nada) | — |

Los status 200/201 son los que efectivamente están declarados en cada
decorador de ruta (`status_code=201` explícito solo en la apertura; el
resto usa el 200 por defecto de FastAPI para POST, no está sobreescrito
en ningún otro endpoint).

La precondición y el estado resultante están hardcodeados en
`app/main.py`, no en un objeto de configuración de máquina de estados —
cada handler llama a `_exigir_estado(sesion, "...")` y después asigna
`sesion.estado = "..."` a mano. Código real de las dos funciones guardia:

```python
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
```

---

## 3 · FORMA DE LA SESIÓN (`GET /sesiones/{id}`)

Confirmados los diez campos que preguntaste, tal cual, en ese orden, de
[app/schemas.py](../app/schemas.py):

```python
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
```

Serialización JSON real (según `app.openapi()`, ver sección 12):
`id_sesion` sale como string con `format: uuid`; `creada_en` y
`actualizada_en` como string con `format: date-time` (ISO 8601);
`features_tabular` / `resultado_tabular` / `resultado_imagen` como objeto
JSON arbitrario o `null`; `motivo_derivacion` / `decision_final` como
string o `null`. **Los diez campos son `required` en el schema** — es
decir, siempre están presentes en el JSON de respuesta, aunque su valor
sea `null` (no hay campos que directamente falten en el payload según el
estado).

Nota: no hay un campo `tabular` ni `imagen` anidados envolviendo los
resultados — son columnas planas al mismo nivel que el resto (confirmado
también en el test `test_camino_feliz_completo`, que hace
`assert "tabular" not in gj`).

---

## 4 · VALORES DE ESTADO

Constante real, de [app/models_db.py](../app/models_db.py):

```python
ESTADOS_VALIDOS = (
    "abierta",
    "clasificada_tabular",
    "derivada_imagen",
    "clasificada_imagen",
    "cerrada",
)
```

Esta tupla se usa para armar el `CHECK CONSTRAINT` de Postgres
(`ck_sesiones_estado_valido`), **no** hay un `Enum` de Pydantic para
`estado` — en los schemas de salida `estado` está tipado como `str`
liso (`estado: str`), sin restricción de valores del lado de FastAPI. La
restricción real de qué strings son válidos vive en `app/main.py` (los
`_exigir_estado(...)` de cada endpoint, ya pegados en la sección 2) y en
el `CHECK` de la base. El front debe tratar esos cinco strings como las
únicas constantes válidas para el stepper, pero no va a encontrar un
enum Python ni un enum en el JSON schema que se los liste como tal (salvo
indirectamente, en el texto del `CHECK`).

Transición que habilita cada endpoint (resumen de la sección 2, mismos
cinco strings, literales):

- `abierta` → (`clasificacion-tabular`) → `clasificada_tabular`
- `clasificada_tabular` → (`derivacion`) → `derivada_imagen`
- `derivada_imagen` → (`clasificacion-imagen`) → `clasificada_imagen`
- `clasificada_tabular` **o** `clasificada_imagen` → (`cierre`) → `cerrada`
- `cerrada` no tiene ninguna transición de salida (no hay DELETE ni
  reapertura; cualquier POST sobre una sesión `cerrada` da 409).

---

## 5 · CONTRATO TABULAR

Modelo Pydantic completo de la entrada, de [app/schemas.py](../app/schemas.py):

```python
class SmokingStatus(str, Enum):
    never_smoked = "never smoked"
    smokes = "smokes"
    formerly_smoked = "formerly smoked"
    unknown = "Unknown"


class ClasificacionTabularIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: float = Field(ge=0, le=110)
    hypertension: Literal[0, 1]
    heart_disease: Literal[0, 1]
    avg_glucose_level: float = Field(ge=40, le=400)
    bmi: float = Field(ge=10, le=100)
    smoking_status: SmokingStatus
```

**No hay `@field_validator` ni `@model_validator` custom en esta clase ni
en ninguna otra de `app/schemas.py`** (confirmado leyendo el archivo
completo) — toda la validación es declarativa, vía `Field(ge=..., le=...)`,
`Literal[0, 1]` y el `Enum` de arriba. `model_config = ConfigDict(extra="forbid")`
es lo que rechaza cualquier campo fuera de estos seis.

Tabla resumen:

| Campo | Tipo | Rango / categorías | Obligatorio |
|---|---|---|---|
| `age` | `float` | 0 – 110 inclusive | sí |
| `hypertension` | `int` (literal) | `0` o `1` | sí |
| `heart_disease` | `int` (literal) | `0` o `1` | sí |
| `avg_glucose_level` | `float` | 40 – 400 inclusive | sí |
| `bmi` | `float` | 10 – 100 inclusive | sí |
| `smoking_status` | `str` (enum) | `"never smoked"`, `"smokes"`, `"formerly smoked"`, `"Unknown"` | sí |

**`gender` y `work_type` no están definidos en ningún lado del contrato.**
No son campos opcionales ignorados: por `extra="forbid"`, si el front los
manda, la request entera se rechaza con 422. No armes esos inputs en el
front.

---

## 6 · FORMA DE LOS RESULTADOS

`resultado_tabular` y `resultado_imagen` son exactamente lo que devuelven
`predict_tabular` y `predict_image` de `src/`, sin transformación
adicional en `app/main.py` (se guarda el dict devuelto tal cual, y
también se lo desarma con `{**resultado, "estado": ...}` para la
respuesta HTTP).

De [src/tabular.py](../src/tabular.py):

```python
    return {"probability": proba, "prediction": prediction, "threshold": THRESHOLD}
```

con `THRESHOLD = 0.43` (constante fija del módulo, no configurable).

De [src/image.py](../src/image.py):

```python
    return {"probability": proba, "prediction": prediction, "threshold": THRESHOLD}
```

con `THRESHOLD = 0.5` (constante fija del módulo, no configurable).

Ambos: `probability: float` (0–1), `prediction: int` (0 o 1),
`threshold: float`. Mismas tres claves en los dos, ningún campo extra
(ni nombre de clase, ni "riesgo alto/bajo" en texto — eso lo arma el
front a partir de `prediction`/`probability` si quiere).

---

## 7 · CONTRATO DE IMAGEN

De [app/main.py](../app/main.py), la firma del endpoint:

```python
async def clasificar_imagen(
    id_sesion: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
) -> dict:
```

El nombre del campo multipart es **`file`** — confirmado también en el
OpenAPI generado (`Body_clasificar_imagen_..._post.properties.file`).

De [app/security.py](../app/security.py):

```python
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB, confirmado por Ari

CONTENT_TYPES_PERMITIDOS = {"image/png", "image/jpeg"}

FORMATOS_PERMITIDOS = {"PNG": ".png", "JPEG": ".jpg"}
```

- Tope de tamaño: **10 MB** (`10 * 1024 * 1024` bytes exactos). Si se
  supera, 413, cortando la lectura por bloques de 1 MiB antes de
  acumular el archivo entero.
- Content-type declarado aceptado: **`image/png` o `image/jpeg`**, nada
  más — cualquier otro valor de `Content-Type` en la parte multipart da
  422 antes de leer el cuerpo.
- Además del content-type declarado, se revalida el formato real
  decodificado por Pillow (`img.format`), que también debe caer en
  `{"PNG", "JPEG"}` — un archivo que no sea realmente una imagen, o que
  sea una imagen de un formato distinto aunque declare `image/png`, da
  422.
- Devuelve (si pasa los cuatro filtros): `ClasificacionImagenOut` —
  `{probability, prediction, threshold, estado}`, igual forma que la
  tabular (ver secciones 1 y 6). `estado` pasa a `"clasificada_imagen"`.

---

## 8 · DERIVACIÓN Y CIERRE

`decision_final`, de [app/schemas.py](../app/schemas.py):

```python
class DecisionFinal(str, Enum):
    alta = "alta"
    derivar_especialista = "derivar_especialista"


class CierreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_final: DecisionFinal
```

Únicos dos valores válidos: `"alta"` y `"derivar_especialista"`.
Cualquier otro string da 422.

`motivo_derivacion`:

```python
class DerivacionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo_derivacion: str = Field(min_length=1, max_length=500)
```

Tipo `str`, con **mínimo 1 y máximo 500 caracteres** — ojo que no es solo
un tope superior, un string vacío `""` también da 422 (`min_length=1`).

---

## 9 · FORMA DE LOS ERRORES

Importante: **no todos los 422 tienen la misma forma.** Hay dos orígenes
distintos y el `detail` sale distinto en cada uno.

**422 de validación Pydantic** (falta un campo, tipo equivocado, fuera de
rango, campo extra, `smoking_status`/`decision_final` fuera del enum,
`motivo_derivacion` fuera de longitud) — generado automáticamente por
FastAPI, `detail` es un **array de objetos**. Schema real, tomado del
`openapi.json` generado (sección 12):

```json
{
  "detail": [
    {
      "loc": ["body", "age"],
      "msg": "<mensaje>",
      "type": "<tipo de error>",
      "input": "<valor recibido>",
      "ctx": {}
    }
  ]
}
```

(`ctx` es opcional, no siempre está.) El schema formal:

```python
class ValidationError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str
    input: Any
    ctx: dict | None = None


class HTTPValidationError(BaseModel):
    detail: list[ValidationError] | None = None
```

Esto es un schema autogenerado por FastAPI (no vive como clase Python en
`app/schemas.py`; aparece en `components.schemas` del OpenAPI porque
FastAPI lo agrega solo).

**422 manual de los filtros de imagen, 409, 404, 413** — estos NO pasan
por el validador de Pydantic, son `raise HTTPException(status_code=..., detail="...")`
directos en `app/main.py` y `app/security.py`. Su `detail` es un
**string simple**, no un array:

```json
{"detail": "La sesion no existe."}
```

```json
{"detail": "La sesion esta en estado 'abierta'; se esperaba clasificada_tabular."}
```

```json
{"detail": "La imagen supera el tamano maximo permitido (10 MB)."}
```

```json
{"detail": "Tipo de imagen no permitido: 'text/plain'. Solo se acepta PNG o JPEG."}
```

Los mensajes de texto exactos (interpolados con los valores reales de
cada caso) están pegados en las secciones 2 y 7 de este documento —
son los `detail=f"..."` literales del código. **El front no puede asumir
`detail` como array de forma universal: tiene que chequear el status
code para decidir si `detail` es string u objeto.**

**5xx — no está definido en el código.** No hay ningún
`@app.exception_handler(...)` ni middleware de errores en
`app/main.py` (confirmado por búsqueda en todo `app/`: cero
resultados para `exception_handler`). Sin un handler propio, aplica el
comportamiento por defecto de Starlette para una excepción no capturada:
como `FastAPI(...)` se instancia sin `debug=True`, el 500 por defecto de
Starlette es **texto plano**, no JSON:

```
Internal Server Error
```

status 500, `Content-Type: text/plain`. Esto es comportamiento de
framework, no algo escrito en este repo — lo marco porque es una trampa
real para el front: un `response.json()` a ciegas sobre un 500 va a
tirar un error de parseo en vez de darte el mensaje.

---

## 10 · CORS

**No está definido.** Búsqueda en todo `app/` de `CORSMiddleware`,
`add_middleware`, `allow_origins`: cero resultados. `app/main.py` no
importa `fastapi.middleware.cors` ni llama a `app.add_middleware(...)`
en ningún lado — el único middleware de la app es el que FastAPI agrega
por defecto (ninguno custom).

Consecuencia directa: si el front corre en otro origen (otro puerto,
otro host), el navegador va a bloquear las requests por CORS hasta que
se agregue el middleware. Esto no es parte de `spec_backend.md` (no está
mencionado ahí tampoco) — es algo a resolver antes de que el front pueda
pegarle a esta API desde un origen distinto.

---

## 11 · CÓMO SE LEVANTA

**Variable de entorno exigida:** `DATABASE_URL`. De
[app/database.py](../app/database.py):

```python
def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Falta la variable de entorno DATABASE_URL con la cadena de conexion a Postgres."
        )
    return url
```

Formato esperado (comentario del mismo archivo):
`postgresql+psycopg://usuario:password@host:puerto/nombre_bd`. No hay
ninguna otra variable de entorno referenciada en `app/` (búsqueda de
`os.environ` / `os.getenv` en todo el paquete: solo esta).

**Comando para correr la API: no está definido en el repo.** No hay
`Procfile`, ni script en `pyproject.toml`, ni bloque `if __name__ ==
"__main__"` en `app/main.py`, ni instrucción en el README. `uvicorn` está
declarado como dependencia (`uvicorn[standard]>=0.52.4` en
`pyproject.toml`) pero no hay un comando documentado en ningún lado del
repo. Dado que `app = FastAPI(...)` vive en `app/main.py`, el comando
esperable sería `uv run uvicorn app.main:app` — pero esto es una
inferencia mía a partir de la convención, no algo que esté escrito en el
código; no hay host/puerto configurado explícitamente en ningún lado
(ni `uvicorn.run(...)` con argumentos, ni variables `HOST`/`PORT`), así
que si se corre así, quedaría en el default de uvicorn (`127.0.0.1:8000`).

**Comando de los tests**, de [README.md](../README.md), literal:

```
uv run pytest
```

Confirmado también en `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## 12 · OPENAPI

`app/main.py` instancia `FastAPI(title="Servicio de riesgo de ictus", lifespan=lifespan)`
sin `docs_url`, `redoc_url` ni `openapi_url` sobreescritos — con la app
corriendo, `/docs`, `/redoc` y `/openapi.json` están disponibles con sus
rutas por defecto.

No levanté ningún servidor para esto: llamé a `app.openapi()` en proceso
(introspección estática de los schemas ya leídos arriba, sin tocar la
base ni el lifespan) para tener el volcado real y cruzarlo contra lo que
ya había leído a mano. `openapi: "3.1.0"`. Los seis `paths` coinciden
exactamente con el inventario de la sección 2:

```
/sesiones
/sesiones/{id_sesion}/clasificacion-tabular
/sesiones/{id_sesion}/derivacion
/sesiones/{id_sesion}/clasificacion-imagen
/sesiones/{id_sesion}/cierre
/sesiones/{id_sesion}
```

**Hallazgo del cruce, importante para el front**: el `openapi.json`
generado **solo documenta las respuestas 200/201 y 422** de cada ruta.
Los 404, 409 y 413 que el código sí devuelve en runtime (pegados en las
secciones 2, 7 y 9) **no aparecen en absoluto** en `responses` de ningún
path — porque ninguna ruta usa el parámetro `responses={...}` de FastAPI
para declararlos, así que el generador de OpenAPI no tiene cómo saber
que existen. Si vas a generar un cliente TypeScript desde este
`openapi.json` (openapi-typescript, orval, etc.), esos tres códigos no
van a estar tipados — hay que agregarlos a mano en el front a partir de
este documento, no del schema máquina a máquina.

El resto de `components.schemas` coincide 1:1 con lo pegado en las
secciones 1, 3, 5, 6 y 8 de este documento (`AbrirSesionIn/Out`,
`ClasificacionTabularIn/Out`, `DerivacionIn/Out`, `ClasificacionImagenOut`,
`CierreIn/Out`, `SesionOut`, `SmokingStatus`, `DecisionFinal`,
`HTTPValidationError`, `ValidationError`). No lo repito completo acá para
no duplicar; si querés el JSON entero para un generador de cliente,
avisame y lo saco de nuevo (no lo dejé guardado en el repo, se generó y
se borró en esta misma sesión de reconocimiento).

---

Esto fue solo lectura: no se modificó, creó ni ejecutó ningún archivo del
backend más allá de este reporte. La construcción del front es un paso
aparte.