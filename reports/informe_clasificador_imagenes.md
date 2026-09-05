# Informe del clasificador de imágenes — TAC cerebral (Normal vs Stroke)

## 1. Contexto

Este informe cubre el segundo componente del Proyecto 8 (Nivel Experto): una red convolucional sobre TAC cerebral y su comparación con el modelo tabular clásico. El objetivo es clasificar tomografías axiales computarizadas de cerebro en dos clases, `Normal` y `Stroke`, como una segunda señal de apoyo diagnóstico, independiente del modelo tabular documentado en `reports/informe_modelo_tabular.md`.

Es importante fijar el estado del artefacto antes de leer cualquier métrica: el clasificador de imágenes es un **prototipo en desarrollo, no un sistema productivo**. Se entrenó con un backbone congelado, en CPU, con un único split train/test y sin validación externa; las secciones 5 y 8 detallan por qué estas decisiones son razonables para un prototipo pero insuficientes para un despliegue clínico.

## 2. Datos

El dataset (`data/raw/Brain_Data_Organised`) contiene 2501 imágenes TAC distribuidas en dos carpetas, `Normal` con 1551 imágenes y `Stroke` con 950, una proporción de 1,63:1 (62,0 % / 38,0 %). Este desbalance es mucho más moderado que el 1:19 del dataset tabular, y ese contraste importa para leer correctamente los resultados de la sección 6: aquí la clase minoritaria (`Stroke`, 950 casos) tiene un orden de magnitud más de ejemplos que los 248 ictus del dataset tabular.

Una auditoría de homogeneidad sobre las 2501 imágenes confirma que el 100 % está en modo `L` (escala de grises, un canal) con tamaño uniforme de 650×650 píxeles, y que no hay ninguna imagen ilegible o corrupta (0 sobre 2501). Esta homogeneidad es una ventaja real para el preprocesado: no hace falta manejar tamaños ni modos de color heterogéneos antes de entrar al pipeline de transforms.

El dataset procede de Kaggle (`afridirahman/brain-stroke-ct-image-dataset`), con licencia `unknown`. El repositorio no incluye archivo de metadata, README de datos ni licencia dentro de `data/raw/` que confirme el origen o los términos de uso, de modo que la licencia se mantiene como `unknown` y se señala como limitación explícita en la sección 8: sin licencia confirmada, no está claro qué usos del dataset están permitidos más allá de este prototipo.

La figura `figures/09_balance_y_ejemplos_tac.png` muestra el balance de clases junto con un ejemplo de cada una, tomados directamente de las carpetas del dataset.

## 3. Preprocesado

El pipeline de transforms usa la API `v2` de `torchvision`, encadenada en un único `Compose` reutilizado tanto en entrenamiento como en inferencia: `Resize((224, 224))` para adaptar cada TAC de 650×650 al tamaño de entrada de ResNet-50, sin recorte (para no perder una lesión que pudiera ubicarse cerca del borde); `Grayscale(num_output_channels=3)` para replicar el canal gris en tres canales idénticos (`r == g == b`), requisito de la primera capa convolucional de la red, sin que esto aporte información cromática real; `ToImage()` seguido de `ToDtype(torch.float32, scale=True)` para convertir a tensor con el escalado explícito de 0-255 a 0-1; y `Normalize` con la media y desviación estándar de ImageNet (`[0.485, 0.456, 0.406]` / `[0.229, 0.224, 0.225]`), heredadas del preentrenamiento y no estimadas sobre este dataset. Se separan `ToImage` + `ToDtype` en lugar de usar el `ToTensor` clásico porque `ToTensor` está deprecado desde torchvision 0.16 y su reescalado implícito de valores es fuente de errores silenciosos, por lo que la API `v2` explícita es la opción más segura.

El dataset se carga con `ImageFolder`, que asigna las etiquetas alfabéticamente: `Normal` → 0, `Stroke` → 1. `Stroke` queda así como la clase positiva (índice 1), y es sobre ella que se mide el recall que gobierna todo el proyecto.

El split es 80/20 mediante `train_test_split` sobre los índices del dataset, estratificado por `dataset.targets` con `random_state=42`, envuelto después en objetos `Subset` de PyTorch. El resultado es 2000 imágenes de train y 501 de test. El balance de clases se mantiene razonablemente estable en ambos lados —train queda en 1,63:1 (1240 `Normal` / 760 `Stroke`) y test en 1,64:1 (311 `Normal` / 190 `Stroke`)— pero conviene ser preciso: `train_test_split` con `stratify` fuerza esta proporción como consecuencia del muestreo estratificado, no es un resultado que se "verificó" de forma independiente después del hecho; el chequeo posterior con `Counter` (celda 14 del notebook) confirma que el estratificado funcionó como se esperaba, no añade una garantía adicional.

