## Context

`ProductSearchEvent` aparece en las especificaciones funcionales v2 §5.8 como un modelo de once campos, y en la ficha C04 del plan como *«entidad, migración, `POST /api/ai/search-events`, índices por fecha y POS»*. Ninguno de los dos documentos dice **quién escribe el evento ni cuándo**, y esa es la decisión de la que cuelga todo lo demás.

El estado del repositorio en el momento de diseñar:

| Pieza | Estado |
|---|---|
| Entidad, enum y repositorio | Ausentes |
| Rutas bajo `api/ai/*` | Ninguna; 18 controladores, ninguno de IA |
| Columnas `jsonb` en el modelo | Ninguna; el único tipo declarado a mano es `text` |
| Tests de migración o aserciones de esquema | **Ninguno** en todo el repositorio |
| `AiCallScope`, con fábrica única que exige punto de venta | Existe (C03) |
| `AiSearchResult` / `AiSearchFilters` / `TraceId` | Existen y están congelados (C03) |
| `TestDatabaseFixture` (Testcontainers + Respawn, expone la cadena de conexión) | Existe |
| Regla y test de confidencialidad del texto de consulta en logs | Existen (C03) |

Dos hechos del entorno gobiernan el diseño más que ninguna consideración estética. El primero: la regla 4 del plan permite **una sola migración de EF Core activa a la vez**, y quedan seis en total, así que un slot de migración es el recurso más escaso del proyecto. El segundo: el consumidor de esta telemetría —el panel de C16— no existirá hasta dos semanas después, de modo que el contrato se diseña sin cliente contra el que probarlo.

## Goals / Non-Goals

**Goals:**

- Que los seis KPIs de las especificaciones v2 §5.11 sean calculables con SQL sobre la tabla, sin inferencias ni cruces difusos.
- Que la búsqueda degradada al buscador léxico (diseño §6.4) quede **distinguible** de la asistida, para que un periodo de cortacircuitos abiertos no se lea como una degradación del ranking.
- Que el trabajo que hereda C16 —🔴, en la ola congestionada— sea el mínimo posible.
- Que la migración deje instalado el utillaje de verificación de esquema que reutilizarán las cinco migraciones restantes.
- Que ningún fallo de telemetría pueda afectar a una búsqueda ni a una venta.

**Non-Goals:**

- Cualquier lectura: consultas, agregaciones, panel de KPIs o cálculo de métricas. El análisis del entregable se hace con SQL a mano en C39.
- Retención, anonimización o supresión programada del texto de consulta.
- El endpoint de búsqueda, el panel del frontend y la escritura de la atribución en el flujo de venta.
- Precisión forense en la captura: el diseño §15.3 fija la barra en *instrumentado*, no en *auditado*.

## Decisions

### 1. El principio que ordena el resto: asimetría de reversibilidad

Este change contiene dos artefactos con costes de cambio opuestos:

```
 ┌────────────────────────────────┬────────────────────────────────┐
 │  ESQUEMA                       │  SUPERFICIE DE API             │
 │  tabla, columnas, tipos,       │  DTO, validación, ruta,        │
 │  índices, nulabilidad          │  códigos de respuesta          │
 ├────────────────────────────────┼────────────────────────────────┤
 │  cambiarlo cuesta 1 slot de    │  cambiarlo cuesta 0:           │
 │  migración de un total de 6    │  no hay ni un cliente          │
 │  + coordinación con el otro dev│                                │
 ├────────────────────────────────┼────────────────────────────────┤
 │  → GENEROSO Y CUIDADOSO HOY    │  → MÍNIMO Y PROVISIONAL HOY    │
 └────────────────────────────────┴────────────────────────────────┘
```

Regla operativa: **si hay duda sobre si una columna hará falta, entra; si hay duda sobre si un campo del DTO hará falta, se queda fuera.** La ceguera de dos semanas sobre el consumidor solo duele en la columna izquierda.

De aquí salen las decisiones 4, 5 y 9, y de aquí sale también que el DTO acabe con un único campo.

### 2. Quién escribe cada dato

La decisión estructural. La partición de conocimiento entre navegador y servidor es **complementaria**: ninguno de los dos puede escribir el evento entero sin inventarse la mitad.

