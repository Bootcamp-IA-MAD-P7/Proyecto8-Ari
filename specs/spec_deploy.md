# spec_deploy.md — Dockerización y despliegue

Documento de diseño para dockerizar el proyecto y desplegarlo en Render.
Lo ejecuta Claude Code por bloques, con puntos de control humanos entre bloques.
Insumo real: `specs/reconocimiento_deploy.md`, leerlo antes de tocar nada. Si algo
no está definido acá, no se inventa, se pregunta.

**Encuadre.** El proyecto es API (FastAPI, Docker) más Postgres más front (React
servido por Nginx). El objetivo es correrlo entero con `docker-compose` en local y
después desplegarlo en Render con una URL pública.

**Prioridad, esto es una entrega con reloj.** La spec está partida en dos. La Parte A
es todo lo que corre local con Docker, y es un entregable Docker completo por sí
mismo. La Parte B es el despliegue en Render, encima de esa misma base. Si el tiempo
aprieta, cerrar la Parte A entera antes de abrir la B. No dejar la A a medias por
adelantar la B.

**Convenciones.** Código, nombres y comentarios en inglés. Commits en inglés, sin
push salvo que se pida. Sin secretos hardcodeados, todo por variable de entorno.

---

## 1 · Arquitectura de despliegue

Tres piezas que se hablan.

```
navegador
   │  todo al mismo origen
   ▼
┌─ front (Nginx) ────────────────┐
│  sirve el build estático de     │
│  React, y hace de reverse proxy │
│  /api  ─────────────►  API      │
└─────────────────────────────────┘
                          │  DATABASE_URL
                          ▼
                       Postgres
```

**Reverse proxy, la decisión que ordena todo.** Nginx sirve el front y además
reenvía las llamadas `/api` a la API. El navegador ve un solo origen, el del front.
Dos consecuencias buenas que hay que aprovechar en toda la spec.

- El front le habla a una ruta relativa `/api`, no a una URL absoluta. Así el
  `VITE_API_BASE_URL` que se hornea en build deja de depender de conocer la URL de
  la API de antemano.
- CORS deja de dispararse, porque no hay dos orígenes. La trampa del default
  silencioso de `CORS_ORIGINS` que marcó el reconocimiento queda desactivada por
  diseño. Igual se setea la variable por defensa, pero ya no es la pieza crítica.

**Local contra Render, no son un calco.** La spec maneja la diferencia con variables.

| Pieza | Local (compose) | Render |
|---|---|---|
| Postgres | contenedor del compose | base gestionada por Render |
| Upstream del proxy | `http://api:8000` (nombre de servicio) | URL interna del servicio de API en Render |
| Puerto de escucha | fijo | el que Render inyecta en `PORT` |
| Imagen de la API | build local | ver Parte B, los modelos obligan a decidir |

---

## PARTE A · Docker local

## 2 · Imagen de la API

Un `Dockerfile.api` en la raíz del repo.

**Base y Python.** `python:3.12-slim` (Linux). El proyecto declara Python
`>=3.12,<3.14` y `.python-version` fija `3.12`.

**Dependencias, el punto que más fácil rompe el tamaño.** El `pyproject.toml` fuerza
`torch` y `torchvision` contra el índice CPU de PyTorch con `explicit = true`. El
build TIENE que respetar `pyproject.toml` más `uv.lock`, o Docker se baja la variante
CUDA por defecto, que pesa varios gigas de más y es inútil sin GPU. Usar `uv` dentro
de la imagen y correr `uv sync --no-dev` para instalar exactamente lo pineado, sin el
grupo `dev` (`httpx`, `pytest`), que es solo para los tests locales.

**Los modelos, precondición explícita.** `models/` está en `.gitignore`, así que los
tres artefactos no viajan con el repo. Son `cnn_resnet50_stroke.pth` (unos 90 MB),
`logistic_stroke.joblib` y `smoking_encoder.joblib`. El Dockerfile los copia desde el
disco de build con `COPY models/ ./models/`, con la precondición de que existan en
disco en el momento del build. En local existen, así que acá no hay bloqueo. En Render
sí lo hay, se resuelve en la Parte B.

