# C30 — decisiones de exploración: la capa de generación, y los cinco huecos entre el contrato y el diseño

**Change:** `add-assist-generation-with-rule-warnings` (C30) · **Fecha:** 2026-09-13
**Árbol explorado:** `ai-eng` en `0743096` · **Rama de implementación:** pendiente, derivada de `ai-eng`

Este informe recoge lo que la exploración **comprobó sobre el árbol** y las once decisiones de
arquitectura que salen de ello. Es la entrada de `/enrich-us` y del `/opsx:propose` posterior.

Contiene **mediciones estáticas nuevas sobre el corpus y el contrato** —tamaños de sección,
distribución de `claim_scope` y `doc_type`, matriz de presencia de secciones, campos obligatorios
del esquema congelado— tomadas con el árbol delante. No contiene mediciones **de ejecución**: C30
no ha corrido, y ninguna cifra de recuperación, latencia o coste real se mueve aquí. Las cifras de
C18b, C23, C25 y C28 se **citan** de sus informes y no se re-miden.

Su razón de ser es que la ficha del plan describe un C30 que el contrato congelado **no puede
servir**. Al comprobarlo, cinco de sus supuestos resultaron falsos del árbol. Se corrigen aquí.
Es el **décimo change consecutivo cuya exploración refuta lo escrito antes**.

---

## 1. El inventario, comprobado sobre el árbol y no sobre la ficha

### 1.1 · El andamio que ya existe, y que C30 no debe reconstruir

| Pieza | Estado verificado | Qué aporta a C30 |
|---|---|---|
| [`retrieval/orchestrator.py`](../../../ai-service/src/jbg_ai/retrieval/orchestrator.py) | `retrieve_products()` vivo, fusión en dos etapas desde C25, `match_reasons` con procedencia real desde C21 | Los candidatos y su *por qué* — no hay que inventar vocabulario de razones |
| [`knowledge/search.py`](../../../ai-service/src/jbg_ai/knowledge/search.py) | `search_knowledge()` **es un callable, no una ruta**, y su docstring declara que *«the only consumer is C30»* | La recuperación citable, ya construida y medida |
| [`knowledge/indexer.py`](../../../ai-service/src/jbg_ai/knowledge/indexer.py) | `document_id(slug)` y `chunk_id(doc_slug, sec_slug)` = `uuid5(KNOWLEDGE_NAMESPACE, …)` | Direccionamiento por **clave primaria**: D-E y D-F se construyen sobre esto, sin migración |
| [`knowledge/corpus.py`](../../../ai-service/src/jbg_ai/knowledge/corpus.py) | `material_sheet_slug(canonical)` y `missing_material_sheets()` | El invariante 1:1 ficha↔material, ya sostenido por un test |
| [`retrieval/abstention.py`](../../../ai-service/src/jbg_ai/retrieval/abstention.py) | Regla relativa de C25, **activa por defecto** (`jpv_abstention_enabled = True`, `α = 0,03`, `N = 15` en [`settings.py`](../../../ai-service/src/jbg_ai/config/settings.py)) | La señal de «el catálogo no puede contestar», construida y **encendida** — lo que falta es que el camino de assist la **honre y la reporte** (D-G) |
| [`enrichment/llm.py`](../../../ai-service/src/jbg_ai/enrichment/llm.py) | Puerto `EnrichLlm` + adaptador LiteLLM, temperatura 0, *backoff* de proveedor, un reintento de parseo | El patrón de cliente generativo a replicar (D-K) |
| `prompts/<área>/<vN>.md` + `PROMPT_VERSION` | Convención viva en `enrichment/`, `catalog-synth/`, `knowledge/`, con test que fija fichero↔constante | El versionado de prompt, sin decidir nada nuevo |
| `ai-service/src/jbg_ai/assist/` | **No existe** | La zona de C30, limpia |
| `IAiGatewayClient` | Cinco métodos: `SearchAsync`, `EnrichAsync`, `HealthAsync`, `SuggestFamiliesAsync`, `AuditFamiliesAsync`. **Ninguno de assist** | `/v1/assist/sale` tiene **cero consumidores hoy** |

**La última fila gobierna cuatro decisiones.** El coste de mover el contrato está en su **mínimo
histórico ahora mismo** y crece de forma monótona a partir de C34.

### 1.2 · Los cinco supuestos de la ficha que el árbol refuta

| # | La ficha supone | El árbol dice | Decisión |
|---|---|---|---|
| **H1** | Los candidatos se agrupan por `family_id` | `AssistGroup.family_id` es **obligatorio y no nullable** en el esquema congelado, y **~58 % del catálogo no tiene familia** (C18b: 156 familias / 486 miembros sobre ~1.168 filas indexadas) | D-A |
| **H2** | `POST /v1/assist/sale` se sirve con una consulta de texto | Su único consumidor previsto, C34, expone **`GET /api/ai/products/{id}/sales-assist`** y `.../substitutes` — las dos **ancladas a pieza**. Y `AssistRequest` no tiene `product_id`, con `query` obligatoria | D-B |
| **H3** | Los cuatro avisos los calcula C30 | Dos son afirmaciones de stock, y `SearchHit.qty_bucket` está declarado como algo que **nunca sale al cable**, además de poder estar desfasado. C34 hidrata la verdad | D-C |
| **H4** | El pitch lleva `citations[]` verificables | `Citation` del contrato tiene **3 campos** (`source`, `snippet`, `product_id`) contra los **10** de `KnowledgeCitation`. Se pierden `citation_id` y **`claim_scope`** — 25 de 161 fragmentos son compromisos de la casa | D-D |
| **H5** | C31 se encarga de lo que está fuera de dominio, después | La abstención medida por C25 es **10 %**: activa por defecto, abstiene en **2 de 20** consultas fuera de dominio y en **0 de 43** contestables, así que **18 de 20 llegan con candidatos**. El golden set tiene **20 de 72** fuera de dominio, su categoría mayor | D-G |

**Dos contradicciones menores anotadas de paso.** (a) La tabla maestra del §2 dice que la cadena
crítica *«pasa a arrancar en C34»*: arranca en **C30**, que C34 lleva de prerrequisito. (b) El §9.1
del diseño dice *«Siete tools, no ocho»* y la ficha de C32 ya las corrigió a seis el 12 de
septiembre; el diseño no se sincronizó.

