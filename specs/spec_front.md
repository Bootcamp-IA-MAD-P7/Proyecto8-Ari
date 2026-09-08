# spec_front.md — Consola de sesión (stand-in del consumidor hospitalario)

Documento de diseño para construir el front del servicio de riesgo de ictus.
Lo ejecuta Claude Code por bloques, con puntos de control humanos entre bloques.
Todas las decisiones de esta spec ya están tomadas. Si algo no está definido acá,
no se inventa, se pregunta.

**Encuadre.** El front consume la API del servicio de riesgo de ictus, que ya
está construida, verificada y con tests. Actúa de stand-in de alta fidelidad del
software hospitalario que en producción consumiría la API. Es un banco de pruebas
para la entrega, no el entregable real. El entregable real es la API.

**Convenciones.** Código, nombres de variables y comentarios en inglés. Prosa de
UI en español, registro clínico sobrio. Mensajes de commit en inglés. Nada de
secretos ni de PHI en el navegador.

---

## 1 · Objetivo y alcance

Consola web que recorre la máquina de estados de una sesión de punta a punta
contra los seis endpoints, con una UI que reacciona al `estado` que devuelve el
server.

**En alcance.** Una sola sesión activa por vez, abrir, clasificar tabular,
derivar, subir imagen, clasificar imagen, cerrar, y leer todo por el GET.

**Fuera de alcance.** Autenticación, bandeja de múltiples sesiones, historia
clínica, PACS, y cualquier persistencia en el navegador.

**Fidelidad.** Alta. Imita el comportamiento de un consumidor hospitalario real
llamando a la API. No reconstruye el hospital.

---

## 2 · Stack y arranque

| Punto | Decisión |
|---|---|
| Framework | React con Vite |
| Fetching | `fetch` nativo con un envoltorio delgado por endpoint. NO TanStack Query (una sola sesión y el server como verdad lo vuelven sobre-herramienta) |
| Base URL de la API | variable de entorno de Vite `VITE_API_BASE_URL`, default `http://localhost:8000` |
| Origen del front | `http://localhost:5173` (default de Vite) |
| CORS | ya resuelto en el backend (`CORSMiddleware`, `CORS_ORIGINS` default `http://localhost:5173`). El front pega directo, sin proxy |

**Gotcha del puerto de la API.** El `8000` es el default de uvicorn, es una
inferencia. Confirmarlo al levantar la API y ajustar `VITE_API_BASE_URL` si difiere.

**Gotcha de CORS.** Acceder al front por `http://localhost:5173`, no por
`127.0.0.1:5173`, porque el origen tiene que coincidir literal con el allowlist del
backend.

---

## 3 · Arquitectura de UI — consola gobernada por estado más stepper

Consola con layout master-detail. El server es la única fuente de verdad del
estado. El front lee `estado` del GET y pinta según eso. No lleva contador propio
de en qué paso va.

**Shell** (anclado a la referencia clínica de la sección 7).

- Barra superior de marca en naranja.
- Panel principal con el detalle de la sesión activa.
- Stepper de ciclo que refleja, en solo lectura, en qué punto va la sesión.

**Mapa estado a UI.** Es la ley del render condicional.

| `estado` (lo dice el GET) | Qué muestra la pantalla | Acción disponible | Endpoint |
|---|---|---|---|
| `abierta` | ficha recién abierta, formulario tabular | cargar 6 features | `POST /clasificacion-tabular` |
| `clasificada_tabular` | resultado tabular | tres caminos, derivar a imagen, alta, o derivar especialista | `POST /derivacion` **o** `POST /cierre` |
| `derivada_imagen` | pide subir la TAC | subir imagen | `POST /clasificacion-imagen` |
| `clasificada_imagen` | resultado imagen junto al tabular | dos caminos, alta o derivar especialista | `POST /cierre` |
| `cerrada` | rastro completo y `decision_final`, solo lectura | ninguna | `GET` |

**Aclaración de las acciones.** "Alta" y "derivar a especialista" van las dos a
`POST /cierre` con distinto `decision_final`. "Derivar a imagen" es `POST /derivacion`,
una transición aparte, no un valor de `decision_final`.

**Regla de oro.** La UI solo muestra las acciones que el estado permite. Por eso el
409 casi no debería dispararse. Si igual llega, se muestra el mensaje y se hace un
GET para re-sincronizar con el server, nunca se confía en la copia local.

---

## 4 · Cliente de API

**Patrón general.** Cada acción es un POST. Tras un POST exitoso, el front hace
`GET /sesiones/{id}` y repinta desde el `SesionOut`, que es la fuente de verdad. El
`id_sesion` se captura del `POST /sesiones` (único que lo devuelve) y se sostiene en
memoria para las URLs siguientes.

**Envoltorio.** Una función por endpoint.

