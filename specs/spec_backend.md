# spec_backend.md — Servicio ictus (backend)

Documento de especificación para construir el backend del predictor de riesgo de ictus del Hospital F5. Fuente de verdad para Claude Code. Se construye a partir de las decisiones de diseño ya tomadas. No se improvisa fuera de lo aquí escrito.

---

## 0 · Bloque de arranque (estado del repo)

El repositorio ya existe. La API se construye dentro de él, no desde cero.

- Python 3.12, gestionado con uv. Declarado en `.python-version` y en `pyproject.toml` (`requires-python = ">=3.12,<3.14"`).
- Modelos ya entrenados en `models/`. No se reentrenan.
  - `models/logistic_stroke.joblib` — pipeline tabular.
  - `models/smoking_encoder.joblib` — encoder de `smoking_status`.
  - `models/cnn_resnet50_stroke.pth` — red de imagen (ResNet-50, ~94 MB).
- Lógica de modelos ya escrita en `src/`. Se usa tal cual, no se reescribe.
  - `src/tabular.py` expone `predict_tabular(patient: dict) -> dict`.
  - `src/image.py` expone `predict_image(image_path) -> dict`.
  - `src/predict.py` expone `predict_patient(patient, image_path=None) -> dict`, orquestador.
- Punto de entrada a los modelos: la API usa las funciones de `src/`. Ver nota en la sección 5 sobre llamadas separadas.
- Dependencias declaradas en `pyproject.toml`. Claude Code suma las de la API (FastAPI, uvicorn, conector de Postgres, pieza para recibir archivos subidos).

Punto de atención (no bloquea el backend, se resuelve en la spec de despliegue): la carpeta `models/` está en `.gitignore` y no viaja con el repo. Al construir el contenedor habrá que incorporarla aparte. La decisión tomada es copiarla dentro de la imagen al construir, con la precondición de que exista en disco en ese momento. Esto pertenece a `spec_deploy.md`, no a esta spec.

---

## 1 · Contexto y objetivo

Servicio de backend que asiste la decisión clínica de riesgo de ictus. Expone dos modelos ya entrenados, un clasificador tabular de riesgo y un clasificador de imagen sobre tomografía cerebral, a través de una API. El servicio no diagnostica. Produce una clasificación de apoyo que el doctor usa para decidir.

El servicio es una pieza que se integra a un sistema hospitalario existente. En producción, quien lo consume es el software del hospital. Para esta entrega, un front propio actúa de stand-in de ese consumidor, para demostrar el flujo completo. El front se especifica aparte.

La unidad de trabajo es la sesión, identificada por un `id_sesion`. Una sesión recorre una máquina de estados, desde que se abre con la ficha del paciente hasta que el doctor la cierra. El `id_paciente` viaja como referencia de correlación, no como llave para buscar datos.

---

## 2 · Stack y restricciones

- Lenguaje: Python 3.12, gestionado con uv.
- API: FastAPI, con validación de entrada vía Pydantic.
- Base de datos: PostgreSQL en su propio contenedor.
- Modelos: ya entrenados y serializados. Se cargan, no se reentrenan.
- Punto de entrada a los modelos: las funciones de `src/`. La API llama a `predict_tabular` y `predict_image` por separado, según el estado de la sesión (ver sección 5).
- Conexión a la base de datos: por variable de entorno. Las credenciales de Postgres nunca van escritas en el código.

Restricción dura: la receta de preprocesado del tabular no se toca ni se reescribe. `src/tabular.py` fija con precisión de código el orden de columnas (`FINAL_COLUMNS`) y el umbral con el que se entrenó el modelo (0.43). Se usa tal como está. Igual criterio para `src/image.py` (umbral 0.5, pipeline de transformación v2).

---

## 3 · Fuera de alcance

Claude Code no construye nada de esto, porque vive del otro lado del borde de confianza o fue descartado por diseño.

- El front. Se especifica en su propia spec.
- El empaquetado Docker, docker-compose, Dockerfile, secretos, despliegue. Se especifica en `spec_deploy.md`, aparte y posterior.
- La historia clínica del paciente. Es del sistema del hospital. El servicio no escribe en ella. El hospital lee vía `GET /sesiones/{id}` y vuelca a la historia desde su lado.
- El almacenamiento de la imagen médica. Vive en el sistema de imágenes del hospital. El servicio clasifica la imagen y la descarta.
- El alta clínica. Es una acción del sistema hospitalario. El servicio solo cierra su propia sesión.
- La autenticación pública, login, gestión de usuarios. El servicio vive dentro de un borde interno. La autenticación servicio a servicio se diseña como evolución futura, no se implementa ahora.
- El borrado de sesiones. No hay endpoint DELETE. Un dato mal cargado se corrige rellamando al endpoint correspondiente.
- El reentrenamiento o ajuste de los modelos. Se cargan tal como están.