```
┌──────────────────────────────┬───────────────────────────────────────┐
│ NAVEGADOR (C16)              │ BACKEND, sirviendo POST /api/ai/search│
├──────────────────────────────┼───────────────────────────────────────┤
│ ✔ qué producto eligió        │ ✔ consulta, filtros efectivos, POS    │
│ ✔ dónde empieza el episodio  │ ✔ la lista exacta tras hidratar       │
│ ✗ qué devolvió jbg-ai        │ ✔ si el circuito estaba abierto       │
│ ✗ el trace_id                │ ✔ trace_id                            │
│ ✗ la latencia real           │ ✔ latencia medida donde ocurre        │
│   (mide red + render encima) │ ✗ si el operador llegó a elegir       │
└──────────────────────────────┴───────────────────────────────────────┘
```

**Decisión: el servidor escribe la mitad de búsqueda; el cliente reporta solo la selección.** Es el principio del diseño §6.2 (*«.NET calcula números y decide»*) y §7.6 (el hidratador es autoridad final) aplicado a la telemetría: pedirle al navegador que reporte la lista que el propio servidor acaba de calcular es el mismo error de categoría que fiarse de `jbg-ai` para el precio y el stock.

```mermaid
sequenceDiagram
    participant FE as Navegador (C16)
    participant API as API .NET (C15)
    participant SVC as Servicio de telemetría (este change)
    participant DB as PostgreSQL

    FE->>API: POST /api/ai/search { query, filters, searchSessionId }
    API->>API: recupera, hidrata, trunca
    API->>SVC: RecordSearchAsync(scope, consulta, lista mostrada, origen, traza, tiempos)
    SVC->>DB: INSERT evento (sin las tres columnas de selección)
    DB-->>SVC: ok
    SVC-->>API: Guid?  (null si algo falló; nunca lanza)
    API-->>FE: resultados + searchEventId

    Note over FE: tiempo de decisión de la persona

    FE->>API: POST /api/ai/search-events/{id}/selection { productId }
    API->>SVC: registra la selección
    SVC->>DB: SELECT resultados guardados
    SVC->>SVC: deriva el rank buscando el producto en la lista
    SVC->>DB: UPDATE producto, rank y SelectedAt
    API-->>FE: 204
```

**Alternativa descartada — que el cliente escriba el evento entero, en una llamada al terminar el episodio.** Más simple de leer, y peor en todo lo que importa: el `ResultsJson` pasaría a ser *lo que el cliente dice que mostró*, la latencia incluiría red y render, el origen y la traza serían repetidos de oídas, y C16 tendría que ensamblar y mantener un payload con lista, filtros, relojes y origen. Solo gana en una cosa —resistencia a que muera la pestaña— y solo respecto a la selección. Con el diseño §15.3 declarando que los KPIs están *instrumentados, no medidos*, esa no es la barra.

Efecto colateral buscado y medible: **tres obligaciones sobre C16 desaparecieron** al tomar esta decisión (emitir en abandono, calcular el rank 1-based de la lista mostrada, reportar el origen). Las tres dejaron de depender de que alguien se acordara.

### 3. Granularidad: una fila por consulta, agrupadas por episodio

Un operador con un cliente delante no hace *una* búsqueda: reformula y refina. Tres opciones y sus consecuencias:

| | Granularidad | Problema |
|---|---|---|
| G1 | una fila por consulta | Las consultas previas a la selección quedan sin ella e **indistinguibles de un abandono real**: quien refina dos veces y compra genera dos falsos «consulta sin resultado» |
| G2 | una fila por episodio | KPIs limpios, pero se pierde la reformulación, que es justo la señal de que el primer intento fue malo |
| **G3** | G1 + identificador de episodio | Las dos cosas, por una columna |

**Decisión: G3**, con `SearchSessionId` generado en el cliente al abrir el panel. Lo elegante es que reformulación y abandono se distinguen **sin columna adicional**: una fila sin selección que tiene hermanas posteriores en su sesión es una reformulación; una que no las tiene, un abandono.

### 4. El enlace venta↔búsqueda va del lado de la venta

Specs v2 lo pone en el evento (`CreatedSaleId`). El flujo real lo desaconseja:

```
  busca → selecciona → añade al carrito ─┐
  busca → selecciona → añade al carrito ─┼→ checkout masivo → 2 ventas, 1 BulkOperationId
  busca → selecciona → abandona ─────────┘
```