Los `DataLoader` usan `batch_size=32` (63 lotes de train, 16 de test) y no fijan `num_workers`, por lo que toman el valor por defecto de PyTorch, 0. Un lote de entrenamiento verificado tiene la forma `[32, 3, 224, 224]`, coherente con el pipeline de transforms.

## 4. Arquitectura y decisiones

El modelo es una ResNet-50 preentrenada en ImageNet (`ResNet50_Weights.DEFAULT`) usada como extractor de features fijo: todos los parámetros del backbone se congelan (`requires_grad=False`) y la capa final `fc`, originalmente pensada para 1000 clases de ImageNet, se reemplaza por una `Linear(2048, 2)`. La verificación de qué parámetros quedan entrenables confirma exactamente `fc.weight` y `fc.bias`, nada más: todo el resto de la red actúa como extractor de características fijo durante el entrenamiento.

La justificación de esta elección es doble: con apenas 2501 imágenes no alcanza para entrenar desde cero una red convolucional profunda de millones de parámetros, y el entrenamiento corre en CPU (sin GPU disponible: `torch.cuda.is_available()` devuelve `False`, con `torch 2.14.0+cpu` y `torchvision 0.29.0+cpu`), por lo que congelar el backbone reduce el cómputo real a entrenar solo la cabeza. Una consideración adicional —preferir una CNN sobre un Vision Transformer porque la CNN aporta un sesgo inductivo convolucional que una ViT necesitaría un dataset mucho más grande para aprender por sí sola— es una afirmación de dominio plausible sobre el comportamiento general de CNNs frente a ViTs con pocos datos, pero sin fuente citable dentro de este proyecto, y se marca aquí como tal.

El entrenamiento usa `CrossEntropyLoss` y el optimizador `Adam` restringido a los parámetros de `fc` (`optim.Adam(model.fc.parameters(), lr=1e-3)`), coherente con que solo esa capa es entrenable. Cada época tomó entre 8,9 y 11,6 minutos según los tiempos registrados por `tqdm` en el notebook, del orden de 11 minutos por época en promedio, sobre CPU.

## 5. Entrenamiento

El entrenamiento se hizo en dos fases sobre el mismo objeto de modelo, sin reiniciar pesos entre una y otra.

**Fase 1 — 3 épocas, sin ponderar clases.** La pérdida de entrenamiento bajó de 0,6368 a 0,5727 y a 0,5315 en las tres épocas. La evaluación sobre el test (501 imágenes) dio una matriz de confusión de `[[290, 21], [103, 87]]`, con un recall de la clase `Stroke` de apenas 0,46: de 190 ictus reales en el test, el modelo detecta 87 y pierde 103 como falsos negativos, el error clínicamente caro en este dominio. La accuracy de esa misma evaluación es 0,75, una cifra que por sí sola oculta el problema real: con 311 de los 501 casos de test siendo `Normal`, un modelo que ignorase por completo la clase `Stroke` ya arrancaría desde una accuracy alta.

El recall tan bajo admite dos causas, presentadas aquí como interpretación del equipo y no como una conclusión textual del notebook: pocas épocas (la pérdida todavía bajaba activamente en la tercera) y el desbalance de clases (el modelo, al dudar, apuesta por la clase mayoritaria).

**Fase 2 — 7 épocas adicionales, con `class_weight`.** Se introdujo un peso por clase inverso a su frecuencia, `[0,806, 1,316]` (`Stroke` pesa aproximadamente 1,6 veces más que `Normal` en la función de pérdida), y se continuó entrenando el mismo modelo 7 épocas más. La pérdida —ya no comparable de forma directa con la de la fase 1, porque cambió la función que se está minimizando al introducir los pesos— bajó de 0,5206 a 0,4047 de forma consistente en las 7 épocas (figura `figures/10_curva_loss_fase1_fase2.png`, que marca el punto de cambio de función de pérdida entre ambas fases).

La evaluación final sobre el mismo test da una matriz de confusión de `[[243, 68], [34, 156]]`: el recall de `Stroke` sube de 0,46 a 0,82, con los falsos negativos bajando de 103 a 34. El trade-off es el esperado y buscado deliberadamente: la precisión de `Stroke` baja de 0,81 a 0,70 y el recall de `Normal` baja de 0,93 a 0,78 (más falsas alarmas), a cambio de atrapar una proporción mucho mayor de los ictus reales — exactamente el intercambio que la prioridad clínica del proyecto (evitar falsos negativos) pide aceptar.

## 6. Evaluación

