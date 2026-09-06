# C23 — mediciones y decisiones de la exploración (corpus de conocimiento e indexador)

**Explorado el 2026-09-06**, sobre la rama `ai-eng` limpia, tras el archivado de C22 y `FIX1`.
Este informe es la entrada de `/enrich-us`: recoge lo medido, las decisiones de arquitectura
tomadas y el corpus aprobado documento a documento.

**Todo en solo lectura y sin proveedor.** No se abrió sesión contra PostgreSQL —el contenedor
`jpv-pv-postgres` no estaba levantado el día de la exploración— ni se llamó a ningún LLM ni a
la API de embeddings. Las cifras salen de los dos corpus JSONL versionados en `data/catalog/`.

> **Limitación del método, declarada.** Las cifras son un **proxy sobre texto**: se emparejan
> las formas de superficie de [`vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml)
> (canónicos **y** sinónimos, plegando tildes) contra `name + description` de los 1.200
> productos. No son los atributos que C09 extrajo a `ai.product_document`. Tres sesgos conocidos:
> `oro` absorbe a los productos de `baño de oro`, porque la cadena contiene la palabra; `perla`
> se cuenta dos veces por estar en `materials` **y** en `stone_type`; y `pequeño`, `grande` y
> `mediano` se inflan porque aparecen en la prosa como adjetivos y no solo como etiqueta de
> talla. **Tarea del change: re-medir contra `ai.product_document` con la base levantada** y
> corregir aquí lo que se mueva. Ninguna decisión de este informe depende de la tercera cifra
> decimal; las que dependen de un orden de magnitud están marcadas.

---

## 1. Punto de partida verificado en el repositorio

| Hecho | Dónde | Consecuencia |
|---|---|---|
| `ai.knowledge_document` y `ai.knowledge_chunk` **ya existen**: `doc_type` con check de cinco valores, FK con `ON DELETE CASCADE`, único `(document_id, chunk_index)`, HNSW coseno, GIN sobre `tsv` y **sobre `metadata`** | [`f46c55c056e2`](../../../ai-service/migrations/versions/f46c55c056e2_ai_schema_foundation.py) | **C23 no abre migración.** `metadata jsonb` es la vía para todo campo que falte |
| El módulo de fusión RRF es puro, sin dominio, y **nombra a C23 por escrito** como importador futuro | [`fusion.py`](../../../ai-service/src/jbg_ai/retrieval/fusion.py) | La rama híbrida se hereda; no se reescribe una línea |
| La deuda del cliente de embeddings por petición **está pagada**: singleton en `app.state.retrieval_embed` | [`main.py`](../../../ai-service/src/jbg_ai/api/main.py) | Una consulta de conocimiento en caliente reutiliza cliente y caché |
| La superficie `/v1` está congelada por un MUST que enumera diez rutas; añadir una obliga a regenerar `openapi.json` y acordarlo con el lado .NET | [`ai-service-api-contracts`](../../../openspec/specs/ai-service-api-contracts/spec.md) | **Cero rutas nuevas.** El único consumidor (C30) vive en el mismo proceso |
| `indexing/embeddings.py` declara en su docstring *«C23 reuses this module and must not edit it»* | [`embeddings.py`](../../../ai-service/src/jbg_ai/indexing/embeddings.py) | Se importa, no se toca |
| El diseño §9.1 ya nombra la tool `consultar_conocimiento` del agente de venta | diseño §9.1 | El *routing* ya está decidido por contrato: decide el llamante |

---

## 2. Mediciones sobre el catálogo (1.200 productos: 436 reales + 764 sintéticos)

### 2.1. Materiales — 9 canónicos, reparto muy desigual

| Canónico | Productos | % | Profundidad de ficha |
|---|---:|---:|---|
| `plata` | 630 | 52,5 % | Rica |
| `oro` | 418 | 34,8 % | Rica *(incluye los de baño; ver sesgo)* |
| `latón` | 77 | 6,4 % | Rica |
| `hilo` | 63 | 5,2 % | Media |
| `baño de oro` | 36 | 3,0 % | **Rica** — es el material más frágil y el peor entendido |
| `perla` | 8 | 0,7 % | Media |
| `resina` | 4 | 0,3 % | Compacta |
| `acero` | 3 | 0,2 % | Compacta |
| `cuero` | 1 | 0,1 % | Compacta |

**La invariante se mantiene, la profundidad no.** Una ficha por canónico sigue siendo la regla
testeable —si entra `titanio` en el vocabulario, el test pide su ficha— pero cuatro materiales
con menos de diez productos no sostienen seis secciones. Las fichas compactas son una decisión,
no un descuido.

### 2.2. Multi-material — 12 % del catálogo, y justifica un documento propio

| Materiales por producto | Productos | % |
|---|---:|---:|
| 0 | 118 | 9,8 % |
| 1 | 938 | 78,2 % |
| **2 o más** | **144** | **12,0 %** |

Pares más frecuentes: `oro+plata` 73 · `baño de oro+oro` 31 · `hilo+plata` 25 · `hilo+oro` 15 ·
`baño de oro+plata` 8 · `perla+plata` 7.

Es la evidencia que sostiene **B1 `material-piezas-mixtas`**: una pieza con baño no se limpia
como una de plata, y ese conflicto de cuidados **solo existe en las mezclas**. Sin este
documento, un operador aplicaría a una pieza bicolor la instrucción de la ficha equivocada.

### 2.3. Piedras — la más frecuente es materia orgánica, y ocho canónicos están vacíos

| Piedra | Prod. | Piedra | Prod. | Piedra | Prod. |
|---|---:|---|---:|---|---:|
| `coral` | **102** | `esmeralda` | 22 | `ópalo` | 7 |
| `ámbar` | **75** | `diamante` | 16 | `jade` | 6 |
| `ónix` | 57 | `lapislázuli` | 14 | `madreperla` | 6 |
| `piedra` *(genérico)* | 33 | `rubí` | 13 | `turquesa` | 6 |
| `perla` | 30 | `amatista` | 11 | `nácar` | 5 |
| `cuarzo` | 26 | `citrino` | 10 | `circonita` | 3 |
| `topacio` | 23 | `granate` | 9 | `ágata` · `hematites` | 2 · 2 |
| `zafiro` | 23 | `obsidiana` | 8 | `labradorita` | 1 |

**Sin una sola aparición (8 de 33):** `malaquita`, `howlita`, `aventurina`, `ojo de tigre`,
`piedra luna`, `amazonita`, `jaspe`, `calcedonia`. **No reciben sección**: el corpus describe el
surtido que existe, no el vocabulario que podría existir.

Las dos piedras más frecuentes —`coral` y `ámbar`, 177 productos entre las dos— son **materia
orgánica**, que es la categoría de cuidado más frágil y la que peor tolera los consejos
genéricos. Por eso las fichas se agrupan **por régimen de cuidado y no por dureza**.

### 2.4. Tallas — el hallazgo que funda el documento de medidas

| Etiqueta | Productos | Etiqueta | Productos |
|---|---:|---|---:|
| `S` | 122 | `mini` | 21 |
| `pequeño` | 108 *(inflado por prosa)* | `grande` | 15 |
| `M` | 103 | `XS` | 10 |
| `L` | 87 | `mediano` | 6 |
| `XL` | 83 | `extramini` | 1 |
| | | **`XXS` y `XXL`** | **0** |

Cruce `piece_type × size_label`, doce combinaciones más frecuentes:

```
  pendientes  pequeño  34      colgante    M        26      pulsera     S        22
  pendientes  S        30      pendientes  M        25      anillo      M        21
  colgante    S        27      anillo      XL       25      pulsera     pequeño  21
  anillo      S        26      anillo      L        23      pendientes  XL       20
```

**La letra no es una talla de dedo: es el tamaño de la pieza.** Se aplica a pendientes,
colgantes, collares, pulseras y anillos por igual, y el tipo de pieza que **más** la usa
—`pendientes`, 24,4 % del surtido— no tiene talla en el sentido de ajuste. El documento de
medidas deja de ser «inventar una tabla de milímetros» y pasa a **describir una convención que
los datos demuestran**. Solo la equivalencia en milímetros queda como afirmación ilustrativa.

Dato derivado que alimenta H2: `pendientes` 24,4 % + `colgante` 16,0 % + `cadena` 4,2 % =
**44,6 % del surtido no depende de talla de ajuste**.

### 2.5. Colecciones — la medición corrige una conclusión de la exploración

En la primera pasada dejé fuera un documento sobre Menorca con el argumento de que *«describe
el catálogo, y el catálogo ya está indexado en el otro índice»*. **La medición lo desmiente y la
conclusión se corrige.** De las 28 colecciones reales:

| Colecciones con topónimo menorquín | Productos |
|---|---:|
| `Menorca` · `Fiestas Menorca` | 70 · 15 |
| `Es Caló Blanc` · `Biniacolla` · `Sa Mesquida` | 31 · 26 · 23 |
| `Cala Pregonda` · `Cala Presili` · `Binibeca` · `Cavalleria` | 20 · 19 · 14 · 12 |
| `Esencia Bagur` · `Joia Bagur` | 8 · 5 |

**Que las líneas llevan nombre de calas y cabos reales de Menorca es un hecho del catálogo, no
una historia inventada.** Lo inventado sería atribuir a cada línea una intención de diseño; eso
es lo que se marca `establecimiento`. El documento se admite, y resulta ser uno de los mejor
fundamentados del corpus.

**Y aparece un hallazgo de calidad de catálogo que no buscaba:** **11 de las 28 «colecciones» no
son líneas de diseño** sino cajones operativos — `Varios` (23), `Composturas` (19, o sea
reparaciones), `Tienda` (13), `Aros plata` (14), `Anillos` (11), `Pedida` (10), `Kit Huella`
(9), `Cursos` (6), `Maternidad` (5), `Melia` (3, la cadena hotelera), `Papelería` (3), `Envío`
(1). El documento J solo da sección a las líneas con topónimo. *(`Composturas` confirma además,
desde los datos, que el servicio de reparación existe: refuerza G3.)*

---

## 3. Decisiones de arquitectura tomadas en la exploración

| # | Decisión | Fundamento |
|---|---|---|
| **D1** | **Ninguna ruta HTTP.** `search_knowledge()` es función de librería; C30 la consume en proceso | La superficie `/v1` está congelada por un MUST y mover `openapi.json` obligaría a coordinar con .NET para conectar dos módulos del mismo proceso |
| **D2** | **Ningún router LLM.** Decide el llamante | S10: *«el mejor router es no tener router»*. El diseño §9.1 ya asignó la decisión a la tool `consultar_conocimiento` |
| **D3** | **Identidad doble del chunk**: `id = uuid5(NS, "<doc_slug>#<section_slug>")` y `metadata.citation_id = "<doc_slug>#<section_slug>"` | S11 exige que la cita *resuelva, localice y sea trazable*. Con el corpus en git, el `citation_id` **es** el localizador: abre el fichero, busca el encabezado. Un `uuid4` solo resuelve, y solo a través de la base de datos |
| **D3b** | **Nunca `(document_id, chunk_index)` como identidad de cita** | Insertar una sección en medio desplaza el índice de todas las posteriores y **repunta silenciosamente cada cita**, sin error y sin cambio visible |
| **D4** | **Híbrido vector + léxico fusionado por RRF**, importando `fusion.py`, con la rama léxica compuesta desde los grupos de C20 | Las nueve fichas de material son **estructuralmente idénticas** (mismo esqueleto, mismo registro): el coseno colapsa y lo único que las distingue es el nombre del material, que es un token léxico |
| **D4b** | **Se mide vectorial solo primero.** La rama léxica se queda solo si mueve el número | Cultura del proyecto: C20, C21 y C22 refutaron su propia ficha con medición. Predicción registrada: vectorial puro confundirá `plata` con `acero` en preguntas de cuidados |
| **D5** | **Nada de filtro duro por material detectado** | La spec de `query-expansion` ya fija que los filtros por regla *degradan, nunca excluyen*. «¿Puedo llevar plata y acero juntos?» nombra dos |
| **D6** | **Los dos índices nunca se fusionan** | S10: la procedencia es información y aplanarla la destruye. Un producto es una entidad que se ordena e hidrata; un chunk es una afirmación que se cita |
| **D7** | **Umbral de abstención propio**, `JPV_KNOWLEDGE_DISTANCE_THRESHOLD`, calibrado contra las preguntas fuera de dominio | El 0,65 de productos se calibró sobre documentos de 40-120 palabras. Para una pregunta que el corpus no cubre, **la respuesta correcta es ninguna cita** |
| **D8** | **Paquete `jbg_ai/knowledge/`** (`corpus.py`, `chunking.py`, `indexer.py`, `search.py`), no `indexing/knowledge.py` | **Desviación declarada de la ficha.** El change es dueño de ingesta *y* consulta; meter la consulta en `indexing/` la misfila, y partirla a `retrieval/` pisa la zona de C25 y C26. Los paquetes por capacidad son la convención del repo (`enrichment/`, `families/`) |
| **D9** | **Hash de contenido en `metadata.content_hash`**, no en columna nueva | Evita repetir el bochorno de C22, que declaró «sin migración de ninguna clase» y acabó abriendo una |
| **D10** | **Mini-medición propia**, ~32 preguntas + 4-5 fuera de dominio, en fixture, **sin tocar `ai.eval_run/case/result`** | Esas tablas las crea C24; usarlas convertiría a C24 en prerrequisito y C23 dejaría de ser el 🟢 libre que es |

---

## 4. Etiquetado de procedencia: el origen no, el alcance sí

**Pregunta planteada:** si todos los documentos los va a escribir un LLM, ¿hace falta etiquetar
el origen? **Respuesta: no el origen; sí el alcance de la afirmación.**

El §8.1.1 del diseño ya enseñó la lección cuando el export real obligó a partir `data_origin` de
`text_provenance`: una sola columna *«respondía a dos preguntas independientes y se rompía»*.

| Eje | Pregunta | ¿Varía hoy? | Dónde vive |
|---|---|---|---|
| Quién lo escribió | ¿LLM o el negocio? | **No.** Todo LLM + revisión humana | Sidecar `.meta.json` + README. **Constante ⇒ no es columna** |
| De quién es el hecho | ¿Del mundo o de esta joyería? | **Sí, y dentro de un mismo documento** | `metadata.claim_scope`, **por sección** |

La medición lo demuestra dentro del propio documento de tallas: *«la letra se aplica a
pendientes, colgantes, collares y pulseras»* es comprobable contra los datos con un comando;
*«una `M` de anillo equivale a 54 mm de contorno»* es un compromiso que solo la joyería puede
confirmar. Dos afirmaciones, un documento, dos estatus.

```
metadata.claim_scope   general          comprobable fuera (química, alérgenos, longitudes,
                                        geografía de Menorca). Se puede leer a un cliente
                       establecimiento  compromiso de la joyería. HOY ILUSTRATIVO.
                                        Se marca en la cita y nunca se afirma sin confirmar
metadata.source_ref    opcional         referencia externa, o el comando que re-mide el catálogo
                                        para las afirmaciones verificables contra los datos
```

**Dos valores porque son dos comportamientos.** Una etiqueta que no cambia el comportamiento es
decoración. Y cuando la joyería mande sus textos, el eje «quién lo escribió» deja de ser
constante y **entonces** gana su campo: aditivo, sin migración, sin haberlo especulado hoy.

**Unidad de marcado.** El chunk es `# Título del documento` + `## Título de la sección` + texto,
y el `claim_scope` se declara **por sección**, así que viaja con ese chunk. El documento no lleva
un valor propio: su composición se reporta como recuento (`n` secciones `general`, `m`
`establecimiento`), que es lo que va al README.

---

## 5. El corpus aprobado — 32 documentos, ~161 chunks

Objetivo D5 del diseño: **150-250 chunks**. Los 15 documentos del corte pre-autorizado dan ~80,
la mitad, con un índice tan pequeño que **la abstención no se puede demostrar**. El corte se
expresó en documentos; la cifra que el diseño fija está en chunks. **Se genera todo en este
change.** `doc_type` usa cuatro de los cinco valores del check: `guion_venta` queda a cero.

### Bloque A · Fichas de material — 9 docs `material` · 47 secciones

Una por término canónico de `vocabularies.yaml`. **Invariante testeable.**

Esqueleto (las cuatro primeras, obligatorias en toda ficha):

| Sección | `claim_scope` |
|---|---|
| `## Qué es y cómo se reconoce` | general |
| `## Cuidados y limpieza en casa` | general |
| `## Qué lo estropea` *(agua, cloro, sal, cosmética, roce)* | general |
| `## Piel sensible y alergias` | general |
| `## Cómo envejece y qué esperar` *(pátina, desgaste, pérdida de baño)* | general |
| `## Cómo guardarlo` | general |
| `## Nuestra garantía sobre el baño` — **solo en `material-bano-de-oro`** | establecimiento |

`material-plata` · `material-oro` · `material-laton` (6 secciones cada una) ·
`material-bano-de-oro` (7) · `material-hilo` · `material-perla` (5) ·
`material-resina` · `material-acero` · `material-cuero` (4: se omiten *cómo envejece* y
*cómo guardarlo*).

`material-perla` cruza `materials` **y** `stone_type`. La ficha vive aquí y C1 la referencia; el
test de la invariante debe contemplar el solape.

### Bloque B · Combinaciones y marcajes — 2 docs `material` · 10 secciones

**`material-piezas-mixtas`** *(justificado por el 12 % medido)* — todas `general`:
`## Por qué se combinan dos materiales` · `## Bicolor oro y plata: qué esperar` ·
`## Plata con baño: la parte frágil manda` · `## Hilo y metal en la misma pieza` ·
`## Limpiar una pieza mixta sin estropear nada`

**`material-marcajes-y-punzones`** *(el diccionario de sinónimos hecho explícito: `925`→plata,
`18k`→oro)* — todas `general`: `## Qué significa el 925` · `## Qué significa 750 y 18k` ·
`## Baño de oro y chapado: qué es y qué no` · `## Dónde se busca el punzón en cada pieza` ·
`## Qué piezas no llevan punzón`

### Bloque C · Piedras — 3 docs `material` · 16 secciones · todas `general`

**`piedras-materia-organica`** *(coral 102 + ámbar 75 + perla 30 + nácar 5 + madreperla 6)* —
7 secciones: `## Qué tienen en común y por qué son distintas` · `## Coral` ·
`## Coral y especies protegidas` · `## Ámbar` · `## Perla y nácar` ·
`## Limpieza: lo único que se puede hacer` · `## Qué las arruina en una tarde`

**`piedras-cuarzos-y-gemas-facetadas`** — 5 secciones: `## Qué son y por qué aguantan bien` ·
`## Ónix, cuarzo, amatista y citrino` · `## Ágata y granate` · `## Zafiro, rubí y diamante` ·
`## Circonita: qué es y qué no`

**`piedras-opacas-porosas-y-tratadas`** — 4 secciones:
`## Por qué porosa cambia todo el cuidado` · `## Esmeralda: la gema tratada que parece dura` ·
`## Lapislázuli, turquesa, jade, ópalo y obsidiana` · `## Nunca ultrasonidos, nunca vapor`

### Bloque D · Medidas y tallas — 4 docs `talla` · 20 secciones

**`tallas-como-se-miden-en-nuestro-catalogo`** — el documento fundamentado en §2.4:

| Sección | `claim_scope` |
|---|---|
| `## La letra es el tamaño de la pieza, no la talla de dedo` | general · `source_ref` a la medición |
| `## A qué tipos de pieza se aplica y con qué frecuencia` | general · `source_ref` |
| `## mini, pequeño, mediano y grande: escalas de motivo` | general · `source_ref` |
| `## Qué mide la letra en cada tipo de pieza` | **establecimiento** |
| `## Qué piezas no llevan talla` | general · `source_ref` |

> Este documento **no** repite la tabla de anillos: la nombra y remite a `tallas-anillos`. Dos
> versiones de la misma tabla en dos documentos es una incoherencia de corpus esperando a que
> alguien corrija una sola de las dos.

**`tallas-anillos`** — el único tipo de pieza donde la letra compromete un **ajuste**, y por eso
el único con tabla de equivalencia:

| Sección | `claim_scope` |
|---|---|
| `## Cómo medir tu talla en casa con hilo o papel` | general |
| `## Medir a partir de un anillo que ya tienes` | general |
| `## Cuándo medir: temperatura, hora del día y nudillo` | general |
| `## De la talla española a los milímetros` | general |
| `## Nuestra escala de letras: qué talla es cada una` | **establecimiento** |
| `## Entre dos tallas, y por qué la banda ancha cambia la respuesta` | general |
| `## Qué aro se puede ajustar y cuál no` | general |

**La convención de la casa, fijada el 2026-09-06** *(decisión D16 del `design.md`, con el
razonamiento completo)*. La escala `XS`–`XL` **no es ningún sistema normalizado de anillo**: no
es la española, ni la ISO 8653, ni la estadounidense, ni la británica de letras. Es una escala
de prenda aplicada a **todo** el catálogo, y para una red de puntos de venta en hoteles y
aeropuerto es la elección correcta: quien compra allí no vuelve a por un ajuste ni sabe su talla
española. La tabla, en tallas españolas **enteras, tres por letra y sin solape**:

| Letra | Talla española | Circunferencia interior | Diámetro interior |
|---|---|---|---|
| `XXS` * | 4 – 6 | 44 – 46 mm | 14,0 – 14,6 mm |
| `XS` | 7 – 9 | 47 – 49 mm | 15,0 – 15,6 mm |
| `S` | 10 – 12 | 50 – 52 mm | 15,9 – 16,6 mm |
| `M` | 13 – 15 | 53 – 55 mm | 16,9 – 17,5 mm |
| `L` | 16 – 18 | 56 – 58 mm | 17,8 – 18,5 mm |
| `XL` | 19 – 21 | 59 – 61 mm | 18,8 – 19,4 mm |
| `XXL` * | 22 – 24 | 62 – 64 mm | 19,7 – 20,4 mm |

\* **Por encargo, no de surtido** — son los dos únicos peldaños del vocabulario con **cero
apariciones** en los 1.200 productos (§2.4). La convención los explica en lugar de fingir que no
existen.

`circunferencia (mm) = talla española + 40` es la regla española de siempre, comprobable fuera:
sección `general`. Que `M` sean las tallas 13-15 **es una decisión de la casa**: sección
`establecimiento`. Es el mejor ejemplo del corpus de por qué el alcance se declara por sección.

**Reglas de oficio que el documento debe recoger** (todas `general`): una banda de más de 6 mm
calza más prieta y pide subir una talla · con el nudillo marcado se elige por el nudillo y se
sube una talla, con bolas de ajuste para que el aro no gire · se mide al final del día y a
temperatura normal, nunca tras el baño en agua fría, **y en verano el dedo varía hasta una talla
entera**, que es el caso de esta red · entre dos tallas se sube, y en verano siempre.

**Y qué se puede ajustar**: ±2 tallas un aro liso o de labrado parcial en plata u oro. **No se
ajusta** una alianza con piedras en todo el contorno, un aro cuyo motivo recorre la banda entera
—se rompería el dibujo—, un aro hueco, **ninguna pieza con baño de oro** —el ajuste quema el
baño— ni el latón y el acero. Esto **ata tres documentos**: la tabla aquí, el límite por material
en `material-bano-de-oro`, `material-laton` y `material-acero`, y el servicio en
`politica-reparaciones-y-ajustes`. Los tres deben decir lo mismo, y hay test que lo comprueba.

**`tallas-collares-y-cadenas`** — todas `general`: `## Longitudes habituales y dónde cae cada
una` · `## Cómo medir la longitud que ya usas` · `## Escote y longitud` · `## Colgante y cadena:
cuándo no pegan`

**`tallas-pulseras-y-tobilleras`** — todas `general`: `## Cómo medir muñeca y tobillo` ·
`## Cuánta holgura dejar` · `## Rígidas y abiertas: se miden distinto` · `## Tobilleras: la
medida que casi nadie sabe`

### Bloque E · Uso, cuidado y entorno — 4 docs `faq` · 18 secciones

**`cuidados-generales`** — `## La regla de la última en ponerse y la primera en quitarse` ·
`## Limpieza semanal: paño, agua tibia y jabón neutro` · `## Lo que nunca: lejía, dentífrico,
ultrasonidos` *(`general`)* · `## Cuándo llevarla a la joyería` *(`establecimiento`)*

**`joyas-playa-piscina-y-deporte`** — el diferencial: la red de puntos de venta son hoteles de
Menorca. Todas `general`: `## Agua salada: qué le hace a cada material` · `## Cloro: el enemigo
del baño y de la plata` · `## Arena y roce` · `## Crema solar y aceites` · `## Agua fría y
anillos que se caen` · `## Qué joya sí puede ir a la playa`

**`perfume-cremas-y-cosmetica`** — todas `general`: `## El orden correcto: joya al final` ·
`## Perfume y plata` · `## Cremas, aceites y el baño de oro` · `## Laca, tintes y productos de
peluquería`

**`guardar-y-viajar-con-joyas`** — todas `general`: `## Cada pieza en su bolsa` · `## Humedad,
luz y calor` · `## Cadenas que se enredan` · `## Viajar: qué va en cabina y qué no`

### Bloque F · Piel, alergias y seguridad — 2 docs `faq` · 9 secciones · todas `general`

**`niquel-y-piel-sensible`** — `## Qué es la dermatitis de contacto` · `## Dónde suele estar el
níquel en una joya` · `## Qué materiales del catálogo son seguros` · `## Latón y baño de oro: el
riesgo real` · `## Piercings recientes y lóbulos irritados`

**`joyas-y-ninos`** *(incluido por decisión del 2026-09-06)* — `## Pendientes de bebé: cierre y
peso` · `## Piezas pequeñas y riesgo de atragantamiento` · `## Cuándo perforar y qué material
elegir` · `## Cadenas y seguridad al dormir`

### Bloque G · Servicio de la joyería — 4 docs `politica` · 19 secciones · **todas `establecimiento`**

Bloque íntegramente ilustrativo. Es el que demuestra el marcado y el que el README declara.

| Documento | Secciones |
|---|---|
| `politica-devoluciones-y-cambios` | Plazo · Estado en que se admite · Piezas personalizadas · Compras en punto de venta de hotel · Cómo se tramita |
| `politica-garantia` | Qué cubre · Qué no cubre · Baño de oro y desgaste · Plazo · Qué hace falta para reclamar |
| `politica-reparaciones-y-ajustes` | Ajuste de talla: qué anillo se puede y cuál no · Soldaduras y cierres · Enfilado de collares · Plazos y presupuesto |
| `politica-grabado-y-encargos` *(incluido el 2026-09-06)* | Qué piezas admiten grabado · Tipos de grabado · Encargos a medida · Plazos · Devolución de lo personalizado |

### Bloque H · Regalo y ocasión — 2 docs `faq` · 9 secciones

Escritos en **modo descriptivo, nunca imperativo**: es la regla que sustituye a `guion_venta`.

**`ocasiones-y-tradicion`** — todas `general`: `## Aniversarios y sus materiales` *(plata 25,
perla 30, oro 50)* · `## Bodas y alianzas` · `## Comunión y bautizo` · `## Cumpleaños y piedras
del mes`

**`regalar-sin-saber-la-talla`** — `## Qué tipos de pieza no dependen de talla` *(`general` ·
`source_ref`: 44,6 % del surtido)* · `## Cadenas y colgantes: la apuesta segura` ·
`## Pendientes: por qué casi siempre valen` · `## Si es un anillo: cómo averiguar la talla sin
preguntar` *(`general`)* · `## Nuestra política de cambio por talla` *(`establecimiento`)*

### Bloque I · Glosario — 1 doc `faq` · 6 secciones · todas `general`

**`glosario-de-joyeria`** — espejo semántico del diccionario de C20; es el documento que más
ayuda a la rama léxica: `## Collar, gargantilla, cadena y colgante: no son lo mismo` ·
`## Anillo, sortija y alianza` · `## Criollas, aros y pendientes de botón` · `## Pulsera,
esclava y brazalete` · `## Cierres: mosquetón, reasa, presión` · `## Engastes y acabados`

### Bloque J · Menorca y el origen de las colecciones — 1 doc `faq` · 7 secciones

*(Incluido el 2026-09-06. La exploración lo había descartado; la medición de §2.5 corrige la
conclusión: los topónimos son un hecho del catálogo.)*

| Sección | `claim_scope` |
|---|---|
| `## Las colecciones llevan nombre de calas y cabos de Menorca` | general · `source_ref` |
| `## Es Caló Blanc, Binibeca y Biniacolla: la costa sur` | general |
| `## Cala Pregonda, Cala Presili y Cavalleria: la costa norte` | general |
| `## Sa Mesquida y la tramontana` | general |
| `## Las fiestas de Sant Joan y el jaleo` | general |
| `## Marés, caliza y el color de la piedra menorquina` | general |
| `## Qué inspira cada línea en nuestro taller` | **establecimiento** |

**Contención de la decisión 4 del diseño.** El documento habla de **Menorca y de por qué las
líneas se llaman como se llaman**, nunca de los productos que contienen. Ninguna sección nombra
un SKU, un producto ni un precio; solo las líneas con topónimo reciben mención, y los once
cajones operativos de §2.5 quedan fuera. Es la frontera que impide que el índice de conocimiento
empiece a duplicar el de catálogo.

### Recuento

| Bloque | Docs | Secciones |
|---|---:|---:|
| A materiales | 9 | 47 |
| B combinaciones y marcajes | 2 | 10 |
| C piedras | 3 | 16 |
| D medidas y tallas | 4 | 20 |
| E uso y entorno | 4 | 18 |
| F piel y seguridad | 2 | 9 |
| G servicio *(todo `establecimiento`)* | 4 | 19 |
| H regalo y ocasión | 2 | 9 |
| I glosario | 1 | 6 |
| J Menorca y colecciones | 1 | 7 |
| **Total** | **32** | **161** |

`doc_type`: `material` 14 · `talla` 4 · `faq` 10 · `politica` 4 · `guion_venta` **0**.
`claim_scope`: ~136 `general` · ~25 `establecimiento` (15,5 % del corpus, y es el número que va al
README).

---

## 6. Reglas de autoría

1. Un documento = un fichero Markdown en `data/knowledge/`, con `# Título` y luego solo
   secciones `##`. **Nada de texto antes de la primera sección**: un preámbulo sin sección es un
   chunk sin localizador, o sea una cita que no localiza.
2. Una sección = **una afirmación citable**, 80-250 palabras. Si pasa del tope, **falla la
   ingesta**: parte el autor, no el código. Misma disciplina que el tope de 1.000 caracteres de
   C06b.
3. Cada sección declara su `claim_scope` en un comentario HTML bajo el encabezado
   (`<!-- claim_scope: general -->`), que el chunker **retira antes de construir `content`**, para
   que no entre ni en el embedding ni en el `tsv`. Sin la marca, la ingesta falla.
4. **Modo descriptivo, nunca imperativo.** «El aniversario de plata es el 25º», no «ofrécele
   plata por su 25º». Un chunk imperativo recuperado dentro de un prompt es indistinguible de una
   instrucción: convertiría el propio corpus en superficie de inyección, y C31 aún no existe.
5. **Ninguna sección nombra un SKU, un producto ni un precio.** La decisión 4 del diseño es que
   el conocimiento es general; un precio en el corpus contradice además la regla de los
   placeholders `{{price}}` / `{{stock}}` de C30.
6. `content` del chunk = `# Título del documento` + `## Título de la sección` + texto. El `tsv` es
   columna generada sobre `content`, así que el título entra a la vez en el índice léxico y en el
   embedding: es lo único que desambigua nueve fichas de material casi gemelas, y sale gratis.
7. Cada documento aporta **una pregunta** al mini-set de evaluación, más 4-5 preguntas **fuera de
   dominio** que deben devolver cero.

---

## 7. Producción del corpus: prompts versionados, subagentes y ventanas separadas

**Esto es planificación obligatoria del change, no una nota al margen.**

**El corpus no cabe en una ventana de contexto.** 161 secciones de 80-250 palabras son ~25.000
palabras de salida útil, y a eso hay que sumar, **en cada petición**, las reglas de autoría, el
esqueleto del bloque y la evidencia medida que lo justifica. Intentarlo de una vez produce
exactamente el fallo que las invariantes cazarían tarde: las primeras fichas se olvidan, las
últimas derivan del esqueleto y el conjunto pierde la homogeneidad que hace comparables a nueve
fichas de material.

**Reparto: un subagente o una ventana nueva por bloque**, nunca por corpus, y nunca por documento
suelto — partir por documento perdería la coherencia interna del bloque, que es justo lo que hay
que preservar.

| Encargo | Bloque | Docs | Secciones |
|---|---|---:|---:|
| 1 | A materiales frecuentes: `plata`, `oro`, `baño de oro`, `latón`, `hilo` | 5 | 31 |
| 2 | A materiales residuales: `perla`, `resina`, `acero`, `cuero` + B combinaciones y marcajes | 6 | 26 |
| 3 | C piedras | 3 | 16 |
| 4 | D medidas y tallas | 4 | 20 |
| 5 | E uso y entorno | 4 | 18 |
| 6 | F piel y seguridad + H regalo | 4 | 18 |
| 7 | G servicio *(todo `establecimiento`)* | 4 | 19 |
| 8 | I glosario + J Menorca | 2 | 13 |

**Prompts versionados en `ai-service/prompts/knowledge/`**, siguiendo el patrón que ya existe
para `catalog-synth/` y `enrichment/`, con `prompt_version` y modelo sellados en el sidecar
`.meta.json` como hace
[`catalog-synthetic.meta.json`](../../../data/catalog/synthetic/generated/catalog-synthetic.meta.json).
Un prompt **por bloque**, no por documento: los bloques comparten esqueleto, y es el esqueleto lo
que hay que fijar por escrito.

**Cada prompt de bloque debe llevar, explícitamente:** el esqueleto de secciones exacto con sus
`claim_scope`; las siete reglas de autoría del §6 completas, no resumidas; la evidencia medida
que justifica ese bloque (productos por material, pares multi-material, cruce
`piece_type × size_label`, topónimos); la prohibición de nombrar SKU, producto o precio; y la
instrucción de devolver **solo ficheros Markdown**, uno por documento, sin comentario alrededor.

**Revisión por bloque según llega**, no al final. Son ~4-6 minutos por documento y ~2-3 horas en
total; acumularlos hasta el cierre convierte al único revisor en el cuello de botella que el §7.8
del diseño ya identificó.

**Reproducibilidad.** El sidecar sella `generator_version`, `model`, `prompt_version`,
`generated_at` y el recuento por `doc_type` y por `claim_scope`. Es lo que permite al README
declarar la composición del corpus con una cifra y no con una impresión.

---

## 8. Lo que este change NO hace

Ruta `/v1/knowledge/*` · router LLM · migración de Alembic · tocar `indexing/embeddings.py` ·
fusionar los dos índices · indexar guiones de venta · construir RAGAS *(es §11.3, de C24)* ·
persistir *pitches* *(regla de C30)* · reranking · usar `ai.eval_run/case/result` *(las crea
C24)*.

---

## 9. Abierto

1. **Re-medir contra `ai.product_document`** con la base levantada y corregir §2 donde el proxy
   de texto se desvíe. Afecta sobre todo a `oro` (absorbe los de baño), a `perla` (contada dos
   veces) y a `pequeño` / `grande` / `mediano` (inflados por prosa).
2. **`XXS` y `XXL` están en el vocabulario y no en el catálogo.** El documento D1 describe la
   escala que existe; queda anotado que el vocabulario tiene dos peldaños sin uso.
3. Cuando la joyería aporte textos reales, el eje «quién lo escribió» deja de ser constante y
   gana su campo. Hoy no se especula: vive en el sidecar.