| Función | Método y ruta | Body | Éxito | Respuesta |
|---|---|---|---|---|
| `openSession` | `POST /sesiones` | `{ id_paciente }` | 201 | `{ id_sesion, estado }` |
| `classifyTabular` | `POST /sesiones/{id}/clasificacion-tabular` | 6 features | 200 | `{ probability, prediction, threshold, estado }` |
| `refer` | `POST /sesiones/{id}/derivacion` | `{ motivo_derivacion }` | 200 | `{ estado }` |
| `classifyImage` | `POST /sesiones/{id}/clasificacion-imagen` | multipart `file` | 200 | `{ probability, prediction, threshold, estado }` |
| `closeSession` | `POST /sesiones/{id}/cierre` | `{ decision_final }` | 200 | `{ estado }` |
| `getSession` | `GET /sesiones/{id}` | ninguno | 200 | `SesionOut` (10 campos, sección 5) |

**Manejo de errores, forma dual.** El cuerpo del error cambia de forma según el
origen, y hay una trampa real.

| Caso | Forma de `detail` | Qué hace el front |
|---|---|---|
| 422 de Pydantic | array de objetos `{ loc, msg, type, input, ctx? }` | muestra el `msg` junto al campo que indica `loc` |
| 404, 409, 413, 422 de imagen | string simple | muestra el string |
| 5xx | texto plano `Internal Server Error`, NO es JSON | mensaje genérico, sin intentar parsear |

**Regla del manejo de errores.** Mirar el status primero y recién ahí decidir cómo
leer el cuerpo. Un `response.json()` a ciegas sobre un 500 revienta.

---

## 5 · Contrato de datos

Encoda el contrato exacto del backend. La validación del front es guía de UX. El
juez es el server (Pydantic con `extra="forbid"`).

**Apertura.** Body con un solo campo, `id_paciente` (string, requerido).

**Tabular.** Seis campos, ni uno más. Mandar campos de más rechaza toda la request
con 422. `gender` y `work_type` NO existen en el contrato, no crear esos inputs.

| Campo | Tipo | Control UI | Rango o valores |
|---|---|---|---|
| `age` | float | input numérico | 0 a 110 |
| `hypertension` | 0/1 | toggle o radio Sí/No mapeado a 1/0 | 0 o 1 |
| `heart_disease` | 0/1 | toggle o radio Sí/No mapeado a 1/0 | 0 o 1 |
| `avg_glucose_level` | float | input numérico | 40 a 400 |
| `bmi` | float | input numérico | 10 a 100 |
| `smoking_status` | string enum | desplegable | `never smoked`, `smokes`, `formerly smoked`, `Unknown` |

Los `min`/`max` de los inputs son barandas de UX, no reemplazan la validación del
server. Ojo la mayúscula de `Unknown` y los espacios de `never smoked` y
`formerly smoked`, van literales.

**Derivación.** Body con `motivo_derivacion` (string, de 1 a 500 caracteres).
Textarea con contador. Bloquear el envío vacío, un string vacío da 422.

**Imagen.** Multipart, el campo se llama `file`. Aceptados PNG o JPEG, hasta 10 MB,
un solo archivo. Pre-chequeo de tipo y tamaño del lado del cliente como UX. El
server aplica sus cuatro filtros y es el juez.

**Cierre.** Body con `decision_final`, valores `alta` o `derivar_especialista`, nada
más. Dos acciones que mapean a esos dos strings.

**GET `SesionOut`.** Diez campos, siempre presentes en el JSON, `null` cuando no
aplican según el estado.

| Campo | Tipo |
|---|---|
| `id_sesion` | string (uuid) |
| `id_paciente` | string |
| `estado` | string, uno de los cinco |
| `features_tabular` | objeto o null |
| `resultado_tabular` | objeto o null |
| `resultado_imagen` | objeto o null |
| `motivo_derivacion` | string o null |
| `decision_final` | string o null |
| `creada_en` | string (datetime ISO 8601) |
| `actualizada_en` | string (datetime ISO 8601) |

**Resultados.** Tanto `resultado_tabular` como `resultado_imagen` y las respuestas
de las dos clasificaciones tienen la misma forma, `{ probability, prediction,
threshold }`. `probability` es float de 0 a 1, `prediction` es int 0 o 1,
`threshold` es float. No traen etiqueta de texto. El front arma "Riesgo alto"
cuando `prediction` es 1 y "Riesgo bajo" cuando es 0. El `threshold` se muestra tal
cual viene (tabular 0.43, imagen 0.5).

---

## 6 · Seguridad del front, afuera del borde de confianza

- **El server es el juez.** La validación del cliente acompaña la experiencia,
  nunca reemplaza la del server.
- **Cero PHI en el navegador.** No persistir `features_tabular` ni
  `motivo_derivacion` en `localStorage` ni `sessionStorage`, ni loguearlos a
  consola. El estado vive en memoria de la app mientras dura la sesión.
