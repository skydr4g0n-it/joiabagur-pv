# HU-AIENG-028: Revisión humana de los perfiles de IA — la pantalla que convierte una promesa del diseño en dos números medidos

## Formato estándar

**Como** administrador del sistema,
**quiero** revisar por lotes lo que la IA ha afirmado sobre cada pieza del catálogo —con el texto de origen delante, la confianza y la procedencia de cada campo, y sin tener que mirar los 1.200 productos—,
**para** que el sistema pueda declarar con datos **cuánto se equivoca su extractor y cuánto cuesta corregirlo**, en vez de afirmarlo sin evidencia.

---

## Descripción

El §7.8 del diseño promete una **revisión híbrida**: lo que un modelo infiere sobre un atributo
sensible pasa por una persona, lo que sale de una regla determinista no. El §11.5 promete dos
números que salen de ahí —**tasa de corrección por campo** y **tiempo medio de revisión**— y el §16
los pide como casilla de entrega. El §15 declara, como limitación 2, que *«solo el 12-15 % de los
perfiles está revisado por humanos»*.

**Hoy los tres son afirmaciones sin respaldo.** Medido contra el Postgres local el 2026-09-12:

| `ReviewStatus` | `ReviewOrigin` | perfiles | con revisor | con cronómetro |
|---|---|---:|---:|---:|
| `Approved` | `AutoBulk` | **1.168** | 0 | 0 |
| `Rejected` | `AutoBulk` | **32** | 0 | 0 |

Ni una sola fila revisada por una persona, ni un solo tiempo medido. La vía revisada del §7.8 **no
existe**, y sin ella el §11.5 ya avisaba: *«no existen sin la vía revisada»*.

Esta historia construye el instrumento **y lo usa**. Su entregable no es una pantalla: son dos
números, y la pantalla es lo que hay que construir para obtenerlos.

### El problema que la ficha del plan no vio: el enrutado híbrido no acota nada

La ficha de C28 se apoya en que la decisión 5 reduce la cola de revisión. **Sobre este corpus no la
reduce**, y está medido: de los cuatro campos que el extractor produce, **`size_label` es el único
que marca alguna vez `rule`**.

| campo | `rule` | `inferred` | ausente |
|---|---:|---:|---:|
| `size_label` | **539** | 0 | 661 |
| `piece_type` | 0 | **1.173** | 27 |
| `materials` | 0 | **1.200** | 0 |
| `stone_type` | 0 | **629** | 571 |

La política *«sensible inferido → revisión; sensible por regla → no»* se traduce, sobre estos datos,
en que **el 100 % de los productos entra en la cola** con dos o tres campos sensibles cada uno. El
mecanismo está bien construido; su efecto de filtrado es nulo.

> **Consecuencia:** quien decide qué se revisa tiene que ser un **criterio de muestreo explícito**, y
> ése es el trabajo de diseño de esta historia. Sin él, la tasa de corrección que se publique no es
> interpretable.

### La confianza es un escalón de evidencia, y es ciega a la mitad de los errores

[`enrichment/confidence.py`](../../../ai-service/src/jbg_ai/enrichment/confidence.py) dice en su
primera línea *«The model's own score is never copied»*, y produce **cuatro valores**, no un continuo:

| valor | significado |
|---|---|
| `1,00` | regla determinista (solo talla) |
| `0,85` | **la frase del vocabulario aparece literalmente** en nombre + descripción |
| `0,45` | el modelo afirmó un valor **cuya frase no está en el texto** |
| `0,20` | ausente (`[]` o `null`) |

Es una buena decisión —no fiarse del autoinforme del modelo— con una consecuencia estructural:

> **La heurística de span solo caza falsos positivos. Es ciega, por construcción, a las omisiones.**
> Si el texto dice *«plata y baño de oro»* y el extractor devuelve `["plata"]`, la frase está en el
> texto → confianza **0,85** → la fila parece impecable y es incorrecta.

**Medido sobre el catálogo real:**