| | En el evento | **En la venta** |
|---|---|---|
| Momento de escritura | después de crear la venta | **en el mismo `INSERT`** |
| Llamadas del cliente | una tercera, tras el checkout | ninguna: un campo más en una petición que ya se envía |
| Checkout de 3 líneas | 3 llamadas de seguimiento | 3 campos opcionales |
| Se puede perder | sí | no: o se crea la venta o no |

**Decisión: `Sale.SearchEventId`.** Es la forma canónica de modelar atribución —el hecho derivado declara su origen, que ya existe cuando nace— y encoge otra vez lo que C16 debe hacer. `ProductSearchEvent` no lleva `CreatedSaleId` ni navegación hacia `Sale`: un solo enlace en un solo sitio, porque dos columnas que dicen lo mismo acaban divergiendo.

### 5. Los tiempos: dos duraciones de servidor y una marca de tiempo

`SearchDurationMs` podía significar tres cosas distintas:

```
   ├──────────────────────── ¿reloj 3? ───────────────────────┤
   ├─ ¿reloj 1? ─┤                                            │
   ▼             ▼                                            ▼
 consulta    resultados en pantalla                    el operador elige
  ≈ 300 ms          │──────────── ¿reloj 2? ────────────│  ≈ 5-30 s
```

**Decisión:**

- `RetrievalMs` — obtener candidatos, **agnóstico del origen**: mide la llamada a `jbg-ai` o la consulta léxica, según cuál haya respondido. Definirlo así hace las dos rutas comparables entre sí, que es lo que permite leer *«la degradada es más rápida y peor»* con números.
- `TotalMs` — hasta que la lista final está lista para devolver, con el corte **antes** de persistir la telemetría o la medición se muerde la cola. `TotalMs − RetrievalMs` ≈ **coste de la hidratación**, cifra que hoy nadie conoce y que el README querrá para defender la decisión de §7.6.
- `SelectedAt` — sellado por el servidor, **en lugar de un delta calculado en el cliente**. Con G3, un delta de cliente solo puede medir el último tramo tras varias reformulaciones; una marca de tiempo permite derivar tanto el tramo como el episodio completo (`SelectedAt − min(CreatedAt)` de la sesión).

Seis análisis salen de estas tres columnas y ninguno requiere aritmética en el cliente: `p95` de recuperación por origen, coste de hidratación, tiempo consulta→selección, tiempo episodio→selección, tiempo de reformulación, y correlación entre latencia y abandono.

**No se reutiliza `UpdatedAt` como `SelectedAt`.** El contexto de datos lo pisa en cada guardado, así que dejaría de ser el instante de la selección en cuanto cualquier escritura futura tocase la fila —un backfill, una anonimización— y lo haría en silencio. Reutilizar una columna de auditoría como hecho de negocio es de las formas más baratas de corromper una tabla de analítica.

### 6. Qué se guarda de cada resultado: solo lo irrecuperable

Criterio único: **¿se puede reconstruir esto dentro de seis semanas con un `JOIN`?**

| Campo | ¿Reconstruible? | |
|---|---|---|
| identificador de producto | es la clave del cruce | entra |
| rank | índice del array, explícito para simplificar el SQL | entra |
| `score` | **no**: dependía del índice, del modelo de embeddings y de los pesos de ese día | entra |
| `matchReasons` | **no**: misma razón, y es lo que el operador leyó como motivo | entra |
| SKU | sí, pero es la identidad legible al consultar a mano | entra |
| materiales, familia, variante | sí, son atributos de catálogo | fuera |
| precio y stock del momento | no, pero es especulativo | fuera, declarado |

El `score` es el caso de libro: misma lógica por la que `Sale.Price` congela el precio en lugar de referenciarlo. Sobre el SKU hay precedente en casa —`ProductPhotoEmbedding` guarda identificador **y** SKU— y el motivo es idéntico: en C39 alguien va a leer estas filas a mano, y un array de identificadores es ilegible.

`matchReasons` merece defensa por ser el campo más gordo: habilita una pregunta que ninguna otra columna responde —*¿los operadores eligen más los resultados cuyo motivo menciona el material, o los que mencionan el nombre exacto?*— que es evidencia directa sobre qué señal del ranking vale, y que §11 solo consigue offline sobre 60-70 consultas etiquetadas a mano.

**La lista guardada es la mostrada**, no los candidatos crudos de la sobre-recuperación. Bajo la decisión 2 es imposible equivocarse: escribe C15 en el mismo método donde acaba de truncar. La única grieta es del lado cliente, y por eso B3 le prohíbe reordenar: si lo hiciera, el rank mediría el orden de la interfaz en lugar de la calidad de la recuperación, que son preguntas distintas y la tabla solo puede responder una.