**Qué copia la imagen.** Solo lo que la API necesita en runtime, `app/`, `src/`,
`models/`, y los archivos de dependencias. Un `.dockerignore` excluye `node_modules`,
`.venv`, `.git`, `frontend/`, `data/`, `notebooks/`, `reports/`, `tests/` y los
`.ipynb`. La imagen no debe cargar el dataset ni los notebooks.

**Arranque.** El contenedor debe escuchar en `0.0.0.0`, no en `127.0.0.1`, o queda
inalcanzable desde afuera del contenedor. El comando, pensado para servir en local y
en Render sin cambiar la imagen.

```
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

En local `PORT` no está seteado y cae en 8000. En Render, que inyecta `PORT`, usa ese.

**Dependencia de sistema, solo si hace falta.** El reconocimiento confirmó que el
proyecto no usa OpenCV, así que `libGL` no hace falta. Puede que el runtime de PyTorch
pida `libgomp1` en una imagen slim. No instalarlo a ciegas. Construir, probar que
`import torch` y `import torchvision` funcionan dentro del contenedor, y agregar
`libgomp1` con `apt-get` solo si el import falla.

**No hace falta paso de init de base.** La tabla `sesiones` la crea sola el `lifespan`
con `create_all` al arrancar la API contra la base. Es idempotente. El usuario de
`DATABASE_URL` sí necesita permiso de `CREATE TABLE`.

## 3 · Imagen del front

Un `Dockerfile.front` en `frontend/`, de dos etapas.

**Etapa 1, build.** Base `node`, `npm ci`, y `npm run build` con
`VITE_API_BASE_URL=/api` (ruta relativa, porque Nginx hace de proxy). Produce los
estáticos en `dist/`.

**Etapa 2, servir.** Base `nginx:alpine`. Copia los estáticos de la etapa 1 a
`/usr/share/nginx/html`. Config de Nginx propia con dos responsabilidades.

- Servir el front estático, con fallback a `index.html` para que la app cargue en
  cualquier ruta.
- Reverse proxy, `location /api/ { proxy_pass <upstream>/; }`. La barra final en el
  `proxy_pass` recorta el prefijo `/api`, así `/api/sesiones` llega a la API como
  `/sesiones`, que es como el backend nombra sus rutas de verdad.

El upstream y el puerto de escucha de Nginx van por variable para que la misma imagen
sirva local y Render. Local, upstream `http://api:8000` y escucha en 80. Render,
upstream la URL interna de la API y escucha en `PORT`. Resolver con una plantilla de
config y `envsubst` en el arranque del contenedor, con defaults para el caso local.

## 4 · Compose local, tres servicios

Un `docker-compose.yml` en la raíz con `db`, `api` y `web`.

| Servicio | Qué es | Puntos clave |
|---|---|---|
| `db` | `postgres:16-alpine` | usuario/clave/base por env, volumen nombrado para persistir, healthcheck |
| `api` | build `Dockerfile.api` | `DATABASE_URL=postgresql+psycopg://stroke:stroke@db:5432/stroke_db`, `depends_on` db sana |
| `web` | build `frontend/Dockerfile.front` | publica `8080:80`, proxy `/api` a `http://api:8000`, `depends_on` api |

**El volumen, el criterio de persistencia.** El servicio `db` monta un volumen
nombrado para sus datos. Es lo que hace que las sesiones sobrevivan a un reinicio del
contenedor, el criterio de la sección 7 del backend. Sin volumen, cada `down` borra
todo.

**El orden de arranque.** La API revienta si Postgres no está listo, porque
`create_engine` lee `DATABASE_URL` al importar el módulo. El `depends_on` con
`condition: service_healthy` sobre el healthcheck de `db` hace que la API espere a que
la base acepte conexiones antes de arrancar.

**Aceptación de la Parte A.** `docker compose up --build`, abrir `http://localhost:8080`,
recorrer el camino feliz completo, abrir sesión, clasificar, derivar, subir imagen,
cerrar. Después `docker compose restart db` o un `down` y `up` sin borrar el volumen,
y confirmar que una sesión guardada antes sigue estando al consultarla por su id. Eso
prueba las tres cosas de una, que los servicios se hablan, que el proxy funciona, y
que el volumen persiste.

---

## PARTE B · Despliegue en Render

Abrir solo con la Parte A cerrada y andando en local.

## 5 · El bloqueo de los modelos, resolver primero