### 1.3 · Mediciones estáticas del corpus, tomadas en esta sesión

Sobre los 32 documentos de [`data/knowledge/`](../../../data/knowledge/), excluyendo `README.md`
—que es la guía de autoría y aporta un ejemplo de cada marca, razón por la que un `grep` ingenuo
devuelve 26/137 en lugar de 25/136:

```
doc_type      material 14 · faq 10 · politica 4 · talla 4          = 32   ✔ cuadra con C23
claim_scope   general 136 · establecimiento 25  (15,5 %)                  ✔ cuadra con C23
```

**Matriz de presencia de secciones en los once ficheros `material-*`:**

```
FICHA                        QUE-ES  CUIDADOS  ESTROPEA  PIEL  ENVEJECE  GUARDAR  extra
material-plata                 g        g         g       g       g        g
material-oro                   g        g         g       g       g        g
material-laton                 g        g         g       g       g        g
material-bano-de-oro           g        g         g       g       g        g     ⚠ E
material-perla                 g        g         g       g        —       g
material-hilo                  g        g         g       g       g         —
material-acero                 g        g         g       g        —        —
material-cuero                 g        g         g       g        —        —
material-resina                g        g         g       g        —        —
material-marcajes-y-punzones  ── esqueleto DISTINTO: «Qué significa el 925» · «750 y 18k» · …
material-piezas-mixtas        ── esqueleto DISTINTO: «Bicolor oro y plata» · «Plata con baño» · …

g = claim_scope: general   ·   E = claim_scope: establecimiento
Tamaño por sección: 127–163 palabras, media ~140. ~200 tokens en castellano (ESTIMACIÓN,
no medición: el contador real está en `evals/cag_run.py` si hace falta la cifra exacta).
```

**Dos hallazgos de esta matriz, y los dos cambian la forma de una regla, no su número:**

1. **`material-bano-de-oro` tiene una séptima sección, `Nuestra garantía sobre el baño`, y es
   `claim_scope: establecimiento`** — la única de las once fichas. Su último párrafo dice
   literalmente *«Como todo compromiso de la casa, estas condiciones se confirman en tienda antes
   de trasladarlas a un cliente.»* Una regla del tipo «mete las secciones de la ficha» metería una
   garantía de taller en un argumentario que nadie pidió, y sólo para las piezas bañadas.