### 7. `jsonb`, no `text`

El único precedente del repositorio es `text`, y no aplica: aquel campo es un blob que nunca se consulta por dentro, y este existe para agregarse. `jsonb` aporta consulta con SQL puro y, sobre todo, **validación en la escritura**, lo que convierte el error de truncar la cadena JSON en algo imposible por construcción en lugar de en algo que hay que recordar no hacer.

Se mapea como propiedad `string` con el tipo de columna declarado a mano, **sin** las entidades propietarias con serialización a JSON que ofrece EF: nunca se lee desde C#, así que el tipado no compra nada y a cambio complica el truncado y lo saca del sitio donde es fácil de probar.

La convención de nombres del JSON queda fijada en `camelCase`. Es una **decisión de una vía**: cambiarla después rompe en silencio todas las consultas del script de C39, que nadie ejecutará hasta el final.

### 8. El truncado es un guardarraíl, no una funcionalidad

Sin cliente no fiable de por medio, «lista demasiado grande» solo puede venir de un defecto propio. Eso cambia el diseño del límite:

- **Por número de entradas, nunca por bytes.** Cortar una cadena JSON produce JSON inválido, inservible para el análisis — y con `jsonb` ni siquiera se almacenaría.
- **Tope holgado por encima de cualquier lista plausible.** Con una página en torno a 10-20 resultados, un tope de 50 no se alcanza jamás en operación normal y solo salta ante un bug. Un tope ajustado sería una funcionalidad que descarta datos buenos en silencio.
- **`ResultsCount` guarda los mostrados de verdad**, con independencia de cuántos se almacenaron. Dos regalos por una columna entera: el KPI más consultado —consultas sin resultado— se calcula sin abrir el JSON, y el truncado queda detectable comparándola con la longitud del array, sin necesidad de un booleano dedicado.

### 9. El rank lo deriva el servidor, y el DTO se queda en un campo

Si el servidor ya tiene la lista ordenada, que el cliente le diga en qué posición estaba es información redundante que puede discrepar. **Decisión: el servidor busca el producto en la lista guardada y calcula el rank.**

Tres consecuencias encadenadas:

- El invariante *«el rank coincide con la posición del producto seleccionado»* **deja de poder romperse**, porque hay un único escritor del par. No necesita validación.
- Es más correcto, no solo más simple: el KPI pregunta por la calidad de la recuperación, y el rank del servidor mide eso aunque la interfaz mostrara otra cosa.
- El cuerpo de la petición queda en `{ productId }`.

Si el producto **no aparece** en la lista guardada, se registra la selección con rank nulo y un aviso en el log, en lugar de rechazar la petición. La comparación es clara: rechazar deja el evento pareciendo abandonado y **el KPI de conversión miente**; guardar con rank nulo lo deja correcto y el KPI de rank simplemente excluye la fila. **Un nulo no miente; una fila que falta, sí.**

### 10. Autorización, y la desviación deliberada del patrón de la casa

La garantía de punto de venta la aporta la **firma del servicio**, no una comprobación que alguien pueda olvidar: el registro de búsqueda recibe un `AiCallScope`, cuyo único constructor exige un punto de venta ya resuelto y validado. Es la disciplina que C03 documentó para ese tipo —*«no autoriza nada; transporta un ámbito ya validado por quien llama»*— reutilizada en lugar de reinventada. La fila no puede existir para un punto de venta ajeno porque la búsqueda tampoco pudo.

En la selección la pregunta es otra: no *«¿tienes acceso a este punto de venta?»* sino *«¿es tuyo este evento?»*. Y ahí **el administrador no hace bypass**, contra el patrón uniforme del repositorio:

```
   patrón de la casa           aquí
   ─────────────────           ────
   admin opera en todo POS ✔   admin ESCRIBE el evento ajeno ✗
```

El bypass de administrador existe para *gestionar* datos de negocio. Un evento de telemetría no se gestiona: es el registro de lo que hizo una persona concreta, y permitir que otra lo complete es permitir corromper el dato sin dejar rastro. El test que lo fija lleva el nombre explícito precisamente porque documenta la desviación.

### 11. La telemetría no puede romper nada