---

## 4 · Modelo de datos

Una sola tabla, `sesiones`. Guarda el rastro de auditoría de la sesión, no historiales clínicos. Los valores nulos codifican en qué parte de la máquina de estados va la sesión.

| Columna | Tipo | Nulo | Qué guarda |
|---|---|---|---|
| `id_sesion` | UUID | no | clave primaria, la genera la API |
| `id_paciente` | texto | no | referencia del paciente, viene en la ficha |
| `estado` | texto | no | estado actual de la máquina |
| `features_tabular` | JSON | sí | los seis campos clasificados. Contiene PHI |
| `resultado_tabular` | JSON | sí | probability, prediction, threshold |
| `resultado_imagen` | JSON | sí | probability, prediction, threshold, o nulo |
| `motivo_derivacion` | texto | sí | justificante del doctor, texto libre, tope 500 caracteres. Puede contener PHI |
| `decision_final` | texto | sí | `alta` o `derivar_especialista`, o nulo |
| `creada_en` | timestamp | no | cuándo se abrió |
| `actualizada_en` | timestamp | no | último cambio |

No hay columna para la imagen. La imagen no se almacena. Solo se guarda su resultado en `resultado_imagen`.

Estados válidos de `estado`: `abierta`, `clasificada_tabular`, `derivada_imagen`, `clasificada_imagen`, `cerrada`.

---

## 5 · Contratos de endpoints

Seis endpoints. Cinco POST que disparan transiciones de estado, un GET que lee sin cambiar nada. Named actions, cada endpoint custodia su propia precondición de estado del lado del servidor. Una transición desde un estado inválido responde 409.

Nota sobre los modelos: aunque `src/predict.py` ofrece una llamada conjunta (`predict_patient`), la API no la usa entera. Llama a `predict_tabular` en el endpoint tabular y a `predict_image` en el de imagen, por separado, respetando que las dos clasificaciones ocurren en momentos distintos de la sesión.

### POST /sesiones
Abre una sesión.
- Entra: `id_paciente`.
- Sale: `id_sesion` (generado por la API, UUID) y `estado = abierta`.
- Errores: 422 si falta o es inválido el `id_paciente`.
- Precondición: ninguna.

### POST /sesiones/{id}/clasificacion-tabular
Clasifica el riesgo tabular.
- Entra: `id_sesion` en la ruta. En el cuerpo, los seis campos, todos obligatorios.
  - `age` — número. Rango clínico (propuesto 0 a 120, a confirmar por Ari).
  - `hypertension` — 0 o 1 (el front lo ofrece como Sí/No).
  - `heart_disease` — 0 o 1 (el front lo ofrece como Sí/No).
  - `avg_glucose_level` — número, mg/dl. Rango clínico (propuesto 40 a 400, a confirmar por Ari).
  - `bmi` — número. Rango clínico (propuesto 10 a 100, a confirmar por Ari).
  - `smoking_status` — una de: `never smoked`, `smokes`, `formerly smoked`, `Unknown`.
- Sale: `probability`, `prediction`, `threshold` (de `predict_tabular`), y `estado = clasificada_tabular`.
- Errores: 404 si la sesión no existe. 409 si no está en `abierta`. 422 si falta un campo, tiene tipo equivocado, o cae fuera de rango.
- Precondición: estado `abierta`.
- No se aceptan campos extra (por ejemplo gender o work_type). Solo los seis.

### POST /sesiones/{id}/derivacion
El doctor deriva a imagen.
- Entra: `id_sesion` en la ruta. En el cuerpo, `motivo_derivacion` (texto libre, tope 500 caracteres).
- Sale: `estado = derivada_imagen`.
- Errores: 404 si la sesión no existe. 409 si no está en `clasificada_tabular`. 422 si el motivo excede el tope.
- Precondición: estado `clasificada_tabular`.