| material nombrado en el texto y **no** extraído | productos | en el estrato de máxima confianza |
|---|---:|---:|
| `hilo` | 60 | 56 |
| `perla` | 35 | 26 |
| `plata` | 3 | 3 |
| **productos distintos afectados** | **94** | **81 (86 %)** |

**Una cola ordenada por confianza ascendente —el orden que cualquiera escribiría— no vería 81 de los
94 errores de omisión del catálogo.** Por eso la muestra es estratificada y no ordenada.

### Los tres estratos y sus cuotas

Tomando el **peor** de los tres campos sensibles por producto, sobre los **1.168 `Approved`** (los 32
rechazados se tratan aparte, ver más abajo):

| estrato | definición | productos | cuota | qué error se espera encontrar |
|---|---|---:|---:|---|
| **A · ausencia** | peor ≤ 0,20 | 122 | **60** | El vacío que no debería estar vacío |
| **B · sin evidencia** | peor ≤ 0,45 | 285 | **60** | **Retiradas** — el modelo se lo inventó (270 son `stone_type`) |
| **C · con evidencia** | peor = 0,85 | 761 | **60** | **Adiciones** — el modelo se dejó algo (los 94 medidos) |
| | | **1.168** | **180** | |

180 productos son el **12-15 % que el §15 ya declara**. Es una predicción falsable: si las retiradas
se concentran en B y las adiciones en C, la heurística de span queda **validada como señal de triaje**
y el proyecto puede recomendar *«revisa estos 285 y cubres la mayor parte del daño»*. Si no, también
es un resultado.

### El criterio del revisor, que hay que declarar o el número no significa nada

Hay **0 fotos y 0 embeddings visuales** en el sistema; los 764 productos sintéticos y el texto de los
404 reales los escribió un LLM (§15, limitación 1). Por tanto:

- **Criterio ejecutable:** *«¿sostiene el texto de origen este valor?»* → mide **al extractor**, que es
  exactamente lo que el §11.5 afirma medir, y sobrevive intacto a que el texto sea asistido.
- **Criterio imposible:** *«¿es verdad de la pieza?»* → exige foto o al comerciante. No hay ninguno.

No es opinable, pero **no está escrito en ningún documento**, y sin escribirlo el número del README no
es interpretable. Va como requisito, y la pantalla lo hace operable mostrando **el nombre y la
descripción completos** junto a cada valor propuesto.

### Y una trampa que este proyecto ya pisó una vez

C18b registró **64 juicios y solo 6 tiempos**. Su informe lo explica sin adornos: *«el cronómetro
vivía en el estado del componente y moría con la pestaña»*. La media del entregable **no existe para
aquella ejecución**.

C28 tiene la misma trampa agravada, porque su ficha pide **aprobación masiva por campo** y
`ReviewDurationMs` queda —correctamente— a `null` en masa:

```text
  Si el lote se aprueba mayoritariamente en masa:
     tasa de corrección  →  sale, y sale baja (una aprobación es un cero)
     tiempo medio        →  NULL sobre casi todo el lote
  → la casilla del §16 se queda a medias por segunda vez
```

---

### Alcance de esta historia (sí)

1. **Cola de revisión por origen, no por estado.** `ReviewOrigin = AutoBulk` sobre `ReviewStatus =
   Approved`; revisar es pasar el perfil a `Human`. **Nada sale del índice durante la revisión.**
2. **Muestra estratificada A/B/C con cuotas 60/60/60**, determinista por semilla, reproducible sin
   persistir el lote y sin migración.
3. **Pantalla de revisión por lotes** en `frontend/src/pages/admin/`: tabla editable, confianza y
   `source` (`rule` / `inferred`) por campo, **texto de origen visible**, y los campos sensibles
   inferidos destacados.
4. **Registro de la corrección con dirección**: adición, retirada, sustitución o confirmación, por
   campo y por producto.
5. **Quién revisó, cuándo y cuánto tardó**, con el cronómetro **persistido en cada guardado**.
6. **Aprobación masiva por campo**, permitida **solo dentro de un estrato y un campo**, marcada como
   tal y sin tiempo fabricado.