- **Cero secretos** en el código o el navegador. La única config es
  `VITE_API_BASE_URL`.
- **La imagen** se maneja en memoria y se envía como multipart, no se guarda del
  lado del cliente.
- **CORS** ya resuelto en el back. Acceder al front por `localhost:5173` para que el
  origen coincida.

---

## 7 · Directrices visuales

Registro clínico creíble, anclado a una referencia real de software clínico,
ejecutado en versión modernizada. Como Claude Code no ve la imagen de referencia,
acá va descripta en palabras.

**De la referencia se toma.** Layout master-detail, barra superior de marca en
naranja, estado comunicado por color con una barra o badge a la izquierda de la
fila o tarjeta, y la sensación de herramienta clínica seria.

**De la referencia NO se copia.** La densidad apretada, la tipografía chica ni la
saturación alta. Ejecutar más limpio, con más aire, tipografía más grande y
saturación contenida.

**Paleta oficial y roles.**

| Hex | Rol |
|---|---|
| `#FF7A1A` naranja | chrome de marca, barra superior, y acción primaria |
| `#FFB347` ámbar | acento y estado en tránsito (derivada, en curso) |
| `#2F7D32` verde | estado positivo, alta, paso hecho |
| `#A8D5A2` verde claro | fondos suaves, badges tenues |
| `#F6F1E6` crema | fondo de página |

**Token semántico extra.** `#C62828` rojo clínico, único color fuera de la paleta
oficial, y con un solo trabajo, señalar el estado de riesgo alto. Verificar
contraste AA sobre crema y sobre blanco antes de fijarlo, ajustar el tono si no
pasa. Definirlo como variable CSS aparte de los tokens de marca.

**Presentación del riesgo, criterio de no sobreafirmar.**

- El texto y los números al frente. Etiqueta "Riesgo alto" o "Riesgo bajo", más
  `probability` y `threshold`.
- El color solo refuerza. El rojo `#C62828` entra como barra o badge contenido en la
  tarjeta del resultado tabular cuando `prediction` es 1. Nunca pantalla roja, ni
  rojo en chrome, bordes o decoración.
- Una línea aclaratoria fija en la tarjeta de resultado. Es una orientación de criba
  previa a la consulta, no un diagnóstico. Aplica al tabular, que es una criba, y a
  la imagen, que es un prototipo.

**Stepper de ciclo.** Refleja los cinco estados en solo lectura, injertado sobre el
shell master-detail.

---

## Bloque de arranque para Claude Code

Modo construcción, spec-driven. El reconocimiento del backend ya está hecho en
`specs/reconocimiento_backend.md`, leerlo primero, es el contrato real. No modificar
el backend. Construir por bloques, parar en cada punto de control y mostrar antes de
seguir.

**Reglas transversales.** Código, nombres y comentarios en inglés. Prosa de UI en
español. Sin secretos ni PHI en el navegador. El server es el juez. Commits en
inglés, sin push salvo que se pida.

**Bloque 0, scaffold.** Proyecto Vite más React, estructura de carpetas,
`VITE_API_BASE_URL` con default `http://localhost:8000`, un `.env.example`, y el
`.gitignore` del front. Punto de control, mostrar la estructura y que arranca en
`5173`.

**Bloque 1, cliente de API.** Envoltorio de `fetch`, las seis funciones, el manejo
de errores de forma dual incluida la trampa del 5xx en texto plano, el patrón POST y
después GET, y la captura y sostén del `id_sesion`. Punto de control, mostrar el
módulo y una prueba manual contra la API real (apertura más GET).

**Bloque 2, shell y máquina de estados.** Consola master-detail, stepper, render
condicional por `estado` según el mapa de la sección 3, y los tokens de color como
variables CSS. Todavía sin lógica de formularios, solo el shell reaccionando al
estado. Punto de control.

**Bloque 3, formularios y flujos.** Tabular de seis campos, derivación con textarea y
contador, subida de imagen con pre-chequeo, y cierre con dos acciones, todo cableado
al cliente y al patrón POST y después GET. Punto de control, recorrer el camino feliz
completo de punta a punta.

**Bloque 4, pulido visual y tarjeta de riesgo.** Aplicar las directrices de la
sección 7, la tarjeta de resultado con el rojo `#C62828` contenido para riesgo alto,
la verificación de contraste, y la línea de criba. Punto de control.

**Aceptación.** Chequeo manual, sin tests automáticos por el deadline. Recorrer el
camino feliz con imagen y el de alta directa. Forzar un 422 con un feature fuera de
rango y ver el mensaje junto al campo. Observar el manejo del 409. Los tests
automáticos del front quedan fuera de alcance por tiempo, anotado como mejora futura.