### POST /sesiones/{id}/clasificacion-imagen
Clasifica la imagen de tomografía.
- Entra: `id_sesion` en la ruta. En el cuerpo, un archivo de imagen subido.
- Sale: `probability`, `prediction`, `threshold` (de `predict_image`), y `estado = clasificada_imagen`.
- Errores: 404 si la sesión no existe. 409 si no está en `derivada_imagen`. 413 o 422 si el archivo no pasa los filtros de la sección 6.
- Precondición: estado `derivada_imagen`.
- Manejo del archivo: pasa los cuatro filtros de la sección 6, se guarda en un archivo temporal solo para pasarle la ruta a `predict_image`, y se borra siempre al terminar, incluso si la clasificación falla. La imagen no se persiste.

### POST /sesiones/{id}/cierre
Cierra la sesión.
- Entra: `id_sesion` en la ruta. En el cuerpo, `decision_final`, una de: `alta`, `derivar_especialista`.
- Sale: `estado = cerrada`.
- Errores: 404 si la sesión no existe. 409 si no está en `clasificada_tabular` ni en `clasificada_imagen`. 422 si `decision_final` no es una de las dos opciones.
- Precondición: estado `clasificada_tabular` o `clasificada_imagen`. Acepta los dos caminos al cierre, con imagen o alta directa.

### GET /sesiones/{id}
Lee la sesión completa.
- Entra: `id_sesion` en la ruta.
- Sale: la sesión completa, estado, resultados, features, decisión, marcas de tiempo.
- Errores: 404 si la sesión no existe.
- Precondición: ninguna. No cambia nada.

---

## 6 · Seguridad transversal

Principio rector: mínimo privilegio. El servicio puede hacer exactamente lo que su tarea necesita y nada más. Sin acceso a historiales, sin escritura en la historia clínica, sin almacenar imágenes.

Validación de entrada. Toda entrada se valida del lado del servidor con Pydantic, antes de tocar el modelo o la base. Nunca se confía en el cliente, aunque el front use desplegables y deshabilite botones.
- Tabular: seis campos obligatorios, tipos correctos, rangos clínicos, categorías dentro del conjunto permitido.
- Cierre: `decision_final` solo `alta` o `derivar_especialista`.
- Justificante: texto libre con tope de 500 caracteres.

Máquina de estados como defensa. Cada endpoint valida su precondición de estado del lado del servidor. Una transición desde un estado que no la permite se rechaza con 409. La regla clínica la hace cumplir la estructura, no la confianza en quien llama. En particular, cargar imagen solo es posible desde `derivada_imagen`.

Subida de imagen. Cuatro filtros en orden, y el archivo debe pasar los cuatro.
1. Límite de tamaño. Rechaza con 413 si supera el máximo (a fijar, por ejemplo 10 MB). Corta antes de leer el archivo entero.
2. Tipo permitido. Solo formatos de imagen de una lista cerrada (por ejemplo PNG y JPEG).
3. Contenido real. Verifica que los bytes sean de verdad una imagen, no solo la etiqueta del archivo.
4. Nombre seguro. La API genera un nombre propio. No usa el nombre que trae el archivo.
Tras clasificar, la imagen temporal se borra siempre.

Datos sensibles en reposo. Dos columnas contienen PHI, `features_tabular` y `motivo_derivacion`. No se escriben en logs, no se exponen más allá del GET. Son las primeras a proteger cuando se asegure la base.

Dirección del borde. El servicio solo expone y guarda lo suyo. El hospital lee vía GET y escribe en sus propios sistemas. Ninguna llamada sale del servicio hacia la historia clínica ni hacia el sistema de imágenes.

Secretos. Las credenciales de Postgres viven como variables de entorno, fuera del repositorio. El detalle de configuración se completa en `spec_deploy.md`.

---

## 7 · Criterios de aceptación

El backend está listo cuando todo lo siguiente es verificable y da verdadero.

Funcionales.
- Se puede recorrer una sesión entera de punta a punta: abrir, clasificar tabular, derivar, clasificar imagen, cerrar.
- Las dos predicciones se devuelven por separado, nunca fundidas en un veredicto único.
- El camino de alta directa, sin imagen, también cierra la sesión.

De estado y validación.
- Una transición desde un estado inválido devuelve 409.
- Una entrada mal formada devuelve 422.
- Cargar imagen sin haber derivado se rechaza.

De seguridad y datos.
- La imagen no queda almacenada tras clasificar.
- Los datos de la sesión persisten en Postgres y sobreviven a un reinicio.
- Las credenciales no están en el código.

---

## Pendientes a confirmar por Ari antes o durante la construcción

- Rangos clínicos exactos de `age`, `avg_glucose_level` y `bmi`. Los valores propuestos en la sección 5 son provisionales y necesitan validación de dominio.
- Tamaño máximo exacto del archivo de imagen en la sección 6.