Las métricas por clase del modelo final (fase 2), a partir de la matriz de confusión `[[243, 68], [34, 156]]` sobre las 501 imágenes de test (311 `Normal`, 190 `Stroke`): recall de `Stroke` 0,82, precisión de `Stroke` 0,70; recall de `Normal` 0,78, precisión de `Normal` 0,88; accuracy global 0,80 — los mismos valores que reporta `classification_report` en la celda 25 del notebook.

La figura `figures/11_matriz_confusion_fase2.png` muestra esta matriz; `figures/12_matriz_confusion_fase1.png` muestra la de la fase 1 (recall `Stroke` 0,46) al lado, para que el efecto del `class_weight` sea visualmente comparable entre ambas fases.

Leído en pacientes: de los 190 TAC con ictus real en el test, el modelo detecta 156 y pierde 34. De los 311 TAC normales, marca 68 como falsa alarma y deja 243 correctamente identificados. El umbral de decisión usado en `src/image.py` es 0,5 sobre la probabilidad de `Stroke` obtenida por softmax, lo cual —al tratarse de una clasificación de 2 clases— equivale exactamente a tomar el argmax de los logits: es el mismo criterio de decisión que ya se usó para calcular la matriz de confusión de arriba en el notebook, no un umbral ajustado aparte ni buscado sobre una curva precisión-recall (a diferencia del modelo tabular, donde el umbral 0,43 sí se buscó explícitamente).

## 7. Comparación con el modelo clásico

El Nivel Experto del proyecto pide comparar este clasificador de imágenes con el modelo tabular clásico documentado en `reports/informe_modelo_tabular.md`. La comparación honesta empieza por dejar clara su principal limitación: **no son comparables de forma directa**. Miden entradas distintas (variables clínicas y demográficas del paciente contra una imagen de TAC cerebral), sobre datasets distintos con desbalances distintos (1:19 en el tabular contra 1,63:1 en el de imágenes), evaluados sobre conjuntos de test distintos y de tamaños distintos (997 pacientes con 50 ictus reales, contra 501 imágenes con 190 ictus reales). Una cifra de recall más alta en un test no implica que ese modelo sea "mejor": implica que resuelve un problema de clasificación distinto, con una tarea de separabilidad distinta.

Con esa advertencia por delante, la tabla siguiente pone lado a lado las cifras de cada uno en su propio test, únicamente como referencia de lectura conjunta:

| | Modelo tabular (logística) | Clasificador de imágenes (CNN) |
|---|---|---|
| Entrada | Variables clínicas/demográficas del paciente | TAC cerebral (imagen) |
| Test | 997 pacientes, 50 con ictus | 501 imágenes, 190 con ictus |
| Recall (clase Stroke/ictus) | 0,900 | 0,821 |
| Precisión (clase Stroke/ictus) | 0,127 | 0,696 |
| Accuracy | 0,686 | 0,796 |
| Umbral de decisión | 0,43 (buscado sobre curva OOF) | 0,5 (argmax, no ajustado) |
| Estado | Congelado, con receta de inferencia en `src/tabular.py` | Prototipo, no productivo |

La precisión mucho más alta del clasificador de imágenes (0,696 contra 0,127) no debería leerse como una superioridad del modelo de imágenes: es en gran medida un reflejo de que su dataset tiene un desbalance mucho menos extremo (1,63:1 contra 1:19), lo que hace la tarea de clasificación estructuralmente más fácil en términos de precisión-recall, independientemente del algoritmo usado en cada caso — la misma lógica del "techo de datos" documentada en el informe tabular.

La arquitectura de producto, tal como está implementada en `src/predict.py`, evita precisamente el error de fusionar estas dos señales en un único número: todos los pacientes pasan por el modelo tabular (siempre disponible, porque solo requiere datos clínicos básicos), y únicamente quienes cuentan con un TAC pasan además por el clasificador de imágenes; las dos predicciones —cada una con su propia probabilidad y su propio umbral— se devuelven por separado, sin combinarse en un score único. La razón, confirmada en el propio código (`predict_patient` en `src/predict.py` devuelve `{"tabular": ..., "image": ...}` sin ningún paso de fusión), es que no hay evidencia ni dato en este proyecto que justifique un peso de combinación entre ambas señales; se muestran las dos y es el criterio clínico el que las integra.

## 8. Limitaciones

El entrenamiento corrió enteramente en CPU, sin GPU disponible, lo que impuso restricciones de tiempo reales sobre cada decisión de diseño (backbone congelado, pocas épocas, sin validación cruzada) y no fue una elección libre de exploración.