7. **Endpoint de métricas** con tasa de corrección **por campo, por estrato y por dirección**, total
   ponderado, y las **dos poblaciones de tiempo reportadas aparte**.
8. **Atajos de teclado** en la pantalla nueva **y en `family-review.tsx`**, vía hook compartido.
9. **Extracción estrecha de carcasa**: `useItemStopwatch()`, `<ThreeStateList>` y
   `useReviewKeyboard()` — lo que tiene dos consumidores reales, nada más.
10. **Crear una familia desde la revisión de familias**, como requisito separado de la capability
    `family-review`, con los **nueve SKU heredados de C18b** como caso de prueba real.
11. **La sesión de revisión de verdad**: 180 ítems cronometrados, más una pasada corta sobre los 32
    rechazados, y el informe de implementación con los números.

### Fuera de alcance (no)

1. **Reenriquecer ningún producto.** Esta historia corrige valores; no vuelve a llamar al extractor.
2. **Cambiar el vocabulario cerrado ni los prompts.** Si la revisión destapa una laguna de
   vocabulario —y la probabilidad es alta con `hilo` y `perla`—, se anota como hallazgo, igual que
   C18a hizo con `FIX1`. No se arregla aquí.
3. **Tocar el pipeline de enriquecimiento, `confidence.py` ni las constantes de confianza.**
4. **Migración de base de datos.** C08 reservó `ProposedProfileJson` y `ReviewDurationMs` por escrito
   y cumplió: no se abre una séptima.
5. **Mover el contrato congelado de `jbg-ai`.** Esta historia no toca `ai-service/`.
6. **Extraer la carcasa completa de `family-review.tsx`.** Solo las tres piezas con dos consumidores.
7. **Reranking, recuperación, evaluación del golden set** ni la tabla de ablations.
8. **Revisar el catálogo entero.** El lote es de 180 y la limitación 2 del §15 se declara con lo que
   se revise de verdad.

### Decisiones de diseño ya acordadas

| # | Decisión | Alternativa descartada, y por qué |
|---|---|---|
| 1 | La cola es de **origen** (`AutoBulk`), no de **estado** | Abrir lote a `Pending` sacaría los 180 del índice a mitad de sesión: el feed selecciona `Approved`. Una entidad `ReviewBatch` costaría la séptima migración |
| 2 | **Muestra estratificada A/B/C**, cuotas 60/60/60 | Orden por confianza ascendente es ciego a 81 de los 94 errores de omisión; aleatoria simple gasta el 63 % de la atención en el estrato C sin separar poblaciones |
| 3 | Muestra **determinista por semilla** (`hash(ProductId + semilla)`) | Persistirla exigiría migración. La semilla se declara y el lote se reproduce |
| 4 | El criterio del revisor es la **fidelidad al texto de origen** | El criterio de verdad de la pieza no es ejecutable: 0 fotos en el sistema |
| 5 | La corrección se reporta **con dirección** | *«Corregido: sí/no»* tira justo lo que el muestreo estratificado fue a buscar |
| 6 | **Dos poblaciones de tiempo**, reportadas aparte; cronómetro persistido en cada guardado | Una media mezclada con los aprobados en masa halaga el proceso. C18b perdió 58 de 64 tiempos por acumularlo en el componente |
| 7 | En el estrato C la pregunta es **«¿falta algo?»**, no «¿es correcto?» | Son tareas cognitivas distintas; pedir la equivocada es como se pierden las 81 omisiones |
| 8 | Extracción de carcasa **estrecha** | Refactorizar 920 líneas ya validadas, con la suite de frontend en rojo de base (118 de 482), es una regresión que no cuenta nadie |
| 9 | Los atajos llegan a **las dos** pantallas | Si solo llegan a la nueva, la tarea 6.4 de C18b sigue siendo falsa en el archivo |
| 10 | Crear familia entra, como **requisito separado** de `family-review` | Mezclarlo con la revisión de perfiles cruzaría dos capabilities en un requisito |
| 11 | El A/B de teclado **se fabrica a propósito**: ~40 ítems a ratón, resto con teclado | Los atajos van en el mismo change: no hay «antes» salvo que se reserve. El efecto aprendizaje se declara |
| 12 | La cola se dibuja sobre los **1.168 `Approved`**; los 32 rechazados van aparte | 26 de los 32 son velas, postales e imanes: rechazo correcto. Gastarían el 18 % de la cuota del estrato A en confirmar que una vela no es una joya |