2. **Dos de los once ficheros `material-*` no son fichas de material.** `marcajes-y-punzones` y
   `piezas-mixtas` comparten prefijo y no esqueleto, y **no están cubiertos por el invariante
   1:1** de C23, que es contra los **nueve** términos de `materials.terms` en
   [`vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml) (`plata`,
   `oro`, `baño de oro`, `hilo`, `latón`, `acero`, `resina`, `cuero`, `perla`). Una regla
   ingenua por slug de material **devuelve nada** para una pieza mixta: fallo silencioso justo en
   el caso difícil.

---

## 2. Las once decisiones

### D-A · El contrato se renegocia ahora, y en un solo bloque

**Decisión.** `openapi.json` se regenera en C30a, con todos los movimientos juntos:

```python
# ── AssistRequest ─────────────────────────────────────────────
  query:      str | None        # era obligatoria (min_length=1)
+ product_id: str | None        # NUEVO — el ancla de pieza
+ model_validator: AL MENOS UNO de los dos  (ver D-B)

# ── AssistGroup ───────────────────────────────────────────────
  family_id: str | None         # era obligatoria y NO nullable
+ invariante de spec:  family_id is None  ⇒  len(members) == 1

# ── AssistGroupMember ─────────────────────────────────────────
+ match_reasons: list[str]      # NUEVO — mismo vocabulario que RetrievalResult
                                # resuelve el `reason` por candidato del §7.7

# ── Citation ─────────────────────────────────────── reforma ──
+ citation_id:    str           # "material-plata#cuidados-y-limpieza-en-casa"
+ document_title: str
+ section_title:  str
+ claim_scope:    str           # general | establecimiento
+ doc_type:       str
+ score:          float
  snippet:        str           # se mantiene (= content)
  product_id: str | None        # se mantiene — a qué candidato respalda
− source:         str           # RETIRADO: lo sustituye citation_id

# ── AssistResponse ────────────────────────────────────────────
+ abstained:      bool          # NUEVO — y NO llamarlo low_confidence (ver D-G)
+ prompt_version: str | None    # null en C30a; "assist/v1" en C30b
  warnings: list[str]           # MISMO TIPO, vocabulario CERRADO de códigos (ver D-C)
  intent: str                   # se mantiene, con semántica estructural (ver D-B)
```

**Evidencia.** `IAiGatewayClient` no tiene método de assist, C34 y C36 no existen, y el README de
`ai-service` ya fija la doctrina: *«Regenerating is a contract negotiation, not a chore. A failing
snapshot test means the frozen boundary moved — agree the change with whoever owns the .NET client
before regenerating.»* La contraparte de esa negociación es la misma persona, y el precedente es
propio: **C18a y C18b regeneraron el snapshot en el mismo change en que movieron la frontera**.

**Alternativas descartadas.** (a) *`family_id` sintético* (`solo:<uuid>` o el `product_id`) — es
una mentira en el cable: .NET y el frontend tendrían que reconocer un prefijo que ningún esquema
declara, el aviso `family_has_variants` no debe disparar nunca en un grupo sintético y nada en el
tipo lo impide, y el test de C36 `should require variant confirmation when family has multiple
members` pasaría trivialmente. Va contra la cultura del propio repo, que se negó a añadir una ruta
*«in order to connect two modules of the same process»* y que insiste en que *«absence is NOT
zero»*. (b) *Mover sólo el mínimo* y declarar el resto como limitación — deja `claim_scope` fuera
del cable, que es H4, y obliga a una segunda negociación cuando C34 ya exista y sea caro.
(c) *Descartar los productos sin familia* — pierde el 58 % del catálogo.

**Consecuencia.** Un solo `openapi.json` regenerado, en C30a, antes de que exista un consumidor.
`test_openapi_snapshot_is_stable` se actualiza con él. La spec `ai-service-api-contracts` recibe
deltas `MODIFIED` sobre *Sale assistance groups results by family* y *Generated text never
contains resolved price or stock*.

### D-B · Tres modos de assist, con «al menos uno» y no «exactamente uno»

**Decisión.** `/v1/assist/sale` sirve tres modos, y la validación exige **al menos uno** de
`product_id` / `query`:

| modo | `product_id` | `query` | caso de mostrador | consumidor |
|---|---|---|---|---|
| **M1** | — | ✓ | *«¿cómo se limpia la plata?»* · *«es un regalo y no sé la talla»* | bucle de C32 (`consultar_conocimiento`, `pedir_aclaracion`) y escenarios de C38 |
| **M2** | ✓ | — | *«véndeme esta pieza»* | C34 `/sales-assist` → card de C36 |
| **M3** | ✓ | ✓ | *«¿este anillo se puede mojar?»* | C34 `/sales-assist?question=` → caja en el card de C36 |

`intent` se deriva **estructuralmente y sin heurística**: `product_pitch` en M2, que es inequívoco,
y `unclassified` en M1 y M3, declarado como *«la clasificación llega en C31»*.

**Evidencia.** El flujo por consulta **ya está servido**: la spec viva
[`ai-assisted-search`](../../../openspec/specs/ai-assisted-search/spec.md) entrega
`POST /api/ai/search` con hidratación, truncado en orden de recuperación, degradación y registro de
episodio, y [`assisted-search-panel`](../../../openspec/specs/assisted-search-panel/spec.md) cierra
con *«la selección se reporta en el momento del clic»* y *«la búsqueda de origen viaja con el
producto hasta la caja»*. Ninguna de las dos tiene caja de pregunta. Y C23 construyó el corpus
**asumiendo que sí la hay**: su fixture de fuera de dominio dice *«son preguntas que un operador
podría teclear de verdad **en el mismo cuadro de texto**»*.

**El hueco que esto descubre, y que se declara aquí.** El corpus de C23 —32 documentos, 161
fragmentos, indexado y calibrado— **no tiene hoy ninguna ruta hasta la pantalla del joyero**: C34
expone dos rutas ancladas a pieza y C36 pinta un card. Diez de los 32 documentos son mostrador
puro (`joyas-playa-piscina-y-deporte`, `niquel-y-piel-sensible`, `regalar-sin-saber-la-talla`,
`perfume-cremas-y-cosmetica`, `joyas-y-ninos`, `guardar-y-viajar-con-joyas`, `cuidados-generales`,
`ocasiones-y-tradicion`, `menorca-y-el-origen`, `glosario`) y ninguno es alcanzable.

**Superficie de operario elegida:** **M2** tal como C34 y C36 ya lo llevan escrito, más **M3** como
`?question=` en esa misma ruta y una caja de pregunta en ese mismo card. Es el camino más barato
que existe para poner el corpus en pantalla, y cubre la situación real: el cliente tiene el anillo
en la mano y pregunta. **M1 se implementa en Python y no recibe superficie de operario en esta
ronda**; su consumidor es C32 y el arnés de C38.

**Alternativas descartadas.** (a) *Exactamente uno de los dos* — excluye M3, que es el modo de
mejor relación valor/coste. (b) *Ruta nueva `/v1/assist/product`* — rompe el MUST de diez rutas y
C23 argumentó contra añadir rutas por comodidad. (c) *Que C34 sintetice una consulta desde los
metadatos de la pieza* — el pitch acaba siendo sobre piezas parecidas y no sobre la elegida, la
pieza puede no salir primera, y se paga un segundo *embedding* por un producto ya conocido.
(d) *Bloque de respuesta de M1 sobre los resultados del panel* — el de más valor para el PF, porque
es donde el rechazo cortés de C31 se **ve** y no sólo se mide, pero exige ruta nueva en .NET y
requisito nuevo en el panel. Queda como crecimiento declarado de C36 o change aparte.

### D-C · Los avisos de stock son de C34, no de C30

**Decisión.** El reparto es por autoridad sobre el dato, y `warnings` lleva **códigos de
vocabulario cerrado**, no prosa:

| código | dato que necesita | quién lo calcula |
|---|---|---|
| `family_has_variants` | roster por `family_id` sobre `ai.product_document` | **C30** |
| `size_label_missing` | `ai.product_document.size_label` | **C30** |
| `stock_critical` | stock real en el punto de venta | **C34**, tras hidratar |
| `family_members_out_of_stock` | stock real por miembro | **C34**, tras hidratar |

El copy castellano lo escribe el **frontend**.

**Evidencia.** `SearchHit.qty_bucket` lo declara sin ambigüedad: *«Carried for the availability
demotion and never emitted: an exact stock figure does not exist here and a bucket on the wire
would be the beginning of one.»* Y el §15.10 fija que la proyección **degrada y nunca elimina**
porque puede desfasarse minutos. Un aviso «stock crítico» mostrado cuando hay doce unidades en el
cajón no es un matiz: es la credibilidad del asistente en el mostrador. Para el copy en el
frontend hay precedente explícito en la spec viva del panel: *«The panel MUST NOT render the
retriever's raw match reason values, which are engineering vocabulary»*, con su mapeo a badge y su
*fallback* neutro para valores desconocidos.

**El precedente exacto, y es la segunda vez.** El plan ya registró este movimiento en la ficha de
C34: *«La exclusión por falta de stock es de este change, y no está en C26 […] Estaba especificada
**dos veces** […] y C26 la retiró de la suya al implementarse.»* Éste es el segundo caso de la
misma forma. Queda anotado para que no haya un tercero.

**Alternativas descartadas.** (a) *Los cuatro en Python desde `qty_bucket`* — rompe el invariante
del cable y puede emitir un aviso falso. (b) *Prosa castellana en Python* — produce una lista de
procedencia mezclada cuando C34 apila los suyos, que el frontend no puede distinguir ni estilar.
(c) *Cambiar `warnings` a `list[Warning{code, params}]`* — movimiento de esquema mayor sin
necesidad: el tipo `list[str]` con vocabulario cerrado da toda la legibilidad por máquina.

**Consecuencia.** La ficha de C30 **pierde** dos avisos; la de C34 los **gana**, calculados tras
hidratar. `test_warnings_are_rule_derived_not_model_generated` se vuelve fuerte: el vocabulario es
un enum cerrado que el modelo nunca ve.

### D-D · Las citas: sólo corpus, sólo las que el pitch usó, con `claim_scope` en el cable

**Decisión.** Tres reglas, las tres verificables:

1. **`citations[]` son fragmentos del corpus de conocimiento, y sólo eso.** El anclaje al catálogo
   se expresa con `match_reasons` (D-A), nunca con una cita al propio producto.
2. **Son las que el pitch **usó**, no las que el retriever devolvió.** El modelo declara en su
   salida estructurada los `citation_id` en los que se apoya.
3. **`claim_scope` viaja siempre**, y una cita colgante nunca sale del servicio.

La integridad referencial se comprueba **en código, después de generar**: todo `citation_id` de la
respuesta ∈ el conjunto que `search_knowledge` devolvió. Política ante fallo: un reintento con
instrucción más dura, y si reincide se entrega la parte estructurada **sin pitch**.

**Evidencia.** El docstring de `KnowledgeCitation` es explícito: *«`claim_scope` travels with the
fragment and is not optional: a commitment of the establishment read aloud as if it were a fact of
the world is the failure mode the whole marking mechanism exists to prevent»* — y son **25 de 161**
fragmentos, el 15,5 %. El `citation_id` de C23 *«resolves, locates and opens the file and the
heading in git»*, que son las tres propiedades que
[S11 · Citación y atribución verificable](../../Sesiones%20Master%20AIEng/S11_RAG_avanzado/Citacion%20y%20Atribucion%20verificable.md)
exige: resolver, **localizar** y ser trazable. La misma nota fija que la integridad referencial
*«no se confía al modelo: se verifica en código, después de generar»*, y que la única política
inaceptable es ignorar una cita colgante. Y la frontera de capas ya está bien: el servicio emite
`document_id` + localizador y **nunca URLs**; `citation_id` es exactamente ese par.

**Alternativas descartadas.** (a) *Meter `citation_id` en `source`* — mecánicamente funciona y
pierde `document_title`/`section_title`, la mitad legible por humanos, dejando al frontend
pintando un slug. (b) *Emitir todo lo recuperado como citación* — es decoración, literalmente el
fallo que S11 describe, y hace imposible la comprobación de integridad. (c) *Citar el catálogo* —
los metadatos del producto ya viajan en la respuesta; citarlos no verifica nada.

### D-E · El argumentario de M2 se funda en lookup determinista, con lista blanca de secciones

**Decisión.** En M2 **no hay búsqueda vectorial**. El contexto se direcciona por clave primaria con
`chunk_id(document_slug, section_slug)`:

```
contexto = para cada material declarado (tope 2, en el orden que la pieza los declara):
             material-<slug>#cuidados-y-limpieza-en-casa
             material-<slug>#piel-sensible-y-alergias
           + si la pieza declara ≥2 materiales:
             material-piezas-mixtas#limpiar-una-pieza-mixta-sin-estropear-nada

invariantes: · sólo claim_scope == "general"
             · LISTA BLANCA de slugs, nunca «todas las secciones de la ficha»
             · la ausencia de una sección es normal, no un error  (acero no tiene ENVEJECE)
             · marcajes-y-punzones NUNCA entra en un argumentario: es ficha de consulta,
               y «¿qué significa el 925?» es una pregunta → M3
             · cada fragmento va ETIQUETADO con su material dentro del contexto

parámetro:   la lista de slugs y el tope de materiales viajan por parámetro, como en
             C20/C23/C25, para que C30b barra 1/2/3 secciones en un proceso
```

**Evidencia.** `CUIDADOS` y `PIEL` están presentes y son `general` en las **nueve** fichas
canónicas (§1.3). El coste **no decide nada**: a ~200 tokens por sección y con `gpt-4o-mini` a
0,15/0,60 USD por millón —[`pricing.yaml`](../../../ai-service/evals/golden/pricing.yaml),
verificado el 2026-09-07— la diferencia entre 2 y 6 secciones por material es de **décimas de
céntimo por llamada**, menos de 0,40 USD por cada mil argumentarios. Lo que decide es otra cosa:

- **El escalón del `claim_scope`.** El riesgo no crece linealmente con el número de secciones; es
  un escalón, y está en `material-bano-de-oro#nuestra-garantia-sobre-el-bano` (§1.3, hallazgo 1).
- **Atención y homogeneidad.** S11 fija que el medio del contexto pesa menos, y aquí es peor porque
  las nueve fichas son *«structurally identical»* y *«cosine collapses by homogeneity»*: el riesgo
  no es que el modelo ignore un fragmento, es la **atribución falsa** entre materiales.
- **Combustible numérico, y la interacción con D-H.** Las fichas llevan `925`, `750`, `18k`,
  micras. La puerta de lista blanca de D-H **admite cualquier cifra presente en el contexto
  citado**: meter la ficha de plata para una pieza de acero haría pasar un «925» erróneo. Ampliar
  el contexto **degrada la puerta que debía protegernos**.
- **Fatiga de citación.** S11: *«una citación que nadie lee no verifica nada […] a nivel de
  componente suele ser el equilibrio correcto»*. El card de C36 lleva citas desplegables; doce son
  un cajón que nadie abre.

**El riesgo que sobrevive, y su mitigación.** En M2 un filtro por material es **total por
construcción** —una pieza de acero no puede recibir la ficha de plata, porque nadie la pide—, así
que lo que queda es atribución cruzada **entre los materiales que la pieza sí declara**. Un anillo
de `plata` con `baño de oro` lleva dos fichas, las dos correctas, y *«la plata tolera bien el
agua»* pertenece a una parte y no a la otra. Un filtro no ayuda: los dos materiales lo pasan. Lo
que ayuda es el tope de 2, el etiquetado por material dentro del contexto, y la sección que el
corpus ya escribió para esto: `material-piezas-mixtas#plata-con-bano-la-parte-fragil-manda`.

**Alternativas descartadas.** (a) *Todas las secciones de la ficha* — cruza a compromisos de la
casa en las piezas bañadas. (b) *Búsqueda vectorial también en M2* — paga un *embedding* y
reintroduce el riesgo de cita espuria para resolver algo que una clave primaria resuelve exacto.
(c) *Una sola sección* — deja el argumentario en recitado de metadatos; queda como brazo del
barrido, no como valor de partida.

### D-F · M3 filtra por slug, y el filtro es asimétrico

**Decisión.** En M3 sí hay k-NN sobre la pregunta, y se acota **sólo dentro del conjunto
homogéneo**:

```
EXCLUIR        material-<slug>  para cada slug de las NUEVE fichas canónicas que la
               pieza NO declara                        ← típicamente 8 señuelos fuera

PASAR SIEMPRE  faq (10) · politica (4) · talla (4) · piedras-* (3)
               material-piezas-mixtas · material-marcajes-y-punzones
```

Implementación, sobre la **clave primaria** y sin migración ni columna nueva:

```python
excluded = [document_id(material_sheet_slug(t))
            for t in CANONICAL_MATERIALS if t not in piece.materials]
#   → cláusula `AND d.id <> ALL(:excluded)` en compile_vector_sql / compile_lexical_sql,
#     con la misma forma que el _DOC_TYPE_CLAUSE condicional que ya existe,
#     más un parámetro en search_knowledge y en el protocolo KnowledgeSearchIndex
```

**Evidencia.** El filtro es seguro precisamente por las dos propiedades que hacen peligroso ese
conjunto: las nueve son **mutuamente excluyentes por construcción** (invariante 1:1 de C23 contra
`materials.terms`) y **confundibles por construcción** (mismo esqueleto, mismo registro, mismo
vocabulario — y por eso C23 tuvo que añadir la rama léxica). Todo lo de fuera es temático y no
específico de material. Rendimiento: irrelevante — 161 fragmentos, y C23 midió la rama léxica en
**~3 ms** sobre el corpus entero.

**Por qué NO un filtro general por material.** Restringir el corpus a las fichas del material de
la pieza corta **23 de los 32 documentos** (§1.3) y con ellos casi toda pregunta real de
mostrador: la piscina, el arreglo, la talla, el regalo sin talla. Sería falsa abstención en masa, y
el proyecto ya zanjó esa asimetría en C25 con medición: *«silenciar una consulta que la tienda SÍ
puede contestar es un fallo visible en el mostrador, mientras que no abstenerse en una imposible
muestra cinco piezas que no encajan y el operario lo ve»*.

**Efecto secundario a favor.** El filtro **refuerza la abstención en vez de debilitarla**: quitar
ocho señuelos casi idénticos deja un conjunto admitido más pequeño y más discriminativo, y el
umbral 0,51 controla la admisión —C23: *«a branch that returns few candidates has already earned
the right to be believed»*. Si el único fragmento sobre umbral era la ficha del material
equivocado, filtrarlo produce abstención, **y es la correcta**.

**En M1 no hay filtro posible**, porque no hay pieza ni materiales declarados. El riesgo de
atribución cruzada es máximo justo donde no se puede acotar: es otra razón para que M1 no reciba
superficie de operario en esta ronda, y una entrada concreta para los casos adversarios de C38
—*preguntar por un material describiéndolo sin nombrarlo*.

### D-G · La abstención se activa en el camino de assist, y no se llama `low_confidence`

**Decisión.** C30 **no clasifica intención** —eso es C31—, pero **no genera pitch cuando la capa de
recuperación dice que el catálogo no puede contestar**. La regla relativa de C25 **ya corre**, así
que lo que falta no es encenderla: es que el camino de assist la **honre y la reporte**. El valor
efectivo viaja **por parámetro** y no leído del entorno, como en C20, C23 y C25, para que el arnés
pueda barrer configuraciones en un proceso. La respuesta lo declara en **`abstained: bool`**.

**Evidencia.** `jpv_abstention_enabled` está **en `true` por defecto**, con `α = 0,03` y `N = 15`
([`settings.py`](../../../ai-service/src/jbg_ai/config/settings.py)), y su propio descriptor de
campo lo fija: *«at the configured band it abstains on 2 of the 20 and on NONE of the 43»*. O sea
que **18 de 20 consultas fuera de dominio llegan con candidatos**, y el golden set tiene **20 de
72** en esa categoría. Sin esta puerta, C30 contestaría *«¿qué tiempo hace mañana?»* con cinco
familias de joyería y un argumentario convencido, y lo haría durante toda una vuelta de manivela
—porque el arreglo es C31 y C31 lleva C30 de prerrequisito. Se comprobó si el orden se puede
invertir: no limpiamente, porque C31 lleva *«rechazo cortés sin llamar al retriever»* y
*«validación de salida contra JSON schema»*, y las dos necesitan que la ruta y el generador existan.

> **Corregido el 2026-09-13, el mismo día.** La primera versión de este informe decía que la regla
> estaba **desactivada por defecto**, tomándolo del §583 del informe de implementación de C25
> —donde sí lo estaba, con `α = 0,05` y `N = 10`—. Ese era un estado intermedio del apply: los
> ajustes vivos son `true`, `0,03` y `15`. **La decisión no cambia y su motivo tampoco**, porque lo
> que la sostiene es el 18 de 20, que es idéntico en la banda configurada. Lo que cambia es el
> trabajo: C30a no enciende una regla apagada, **propaga y declara** una que ya decide.

**Por qué el nombre importa.** `low_confidence` ya tiene en este repo un significado medido
—consenso entre ramas— que está **anticorrelacionado** con lo que aquí hace falta: dispara en
**1 de 20** fuera de dominio y en **10 de 43** contestables. Reutilizar el nombre importaría el
sentido equivocado y nadie lo notaría hasta medir.

**Alcance por modo.** `abstained` es significativo sobre todo en **M1**. En **M2** no hay
recuperación que abstenerse: si la pieza no está indexada eso es un error, no una abstención, y se
reutiliza el patrón de C26 —`source_document` devuelve `None` y el router convierte los tres casos
inservibles (desconocido, inactivo, sin indexar) en tres frases distintas. En **M3** la parte de
conocimiento ya se abstiene devolviendo cero citas, que es el comportamiento de C23.

**Alternativas descartadas.** (a) *Embarcar el hueco declarado* — la categoría más medida del
golden set queda contestada con prosa confiada, y el vídeo del PF lo enseñaría. (b) *Fusionar C30 y
C31* — la regla 5 del §1 ordena partir, no juntar. (c) *Un mini-router por palabras clave* —
trabajo que C31 borra, y el repo ya pagó por andamio una vez con C25bis.

### D-H · La puerta numérica es por lista blanca, y corre en ejecución

**Decisión.** Antes de responder, el pitch pasa una puerta determinista: **sólo puede contener
cifras que aparezcan literalmente en el payload estructurado que se le entregó** (tallas, mm,
`925`, dígitos de SKU, `citation_id`) más los tokens `{{price}}` y `{{stock}}`. Cualquier otro
numeral rechaza. Política: un reintento con instrucción más dura, y si reincide se entrega la
parte estructurada **sin pitch**.

**Evidencia.** El mecanismo de placeholders protege un flanco y deja el otro abierto:

```
modelo escribe "{{price}}"  ──▶ .NET sustituye              ──▶ ✓
modelo escribe "{{price}}"  ──▶ .NET no puede resolver      ──▶ ✗ rechaza  (§7.7, C34)
modelo escribe "39,90 €"    ──▶ .NET no ve nada sin resolver ──▶ ✓✓ PASA
                                └─ el operario lee un precio inventado
```

El validador determinista del §11.3 lo caza **en evaluación, no en ejecución**, y la ficha de C30
exige la garantía en ejecución con `test_response_contains_no_literal_price_or_stock_number`. Un
prompt no da garantías: S11 lo dice como regla —*«No intentes resolver en el prompt lo que toca
resolver verificando»*— y describe la forma exacta de esta puerta como *anclaje numérico*, que aquí
es pertenencia a un conjunto en lugar de `min ≤ x ≤ max`.

**Por qué lista blanca y no lista negra.** El dominio está lleno de números legítimos: `talla 12`,
`18 mm`, `SKU JBG-0042`, `plata de ley 925`. La ficha de C38 ya reconoce el problema con
`test_ignores_numbers_that_are_sizes_or_skus`. Una lista negra se equivoca en los dos sentidos; la
blanca además caza pesos, micras y recuentos de piedras inventados.

**Consecuencia y aviso.** Esta puerta **depende del contexto que se le dé** (ver D-E): cuanto más
ancho el contexto, más permisiva la lista blanca. Es un argumento para estrechar el contexto, no
para confiar en la puerta.

### D-I · El pitch no se persiste, eso incluye no loguearlo, y el arnés es la excepción declarada

**Decisión.** Lo único sin copia durable es el **`pitch`**. Las citas (slugs estables, ya
persistidos en el corpus), los avisos (códigos recalculables) y los `match_reasons` (los produce el
retriever) no están afectados. **Y el texto del pitch no se escribe en ningún log.**

Lo que sí se loguea: `trace_id`, `prompt_version`, `model`, `usage`, latencia, los `citation_id`
usados —slugs, no contenido—, los códigos de aviso, la decisión de abstención, `len(pitch)` y un
hash. Suficiente para diagnosticar todo menos la redacción exacta.

**Evidencia — por qué no se persiste, de más fuerte a menos:**

1. **Resucitaría `CareInstructions` por la puerta de atrás.** El §7.7 concede *«se elimina
   `CareInstructions` como atributo del producto, de acuerdo»*, y el corpus —una ficha por
   material, **no por producto**— es el sustituto aceptado. Un pitch persistido en el producto es
   un campo de texto por producto, escrito por un modelo, que nadie revisó. La objeción que el
   diseño concedió estaría de vuelta, y esta vez indexada.
2. **Volvería a entrar en el índice.** `ai.product_document.doc_text` lo construye C11 en orden
   fijo desde metadatos aprobados; un texto sentado en el producto acabará incluido por algún
   constructor futuro, y la salida del modelo se convierte en contexto de recuperación. C23
   rechazó el caso vecino con una frase que aplica palabra por palabra: **cero documentos
   `guion_venta`**, porque *«an imperative fragment retrieved into a prompt is indistinguishable
   from an instruction, so the corpus would become an injection surface»*.
3. **Su verdad tiene media vida corta.** Persistir la versión resuelta congela un precio
   presentado como actual; persistir la plantilla obliga a rehidratar, y para entonces el roster,
   los avisos y la disponibilidad también se han movido.
4. **La política de revisión del §7.8 no tiene hueco para él**, y hay precio medido: C28 cerró con
   **20,9 %** de corrección ponderada y **32,1 s** por perfil sobre 204.
5. **Podredumbre de citas.** El `citation_id` es `uuid5` sobre slugs para que insertar una sección
   no repunte las citas, pero el **contenido** de una sección puede reescribirse. Un pitch
   persistido seguiría «resolviendo» contra texto que ya no dice aquello: la *«alucinación con
   coartada»* de S11, fabricada por el tiempo y no por el modelo.
6. **Los compromisos de la casa.** 25 de 161 fragmentos son `establecimiento`, hoy ilustrativos. Un
   pitch persistido que cite uno lo convierte en registro durable, y la ficha del baño de oro dice
   explícitamente que esas condiciones se confirman en tienda antes de trasladarlas.

**No es por coste.** Cachear el pitch sería más barato. No se persiste porque su verdad caduca.

**Evidencia — por qué el log cuenta.** C17 está desplegado, y una línea de log es almacenamiento
durable fuera de la base de datos. Si el texto va a CloudWatch: (a) el invariante es falso una capa
más abajo y `test_pitch_is_not_persisted_anywhere` afirmaría una propiedad que el sistema incumple
—un test que pasa sobre una propiedad falsa es peor que no tener test; (b) la retención es la de
CloudWatch, no una decisión que nadie tomó; (c) **se pierde el ámbito que la respuesta sí tenía** —
`AssistResponse` es un `ScopedResponse` y devuelve `effective_pos_id`, *«always the token claim,
never the body value»*, mientras una línea de log no tiene ámbito y quien lee logs lee el
argumentario de todas las tiendas, cuando `projection.py` llama a un punto de venta comodín
*«exactly what must not exist»*; (d) del lado .NET, un log posterior a la hidratación llevaría el
**precio resuelto**, lo único que todo el mecanismo de placeholders existe para mantener fuera del
texto generado. Y C39 declara propiedades comprobables a un evaluador externo: una afirmación falsa
en el README es peor que una ausente.

**Que el texto no se guarde es viable porque es re-derivable.** Temperatura 0 más prompt versionado
(D-K) significa que el log no necesita el texto. Salvedad honesta: re-derivable para el estado
**actual** del producto y del corpus, no para el histórico — coherente con que el pitch no tenga
una verdad histórica que merezca guardarse.

**La excepción, delimitada aquí para que C38 no choque con esto.** C38 corre **RAGAS sobre el
subconjunto con citas**, y eso necesita el texto generado. Las tablas ya existen: `ai.eval_run` /
`eval_case` / `eval_result` de C24, cuya migración anota *«C38 adds generation metrics to the same
runner»*. Así que **la prohibición es del camino de servicio**, y el arnés es la excepción
declarada: artefactos en `evals/results/` y filas atadas a un `run_id`, un `git_sha` y un
`prompt_version`, fuera del camino del operario. Si no queda escrito en la spec de C30, la primera
sesión de C38 rompe el invariante sin darse cuenta o se queda bloqueada por él.

### D-J · C30 se parte en C30a y C30b, y el corte deja una ablación gratis

**Decisión.**

```
C30a · «assist estructurado y citable»            CERO llamadas a proveedor
  ├─ movimiento de contrato completo (D-A)  ── al momento más barato posible
  ├─ tres modos con «al menos uno» (D-B)
  ├─ agrupación por family_id nullable + family_roster en ProductSearchPort
  ├─ avisos por reglas: family_has_variants · size_label_missing (D-C)
  ├─ filtro de slug asimétrico en M3 (D-F)
  ├─ puerta de abstención + abstained (D-G)
  └─ CITAS VERIFICABLES YA:  M2 lookup determinista (D-E) · M1/M3 search_knowledge
     pitch: ""   ·   prompt_version: null   ·   usage: 0
  ✓ determinista de punta a punta, testeable sin un solo fake de LLM
  ✓ DESBLOQUEA C34 y C36: dependen de la FORMA, no de la prosa

C30b · «el argumentario»
  ├─ prompts/assist/v1.md + esquema de salida estructurado
  ├─ el modelo DECLARA qué citation_id usó → integridad referencial en código (D-D)
  ├─ puerta numérica por lista blanca (D-H)
  └─ usage y prompt_version reales
```

**Evidencia.** Contando entregables —paquete nuevo, prompt, puerto LLM, agrupación, método de
roster con su SQL, avisos, integración de conocimiento, filtro de slug, verificación de citas,
puerta numérica, puerta de abstención, movimiento de contrato con regeneración y snapshot, cableado
del router, capability nueva y tests de todo— son dos sesiones y no una. La regla 5 del §1 lo
prevé: *«Si un change se desborda de la sesión, se parte y se entrega primero la mitad que
desbloquea el grafo.»*

**El corte deja algo que no estaba buscado.** C30a entrega **citas verificables sin una sola
llamada a un proveedor**: `search_knowledge` ya existe y el lookup de material es determinista. Así
que C30a demuestra por sí solo recuperación, atribución resoluble y abstención, todo medible, y
C30b añade la prosa como **capa separable cuyo valor se mide contra C30a**. Es la estructura de
ablación que el §11.2 y C39 piden.

**Contra-argumento reconocido.** C30a solo no demuestra «generación» para el PF. Con prórroga
abierta y equipo de uno el riesgo es bajo, pero es real y queda dicho.

**Identificadores propuestos** (renombrar un change del plan es decisión de quien lo mantiene):
`add-assist-structure-and-rule-warnings` y `add-assist-pitch-generation`.

### D-K · Modelo, temperatura y prompt versionado, por coherencia y reproducibilidad

**Decisión.** `gpt-4o-mini` vía LiteLLM con `JPV_RAG_LLM_*`, **temperatura 0**, y prompt versionado
en `prompts/assist/v1.md` con `PROMPT_VERSION = "assist/v1"` fijado por test contra el fichero.

**Evidencia.** Es exactamente el patrón que C09 ya corrió en real sobre 1.178 perfiles, y el que
[`enrichment/llm.py`](../../../ai-service/src/jbg_ai/enrichment/llm.py) implementa con su *backoff*
de proveedor y su reintento de parseo. El modelo está en
[`pricing.yaml`](../../../ai-service/evals/golden/pricing.yaml) a 0,15/0,60 USD por millón,
verificado el 2026-09-07. Temperatura 0 es además lo que hace viable D-I: el texto no se guarda
porque es re-derivable.

**Consecuencia.** Ninguna llamada real a un LLM en tests unitarios —regla transversal del §1—:
fakes inyectados por la misma costura de constructor que usa `LiteLlmEnrichClient`.

---

## 3. Mapa de deltas

### Contrato y specs

| Artefacto | Delta | Decisión |
|---|---|---|
| `ai-service/openapi.json` | **Regenerado** con el bloque completo, en C30a | D-A |
| `openspec/specs/ai-service-api-contracts` | `MODIFIED` *Sale assistance groups results by family* · `MODIFIED` *Generated text never contains resolved price or stock* · `MODIFIED` *Versioned OpenAPI snapshot…* (nota de regeneración) | D-A, D-H |
| `openspec/specs/knowledge-corpus` | `MODIFIED` para el filtro por documento y el direccionamiento por `chunk_id` | D-E, D-F |
| `openspec/specs/retrieval-abstention` | `MODIFIED`: la decisión de la regla —ya activa— se **propaga al camino de assist y se declara** en la respuesta, con el valor efectivo por parámetro | D-G |
| **capability nueva `assist-generation`** | `ADDED`: los tres modos, agrupación, avisos por códigos, citas, no-persistencia, puerta numérica. **Nombre fijado el 13 sep**: C30b añade requisitos sobre ella en vez de crear otra, y `sale-assist` se descartó porque nombra el caso de uso y no la capacidad, con `assisted-search-panel` y `ai-assisted-search` ya ocupando ese registro semántico | todas |

### Fichas del plan

| Ficha | Entra | Sale |
|---|---|---|
| **C30** | ancla de pieza y tres modos · bloque de contrato · `family_roster` en el puerto · filtro de slug en M3 · puerta de abstención · puerta numérica · integridad referencial · partición a/b | avisos `stock_critical` y `family_members_out_of_stock` |
| **C34** | `?question=` en `/sales-assist` · los dos avisos de stock **tras hidratar** · apilado sobre los de Python | — |
| **C36** | caja de pregunta en el card · tabla de copy para los códigos de aviso | — (su test `should render citations when pitch has sources` pasa a tener fuente real) |
| **C38** | la excepción de persistencia del arnés, escrita · casos adversarios de material descrito sin nombrar | — |
| **Diseño §9.1** | sincronizar *«Siete tools, no ocho»* → **seis**, ya corregido en la ficha de C32 el 12 sep | — |
| **Plan §2** | corregir *«la cadena crítica pasa a arrancar en C34»* → arranca en **C30** | — |

---

## 4. Los tres spikes, antes de escribir código

1. **El umbral de conocimiento contra consultas de producto, en dos brazos.** El 0,51 se calibró
   con preguntas de conocimiento frente a fuera de dominio, **nunca con consultas de producto**, y
   M1 recibe ese texto. Pasar las **72 consultas del golden set** por `search_knowledge` **con y
   sin el filtro de slug de D-F**, contando citas espurias y abstenciones en cada brazo. Mismo
   coste que una medición suelta, el doble de información, y es la primera cifra de C30 que puede
   entrar en la tabla de ablaciones de C39. *(M2 y M3 no dependen de esto: M2 no usa vectores y M3
   parte de una pregunta humana.)*
2. **Reutilización del vector de consulta.** El camino de assist ya embebe el texto para el
   retrieval y `search_knowledge` lo embebe otra vez dentro. Mismo cliente, misma `EMBEDDING_DIM`,
   `model_version_key` construida igual en los dos sitios. Si la costura es viable, el coste
   marginal de consultar el conocimiento baja a una sentencia SQL sobre 161 filas. **Verificar
   antes de asumirlo.**
3. **Cardinalidad del roster.** C18b midió 486 miembros en 156 familias —~3,1 de media—, pero hay
   familias de 7 y 8 (`Colgante estrella de mar` nominó 8 huérfanos). El roster necesita **tope
   declarado**, no confianza en la media.

---

## 5. Esqueleto de tareas revisado

### C30a · assist estructurado y citable

**1 · Puerta de entrada y línea base**
- Línea base de las dos suites, por **nombres** y no por recuento (`git stash push -u`, correr,
  `git stash pop`). Backend y frontend vienen rojos de fábrica; el criterio es el conjunto de
  nombres.
- `openspec validate --all --strict` en verde antes de tocar nada.

**2 · Los tres spikes del §4**, con sus cifras escritas antes de decidir sobre ellas.

**3 · El movimiento de contrato (D-A)**
- Esquemas Pydantic, `model_validator` de «al menos uno», invariante `family_id is None ⇒ un
  miembro`, regeneración de `openapi.json` con `canonical_openapi_settings()`, snapshot.

**4 · El puerto y el roster**
- `family_roster(family_id, …)` en `ProductSearchPort` + implementación SQL sobre
  **`ai.product_document` únicamente** (el puerto no lee `public`), con el tope del spike 3.
- Sirve a la vez el aviso `family_has_variants` y la futura tool `listar_familia` de C32.

**5 · El paquete `assist/`**
- Agrupación por `family_id` (nullable), avisos por códigos cerrados, `intent` estructural.
- Direccionamiento determinista de M2 por `chunk_id` (D-E), con lista blanca parametrizada.
- Filtro de slug asimétrico en M3 (D-F), en las dos sentencias y en el protocolo.
- Puerta de abstención por parámetro y `abstained` (D-G).
- Cableado del router: stub cuando `STUB_MODE=true`, real cuando no.

**6 · Verificación**
- `test_variants_grouped_by_family_id` · `test_warnings_are_rule_derived_not_model_generated` ·
  `test_citations_reference_retrieved_chunk_ids_only` · un test del invariante de grupo sin familia
  · un test de que ninguna sección `establecimiento` entra en un argumentario de M2 · un test de
  que el filtro de slug deja pasar `faq`/`politica`/`talla`/`piedras` y `piezas-mixtas`.
- Comparación final de nombres contra la línea base del paso 1.

**7 · Specs y documentación** con las cifras del §1.3 y del §4 delante.

### C30b · el argumentario

**1 · Prompt y esquema**
- `prompts/assist/v1.md` + `PROMPT_VERSION = "assist/v1"` con su test de fichero↔constante.
- Salida estructurada donde el modelo **declara los `citation_id` que usó**.

**2 · Puerto LLM**, replicando la costura de `LiteLlmEnrichClient`: temperatura 0, un reintento de
parseo, *backoff* de proveedor, fake inyectable.

**3 · Las dos puertas**
- Integridad referencial de citas (D-D), con su política de reintento y degradación.
- Puerta numérica por lista blanca (D-H), con `925`, tallas, mm y dígitos de SKU admitidos por
  pertenencia al contexto y no por regex de excepción.

**4 · No persistencia (D-I)**
- `test_pitch_is_not_persisted_anywhere` con listener `before_cursor_execute` contando DML, no con
  «el módulo no importa un repositorio».
- Un test de que el log no contiene el texto: sólo longitud, hash y los `citation_id`.

**5 · Verificación**
- `test_response_contains_no_literal_price_or_stock_number` · `test_pitch_is_not_persisted_anywhere`
  · barrido de 1/2/3 secciones con su efecto sobre la tasa de rechazo de la puerta numérica.