Corolario del principio del diseño §6.4 —*«el sistema nunca se cae por culpa de la IA»*— extendido: **tampoco por culpa de medirla.** Se implementa como garantía, no como obligación sobre otro:

- El registro de búsqueda **devuelve un identificador opcional y nunca lanza**: absorbe cualquier fallo de persistencia y lo registra. C15 no puede incumplirlo aunque quiera; solo tiene que tolerar el nulo.
- Un identificador de búsqueda desconocido en una venta degrada la atribución a nula. Con una clave foránea real y sin esta regla, un identificador caducado produciría una violación de restricción y **el operador no podría vender**.

Las reglas de borrado se declaran a mano por el mismo motivo. El comportamiento por defecto para las relaciones obligatorias es la eliminación en cascada, que aquí significaría *«borrar un empleado borra la evidencia de cómo se usó el sistema»*:

| Relación | Default | Decisión | Motivo |
|---|---|---|---|
| evento → usuario | cascada | restringir | La supresión es un borrado deliberado en dos pasos, no un efecto colateral |
| evento → punto de venta | cascada | restringir | Cerrar un punto de venta no borra su telemetría |
| evento → producto seleccionado | restringir | restringir, explícito | Los productos se desactivan, no se borran; que falle ruidosamente si algún día alguien borra uno |
| venta → evento | restringir | **poner a nulo** | Purgar telemetría no puede bloquear ni destruir ventas |

Asimetría deliberada: **poner a nulo hacia la venta, restringir hacia todo lo demás.** La telemetría es prescindible, así que nada que dependa de ella puede romperse al desaparecer; y nada de lo que ella depende puede desaparecer por accidente arrastrándola. Como efecto secundario, una futura solicitud de supresión es operable sin tocar ventas.

### 12. Índices: dos, y el motivo por el que no son más

A ~200 filas al día —~3.000 en la fecha de entrega, ~70.000 en un año de operación real— **todo índice es decorativo**: un recorrido secuencial completo es sub-milisegundo. Se ponen dos porque el coste de tenerlos también es cero y añadirlos después costaría un slot de migración de un presupuesto de seis. Cuando ambos platos pesan cero, decide el que no consume el recurso escaso más tarde.

| Consulta | Índice |
|---|---|
| KPIs de un punto de venta en un rango de fechas — la dominante | compuesto, punto de venta **primero** por ser el predicado de igualdad |
| Serie temporal global | por fecha |
| Agrupar por sesión, comparar orígenes, consultas sin resultado | ninguno: son agregaciones completas |

El motivo queda escrito en el spec para que nadie añada cuatro más «porque es barato». La configuración de la relación desde `Sale` genera además un índice sobre la columna nueva, que sirve a la dirección evento→venta y **no se elimina**.

*Precisión añadida al aplicar el change:* «dos índices» se refiere a los **índices analíticos declarados a mano**. El generador crea además, por convención, un índice por cada clave foránea —usuario y producto seleccionado—, igual que en el resto de tablas del repositorio. No se suprimen, y no por inercia: las tres reglas de borrado restrictivas obligan a la base de datos a comprobar las filas referenciadas antes de permitir borrar un usuario o un producto, y sin esos índices esa comprobación sería un recorrido secuencial. Son índices estructurales, no decisiones de analítica.

### 13. El arnés de test de migración

Un test que solo afirma *«la migración aplica»* es teatro: el fixture de integración ya ejecuta las migraciones en cada test. El valor está exclusivamente en **lo que falla sin dar error**:

| Fallo posible | ¿Rompe al aplicar? | ¿Cuándo se descubre de verdad? |
|---|---|---|
| Falta el tipo declarado y la columna nace `text` | **no** | en C39, al consultar el JSON, con semanas de datos dentro |
| Índice compuesto con las columnas al revés | **no** | nunca; solo un plan de consulta lento que nadie mira |
| Regla de borrado en cascada | **no** | el día que se purgue telemetría **y desaparezcan ventas** |
| Regla de borrado restrictiva donde debía ser nula | **no** | el día que se ejerza una supresión y no se pueda |
| Configuración cambiada sin generar migración | a veces | según qué test toque esa entidad |

Es el mismo fenómeno que motiva `test_hnsw_index_uses_cosine_operator_class` en C05: un índice mal declarado no da error, simplemente deja de usarse.