### Referencias

- **Mediciones de exploración:** [c28-exploration-measurements.md](../../Proyecto%20Final%20AIEng/informes/c28-exploration-measurements.md)
- **Diseño:** §7.8 (revisión híbrida), §11.5 (métricas del enriquecimiento), §15 limitación 2, §16 — [proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md)
- **Ficha del plan:** C28 en [proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md)
- **Capabilities vivas:** [`product-ai-profile`](../../../openspec/specs/product-ai-profile/spec.md) · [`family-review`](../../../openspec/specs/family-review/spec.md) · [`index-feed`](../../../openspec/specs/index-feed/spec.md)
- **Herencias de C18b:** [c18b-family-review-report.md](../../Proyecto%20Final%20AIEng/informes/c18b-family-review-report.md) §8.3 (los nueve SKU) y § *«El tiempo medio no está»* (el cronómetro perdido)
- **Change:** `add-profile-review-ui-and-metrics` · **Épica:** EP13

---

## Criterios de Aceptación

### Escenario 1: La cola se dibuja por origen y nada sale del índice

- **Dado que** los 1.200 perfiles están en `ReviewOrigin = AutoBulk` y 1.168 de ellos en `ReviewStatus = Approved`,
- **Cuando** un administrador abre la pantalla de revisión de perfiles,
- **Entonces** la cola se compone únicamente de perfiles `AutoBulk` **y** `Approved`,
- **Y** ningún perfil cambia de `ReviewStatus` por el hecho de entrar en la cola,
- **Y** el número de documentos vivos en `ai.product_document` no varía mientras la revisión está en curso.

### Escenario 2: La muestra es estratificada y reproducible

- **Dado que** la cola se solicita con una semilla determinada,
- **Cuando** se pide el lote dos veces,
- **Entonces** devuelve **los mismos 180 productos** en el mismo orden,
- **Y** con las cuotas **60 / 60 / 60** sobre los estratos A (ausencia), B (sin evidencia) y C (con evidencia),
- **Y** cada ítem declara a qué estrato pertenece y por qué campo lo hace.

### Escenario 3: Los campos sensibles inferidos se destacan, y los de regla no

- **Dado que** un perfil tiene `size_label` con `source: rule` y `piece_type`, `materials` y `stone_type` con `source: inferred`,
- **Cuando** el administrador lo abre en la pantalla,
- **Entonces** los tres campos inferidos aparecen destacados como pendientes de revisión,
- **Y** `size_label` no lo hace,
- **Y** cada campo muestra su confianza y su procedencia.
- *(Cubre el test de la ficha `should highlight inferred sensitive fields pending review`.)*

### Escenario 4: El texto de origen está delante, porque es el criterio

- **Dado que** el criterio de revisión es la fidelidad al texto de origen y no la verdad de la pieza,
- **Cuando** el administrador revisa un producto,
- **Entonces** la pantalla muestra el **nombre y la descripción completos** del producto junto a los valores propuestos,
- **Y** cuando el producto no tiene descripción, lo dice explícitamente en vez de mostrar un hueco.

### Escenario 5: Corregir una lista de materiales se registra con su dirección

- **Dado que** un perfil propone `materials: ["plata"]` y su descripción menciona además `hilo`,
- **Cuando** el administrador añade `hilo` y guarda,
- **Entonces** se registra una corrección de **dirección `adición`** sobre el campo `materials`,
- **Y** el perfil pasa a `ReviewOrigin = Human` conservando su `ReviewStatus`,
- **Y** `ProposedProfileJson` **no se modifica**, de modo que la diferencia sigue siendo computable.
- *(Cubre el test de la ficha `should record correction when material list is edited`.)*