El backbone permanece congelado durante todo el entrenamiento: solo la capa `fc` final se ajusta a datos de TAC cerebral, mientras que todas las capas convolucionales conservan exactamente los pesos aprendidos sobre ImageNet, un dominio de imágenes naturales muy distinto al de una tomografía médica. Esto es una limitación de capacidad real: el modelo no puede aprender features específicas de TAC cerebral, solo puede recombinar linealmente las features genéricas que ResNet-50 ya trae. Un fine-tuning parcial (descongelando las últimas capas convolucionales) es una vía de mejora natural, no explorada en este prototipo.

No existe un conjunto de validación separado del test: el notebook solo define `train_loader` y `test_loader`. Esto se conecta con la limitación metodológica más importante del prototipo. La secuencia real de entrenamiento fue: se entrena la fase 1, se evalúa sobre `test_loader` (recall `Stroke` 0,46), y es a partir de ese resultado de test que se decide introducir `class_weight` y entrenar 7 épocas más; después se vuelve a evaluar sobre el mismo `test_loader` (recall 0,82). El conjunto de test se miró dos veces, y la segunda decisión de diseño (agregar `class_weight`) estuvo directamente informada por el resultado de la primera medición sobre test. Es una forma de fuga de información del investigador hacia el test —no leakage de datos, en el sentido de que el modelo no vio esas imágenes durante el entrenamiento, sino leakage de decisión: el test dejó de ser una medición ciega y pasó a influir en una elección de diseño—. Conviene matizarlo en dos direcciones: por un lado, `class_weight` era justificable *a priori* por el desbalance 1,63:1 conocido desde la auditoría de datos (sección 2), de modo que la decisión no dependía en rigor de haber visto el test; por otro, tal como se ejecutó, el resultado de test sí disparó el cambio, así que la cifra de recall 0,82 no es una estimación tan limpia de generalización como lo sería si `class_weight` se hubiera fijado de antemano o validado en un conjunto aparte. Se registra como limitación real del prototipo.

La medición se hace con un único split train/test (80/20, semilla 42) en lugar de validación cruzada, que habría dado una estimación más estable del recall con su propia variabilidad entre folds —como sí se hizo en el modelo tabular—. La razón es de tiempo de cómputo: con un promedio del orden de 11 minutos por época sobre CPU y 10 épocas para llegar al resultado final del prototipo (3 de fase 1 más 7 de fase 2), una validación cruzada de 5 folds habría requerido repetir ese entrenamiento completo cinco veces, del orden de 7 a 9 horas de cómputo solo para esa validación, tiempo no disponible en este entorno de CPU.

La licencia del dataset de origen no pudo confirmarse (ver sección 2): se reporta como `unknown` porque no hay documentación disponible en el repositorio que la aclare, ni un README de datos ni un archivo de metadata.

Por último, y aplicable a todo el informe: el modelo es un **prototipo en desarrollo, no productivo**. No se validó sobre datos de otro hospital o de otra procedencia (todos los TAC vienen de la misma fuente), no se sometió a revisión clínica, y las limitaciones anteriores —backbone congelado, sin validación cruzada, con la fuga de decisión ya señalada— hacen que sus métricas deban leerse como una primera demostración de viabilidad, no como una evaluación lista para respaldar una decisión médica real.

## 9. Reproducibilidad

El entorno usa `torch 2.14.0+cpu` y `torchvision 0.29.0+cpu`, sin GPU (`torch.cuda.is_available()` devuelve `False` en el notebook). El split train/test (2000/501) está fijado con `random_state=42` en `train_test_split`, por lo que la partición de imágenes es reproducible de forma exacta. El propio entrenamiento, sin embargo, no fija una semilla de PyTorch (no hay ninguna llamada a `torch.manual_seed` en el notebook): la inicialización de la capa `fc` nueva y el orden de barajado de `train_loader` (`shuffle=True`) no están controlados por semilla, por lo que reejecutar el notebook desde cero reproduciría la misma partición de datos pero no necesariamente los mismos pesos entrenados ni exactamente las mismas cifras de recall reportadas aquí. La reproducibilidad de los números de este informe depende, en la práctica, del `state_dict` ya guardado en `models/cnn_resnet50_stroke.pth` (del orden de 90-95 MB en disco), no de la posibilidad de volver a entrenar y obtener el mismo resultado.

La receta de inferencia congelada vive en `src/image.py`: reconstruye la arquitectura (ResNet-50 sin pesos de ImageNet, `weights=None`, ya que el `state_dict` los sobrescribe por completo), aplica exactamente el mismo `Compose` de transforms `v2` usado en entrenamiento, y calcula la probabilidad de `Stroke` con softmax sobre los logits antes de aplicar el umbral 0,5. `src/predict.py` es el orquestador que combina esta señal con la del modelo tabular (`src/tabular.py`) sin fusionarlas, tal como se describe en la sección 7: el tabular corre siempre, la imagen solo si hay un TAC disponible para ese paciente.