**Capa 1, reutilizable:** el test de desfase entre el modelo y el snapshot de migraciones —que compara dos modelos en memoria y **no necesita base de datos**, así que es un test unitario de milisegundos que corre en cada build— y un ayudante de aserciones sobre el catálogo de PostgreSQL, apoyado en el fixture existente. Infraestructura nueva: ninguna.

**Capa 2:** las aserciones propias de este change. C07, C08, C19, C27 y C29 escriben su capa 2 en diez líneas y heredan la capa 1 gratis.

**No se prueba la reversibilidad**, y el motivo diferencia en lugar de calcar el lado Python: aquella migración es artesanal, con extensiones y DDL de índices escritos a mano; esta es generada, y su reversión no es código nuestro. Además exigiría un contenedor propio, porque bajar y subir rompe el aislamiento del fixture compartido.

### 14. Confidencialidad del texto de consulta

El texto es libre, se guarda indefinidamente, y el contexto del negocio lo hace concreto: los puntos de venta son hoteles y un operador puede teclear una referencia a un huésped.

**No procede el pipeline de anonimización** que se aplicaría a un corpus. El argumento de fondo de esa práctica es que el control de acceso no basta en recuperación semántica, porque una vez que el dato está en el espacio vectorial cualquier consulta cercana lo alcanza. Aquí **el texto nunca entra en el espacio vectorial**: no se indexa, no se recupera, no se le pasa a ningún modelo, y no tiene ruta de lectura por API. En ese escenario el control de acceso sí basta.

Las medidas proporcionadas son tres, y dos ya existen: el tope de longitud —**derivado del contrato congelado**, no elegido a ojo—, la regla heredada de C03 de que el texto **no aparece en ningún registro por encima del nivel de depuración**, con su test, y la ausencia de ruta de lectura. La falta de política de retención se declara como limitación en el diseño §15.

## Risks / Trade-offs

| Riesgo | Mitigación |
|---|---|
| **C15 no invoca el registro y este change queda inerte, sin síntoma**: compilaría, los tests pasarían y la tabla llegaría vacía a la entrega | Obligación A1 en el proposal **y** replicada en la ficha de C15 del plan de changes, con tarea explícita para anotarla |
| El arnés de esquema se sobredimensiona: *«construye una herramienta que heredarán cinco changes»* es el enunciado que produce un DSL que nadie pidió | Guardarraíl en `tasks.md`: solo las aserciones que este change necesita hoy. Los cinco siguientes extienden la capa común cuando sepan qué necesitan |
| El change desborda la sesión de 2-3 h | Línea de corte predefinida y tareas ordenadas para respetarla: primero esquema, migración y arnés —que libera el slot y es archivable solo—, después servicio y endpoint, que no llevan migración |
| Colisión con C07 por la regla de migración única | Anuncio previo (regla 3) y cierre temprano de la mitad de esquema. La cola limpia del compañero es C05 o C06 |
| **Trade-off asumido: se antepone un 🟢 a un change que desbloquea la ruta crítica.** C07 abre C12 🔴 y este no abre nada | Se acepta por el coste fijo del arnés, que conviene pagar fuera de la ruta crítica, y queda justificado por escrito. **Si se decide lo contrario, el arnés viaja con C07 y este change lo hereda**: la decisión es de orden, no de propiedad |
| **Trade-off asumido: tres divergencias respecto a las especificaciones funcionales v2**, que es el documento que el tribunal leerá como contrato funcional | Cada una con motivo escrito en el proposal, y las tres corregidas **en el propio documento v2** con fecha y razón, en lugar de dejarlas solo en el change |
| **Trade-off asumido: columnas que nadie escribe todavía** (`Sale.SearchEventId`, y toda la tabla hasta C15) | Es la consecuencia deliberada de la decisión 1. La alternativa —una segunda migración en la Ola 2, la congestionada— es peor por el recurso que consume |
| El tipo de columna se pierde por olvidar declararlo y nace `text`; nada falla hasta C39 | Aserción de esquema en la capa 2 del arnés |
| Un identificador de búsqueda caducado en una venta produce una violación de clave foránea y **el operador no puede vender** | Regla C1 especificada aunque la implemente otro change: identificador desconocido ⇒ atribución nula |
| El contrato se diseña sin consumidor real y resulta incómodo de usar | El test de integración hace de C16: construye el payload a partir de tipos reales de C03. **Umbral explícito: si la proyección no cabe en unas diez líneas legibles, se arregla el payload, no el test** |