### Escenario 6: Retirar un valor inventado se registra como retirada

- **Dado que** un perfil del estrato B propone `stone_type: "piedra"` y el texto no nombra ninguna piedra,
- **Cuando** el administrador vacía el campo y guarda,
- **Entonces** se registra una corrección de **dirección `retirada`** sobre `stone_type`.

### Escenario 7: El cronómetro se persiste en cada guardado

- **Dado que** el administrador ha tardado 34 segundos en decidir sobre un producto,
- **Cuando** guarda esa revisión,
- **Entonces** `ReviewDurationMs` queda persistido en esa misma petición,
- **Y** cerrar la pestaña a continuación **no pierde** ningún tiempo ya guardado,
- **Y** recargar la pantalla y revisar el siguiente ítem no reutiliza el cronómetro del anterior.

### Escenario 8: La aprobación masiva no fabrica un tiempo

- **Dado que** el administrador aprueba en masa el campo `color_tags` de 40 productos del mismo estrato,
- **Cuando** la operación se confirma,
- **Entonces** los 40 quedan marcados como aprobados en masa y con `ReviewDurationMs` **nulo**,
- **Y** las métricas cuentan esos 40 en la población **sin tiempo**, nunca en la media,
- **Y** la operación es rechazada si los productos seleccionados pertenecen a más de un estrato o a más de un campo.

### Escenario 9: La tasa de corrección se calcula por campo

- **Dado que** hay revisiones humanas registradas,
- **Cuando** se consulta el endpoint de métricas,
- **Entonces** devuelve la tasa de corrección **por campo** (`piece_type`, `materials`, `stone_type`, `size_label` y las tres listas de etiquetas),
- **Y** desglosada **por estrato** y **por dirección** (adición / retirada / sustitución / confirmación),
- **Y** con un total ponderado por el tamaño real de cada estrato en el corpus.
- *(Cubre el test de la ficha `Metrics_CorrectionRate_ComputedPerField`.)*

### Escenario 10: Las métricas excluyen los perfiles no revisados por humanos

- **Dado que** 1.020 perfiles siguen en `ReviewOrigin = AutoBulk` y 180 han pasado a `Human`,
- **Cuando** se consulta el endpoint de métricas,
- **Entonces** ningún perfil `AutoBulk` entra en el numerador ni en el denominador de la tasa de corrección,
- **Y** la respuesta declara cuántos perfiles hay de cada origen, para que el porcentaje revisado sea legible.
- *(Cubre el test de la ficha `Metrics_ExcludesAutoBulkProfiles`.)*

### Escenario 11: Sin tiempos, la métrica informa la ausencia y nunca un cero

- **Dado que** ninguna revisión registrada lleva tiempo medido,
- **Cuando** se consulta el endpoint de métricas,
- **Entonces** el tiempo medio se devuelve **nulo**, nunca cero,
- **Y** la respuesta indica cuántas revisiones llevan tiempo y cuántas no.

### Escenario 12: Una corrección llega al índice sin intervención

- **Dado que** el administrador ha corregido los materiales de un producto aprobado,
- **Cuando** el feed de indexación se ejecuta de forma incremental,
- **Entonces** ese producto vuelve a emitirse porque su marca de agua ha avanzado,
- **Y** su documento en `ai.product_document` refleja los materiales corregidos.

### Escenario 13: Rechazar un perfil lo saca del índice

- **Dado que** el administrador decide que un producto de la cola no es una joya,
- **Cuando** lo marca como rechazado y guarda,
- **Entonces** el perfil queda en `ReviewStatus = Rejected` con `ReviewOrigin = Human`,
- **Y** el feed propaga su baja, de modo que deja de estar en el índice.

### Escenario 14: Los 32 rechazados se revisan con la pregunta invertida