Este es el nudo de la Parte B y hay que desatarlo antes que nada. Render construye
desde el repo de GitHub, y `models/` no está en el repo. Un build en Render no tiene
los modelos que el `Dockerfile.api` intenta copiar, así que el `COPY models/` falla.
En local no pasa porque los modelos están en tu disco, en Render sí. Dos caminos.

| Camino | Cómo | Costo |
|---|---|---|
| Imagen pre-construida (recomendado) | construir la imagen de la API en local, donde los modelos existen, empujarla a un registro, y que Render despliegue esa imagen ya hecha en vez de construir desde el repo | evita el problema de raíz, no toca `.gitignore` |
| Modelos al repo | sacar `models/` del `.gitignore` o usar Git LFS, para que el build de Render los vea | mete 90 MB en git, ensucia el historial |

Recomiendo el primero para la API. La imagen se construye donde los modelos viven, y
Render solo la baja. La decisión es tuya, es la primera de la Parte B.

## 6 · Servicios en Render

**Postgres gestionado.** Crear la base gestionada de Render. Render entrega una URL de
conexión, y acá hay un gotcha real. Render la da con esquema `postgres://` o
`postgresql://`, pero el proyecto usa psycopg v3, que necesita
`postgresql+psycopg://`. Adaptar el esquema al setear `DATABASE_URL` en la API, o la
conexión falla.

**Servicio de API.** Desplegar la imagen (pre-construida, según la sección 5). Setear
`DATABASE_URL` con la URL interna de la base gestionada, esquema adaptado. `PORT` lo
inyecta Render y el comando ya lo respeta. `CORS_ORIGINS` se puede setear al origen
público del front por defensa, aunque con el reverse proxy no es crítico.

**Servicio del front.** Desplegar la imagen de Nginx. Acá el upstream del proxy tiene
que apuntar a la URL interna del servicio de API en Render, no al `http://api:8000` de
compose. Se pasa por la variable del upstream que la imagen ya lee. Y Nginx tiene que
escuchar en el `PORT` que Render inyecta, que la plantilla ya resuelve.

**Aceptación de la Parte B.** Abrir la URL pública del front de Render, recorrer el
camino feliz de punta a punta contra la API desplegada. Aviso de tier gratis, el
servicio se duerme tras inactividad y la primera carga tarda en despertar, no es un
fallo.

---

## Bloque de arranque para Claude Code

Modo construcción, spec-driven, por bloques. Insumo real
`specs/reconocimiento_deploy.md`, leerlo primero. Construir por bloques, parar en cada
punto de control y mostrar antes de seguir. No modificar el código de `app/`, `src/`
ni del front, esta fase agrega archivos de infraestructura, no cambia la app.

**Reglas transversales.** Nombres y config en inglés. Sin secretos hardcodeados, todo
por variable. Commits en inglés, sin push salvo que se pida. Respetar `pyproject.toml`
más `uv.lock` para no bajar la build CUDA de PyTorch.

**Bloque 1, imagen de la API.** `Dockerfile.api` y `.dockerignore` según la sección 2.
Build local. Verificar dentro del contenedor que `import torch` y `import torchvision`
funcionan, y agregar `libgomp1` solo si fallan. Reportar el tamaño real de la imagen.
Punto de control, mostrar el Dockerfile, el `.dockerignore`, el tamaño, y el resultado
del import.

**Bloque 2, imagen del front.** `Dockerfile.front` de dos etapas y la plantilla de
config de Nginx según la sección 3, con upstream y puerto por variable y defaults
locales. Build local. Punto de control, mostrar los dos archivos y que la imagen
construye.

**Bloque 3, compose local.** `docker-compose.yml` con los tres servicios según la
sección 4, volumen nombrado para Postgres y `depends_on` con healthcheck. Punto de
control, correr `docker compose up --build`, recorrer el camino feliz en
`http://localhost:8080`, y probar la persistencia con un reinicio sin borrar el
volumen. Este bloque cierra la Parte A, un entregable Docker completo.

**Bloque 4, Render.** Solo con la Parte A andando. Resolver primero el bloqueo de los
modelos según la sección 5. Después la base gestionada con el esquema adaptado, el
servicio de API, y el servicio de front con el upstream interno y el `PORT` de Render.
Punto de control, la URL pública andando de punta a punta. Parar y avisar en cualquier
paso que dependa de la consola de Render o de credenciales, no inventar valores.