- **Dado que** existen 32 perfiles en `ReviewStatus = Rejected`, todos con origen `AutoBulk`,
- **Cuando** el administrador abre la revisión de rechazados,
- **Entonces** la pantalla los presenta preguntando si **algún rechazo es incorrecto**,
- **Y** permite devolver uno a `Approved` dejando constancia de quién lo hizo,
- **Y** esos 32 **no consumen cuota** de los tres estratos del lote principal.

### Escenario 15: Se puede crear una familia desde la revisión de familias

- **Dado que** existen siete productos de `piece_type: cadena` y no existe ninguna familia de ese tipo,
- **Cuando** el administrador los selecciona en la pantalla de revisión de familias y crea una familia con su nombre y sus etiquetas de variante,
- **Entonces** la familia queda persistida con sus miembros y su `Origin` correspondiente,
- **Y** los productos dejan de figurar como huérfanos,
- **Y** el mismo flujo resuelve las dos alianzas (`SKU327`, `SKU397`) que la auditoría por vecindad no puede nominar.

### Escenario 16: Los atajos de teclado funcionan en las dos pantallas

- **Dado que** el administrador está recorriendo una cola de revisión,
- **Cuando** usa los atajos de teclado para aprobar, rechazar y avanzar al siguiente ítem,
- **Entonces** no necesita el ratón para recorrer la cola completa,
- **Y** los mismos atajos funcionan en la revisión de perfiles **y** en la revisión de familias,
- **Y** los atajos no se disparan mientras el foco está dentro de un campo de edición de texto.

### Escenario 17: Una lista que no se pudo calcular nunca se presenta como vacía

- **Dado que** la consulta de la cola falla,
- **Cuando** la pantalla se dibuja,
- **Entonces** informa de que la lista **no se pudo calcular**,
- **Y** nunca muestra un estado de «no hay nada que revisar», que en una pantalla cuyo asunto es la calidad del catálogo se leería como «no hay nada mal».

### Escenario 18: Solo los administradores

- **Dado que** un usuario con rol Operador está autenticado,
- **Cuando** solicita cualquiera de las rutas de revisión de perfiles o de métricas,
- **Entonces** recibe `403 Forbidden`,
- **Y** una petición sin autenticar recibe `401 Unauthorized`.

### Escenario 19: Fuera de alcance explícito

- **Dado que** la revisión destapa que el vocabulario de materiales no cubre un término frecuente,
- **Cuando** el administrador lo corrige a mano en los productos del lote,
- **Entonces** el hallazgo queda **anotado en el informe de implementación**,
- **Y** esta historia **no** modifica `vocabularies.yaml`, **no** reenriquece ningún producto y **no** cambia versión de prompt.

---

## Notas adicionales

- **Actor:** Administrador. Todas las rutas van bajo `[Authorize(Roles = "Administrator")]`, como
  las de revisión de familias.
- **Es la segunda pantalla de juicio humano del proyecto**, y la primera que produce una métrica que
  el checklist de entrega pide por su nombre. La primera —`family-review.tsx`, C18b— aporta la
  carcasa y la lección: el cronómetro se persiste o no existe.
- **No es una historia de pantalla, es una historia de medición.** La pantalla es el medio; el
  entregable son los dos números y su desglose. Por eso la sesión de revisión de 180 ítems está en el
  alcance y no en el «después».
- **Limitación conocida que hereda del corpus:** el texto contra el que se juzga lo escribió un LLM
  —los 764 sintéticos por construcción, los 404 reales por asistencia de redacción—. La métrica mide
  **al extractor**, que es lo que el §11.5 afirma medir, y esa frontera se declara en el README.
- **Limitación conocida del instrumento:** la heurística de span no puede detectar omisiones, así que
  el recuento de 94 productos afectados es una **cota superior** obtenida con coincidencia literal,
  no un recuento de errores confirmados. Confirmarlos es justamente lo que la revisión hace.
- **Change de OpenSpec:** `add-profile-review-ui-and-metrics`. **Rama:**
  `c28-add-profile-review-ui-and-metrics`.

---

## Tareas

1. **Definición del estrato en un solo sitio** (`Application/`): función compartida por la cola y por
   las métricas, para que no puedan divergir.
2. **Muestreo determinista por semilla**, con cuotas por estrato y la semilla leída de configuración.
3. **`IProfileReviewService`**: listar la cola, registrar una revisión individual, aprobar en masa
   por campo y estrato, y calcular las métricas.
4. **DTOs y validación**: petición de revisión con valores corregidos y duración; rechazo de la
   aprobación masiva que cruce estratos o campos.
5. **Cálculo de la corrección con dirección**, diferenciando `ProposedProfileJson` de los valores en
   vigor, con tratamiento explícito de listas (adición, retirada, sustitución).
6. **Rutas en la API** bajo el prefijo de catálogo de IA, solo administrador, con paginación.
7. **Revisión de los 32 rechazados** como vista y ruta propias, con la pregunta invertida.
8. **Extracción estrecha de carcasa** en frontend: `useItemStopwatch()`, `<ThreeStateList>`,
   `useReviewKeyboard()`.
9. **Pantalla `profile-review.tsx`**: tabla editable, texto de origen, confianza y procedencia por
   campo, destacado de sensibles inferidos, barra de aprobación masiva y tarjeta de métricas.
10. **Atajos de teclado** enganchados en la pantalla nueva **y** en `family-review.tsx`, corrigiendo
    la tarea 6.4 de C18b.
11. **Creación de familia desde la revisión de familias**, consumiendo el `POST` que ya existe.
12. **Tests backend** (xUnit + FluentAssertions): estratificación, determinismo, dirección de la
    corrección, exclusión de `AutoBulk`, nulo frente a cero, y permisos.
13. **Tests frontend** (Vitest + RTL): destacado de sensibles inferidos, registro de corrección al
    editar materiales, cronómetro por ítem, tres estados de lista y atajos.
14. **Sesión de revisión real**: 180 ítems cronometrados con el A/B de teclado reservado, más la
    pasada sobre los 32 rechazados.
15. **Specs delta** de `product-ai-profile` y `family-review`, con `openspec validate --all --strict`
    en verde.
16. **Informe de implementación** con los dos números, su desglose por estrato y dirección, y los
    hallazgos de vocabulario que la revisión destape.
17. **Documentación**: `Documentos/epicas.md`, plan de changes, y la limitación 2 del §15 ajustada al
    porcentaje realmente revisado.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **5/5** — el §13.4 la marca como **«nunca se recorta»**, y el §16 la convierte en una casilla marcada o vacía, no en un grado. Es la única evidencia de que el extractor sirve |
| Urgencia | **3/5** — es **hoja del grafo**: nadie depende de ella. Pero es lo único que produce dos de los números del entregable, y su coste real es de atención humana, que no se puede paralelizar ni comprimir |
| Complejidad / esfuerzo | **3/5** — sin migración, sin contrato que mover, sin `ai-service/`, y con el reindexado ya resuelto. Lo caro es el diseño del muestreo, la disciplina del cronómetro, y las 1,5-2 h de revisión que el entregable exige |
| Riesgos | Que el cronómetro vuelva a salir vacío, como en C18b (mitigado por los Escenarios 7 y 8); que la aprobación masiva vacíe el lote de contenido (mitigado por la restricción de estrato y campo); que el refactor de carcasa rompa `family-review.tsx` en silencio, con la suite de frontend en rojo de base (mitigado por la extracción estrecha y por comparar **nombres** de test, nunca recuentos); que la sesión de revisión se posponga y el change se dé por hecho sin sus números; que el etiquetado lo haga la misma persona que diseñó el muestreo, sesgo que el README ya declara para el golden set |
| Dependencias | **C08**, archivado — reservó `ProposedProfileJson` y `ReviewDurationMs`, de modo que no hace falta migración. Hereda de **C18b** los atajos de teclado y los nueve SKU sin familia. **No bloquea a nadie** |
