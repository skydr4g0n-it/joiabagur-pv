# C23 — mediciones de implementación (corpus de conocimiento e indexador)

**Medido el 2026-09-06**, al implementar `add-knowledge-corpus-and-indexer`. Recoge lo que
la mini-medición devolvió, la decisión sobre la rama léxica, el umbral calibrado, la latencia
que hereda C30 y la re-medición del catálogo que el §9 del
[informe de exploración](c23-exploration-measurements.md) dejó abierta.

**Complementa, no sustituye**, a aquel informe: allí está el corpus aprobado documento a
documento y las quince decisiones de arquitectura; aquí, lo que salió al construirlo.

---

## 0. Lo que se construyó

| Pieza | Resultado |
|---|---|
| Corpus | **32 documentos, 161 secciones** en `data/knowledge/`, más su guía de autoría y el sidecar `_corpus.meta.json` |
| `doc_type` | `material` 14 · `talla` 4 · `faq` 10 · `politica` 4 · **`guion_venta` 0** |
| `claim_scope` | **136 `general` · 25 `establecimiento`** — el 15,5 %, la cifra que va al README |
| Paquete | `ai-service/src/jbg_ai/knowledge/`: `corpus`, `chunking`, `indexer`, `search`, `sizing`, `offline`, `measure`, `cli` |
| Prompts | Ocho, uno por bloque, en `ai-service/prompts/knowledge/v1/` |
| Tests | **91** en `tests/knowledge/`, de los que 3 corren contra PostgreSQL con pgvector |
| Suite completa | **795 pasan, 0 fallan** (`uv run pytest`, con Docker levantado) |
| Migraciones | **cero**. `openapi.json` **byte a byte idéntico** |

Los recuentos coinciden **exactamente** con los que el §5 del informe de exploración fijó de
antemano. No es casualidad ni suerte: el esqueleto de secciones iba literal en los ocho prompts
y el validador de ingesta lo comprueba.

---

## 1. La rama léxica se queda, y por medición

La predicción registrada en D7 era: *«vectorial puro confundirá `plata` con `acero` en preguntas
de cuidados»*, porque las nueve fichas de material son estructuralmente idénticas —mismo
esqueleto, mismo registro, mismo vocabulario— y lo único que las distingue es el nombre del
material, un token léxico corto ahogado en prosa compartida.

Sobre las 32 preguntas del fixture —una por documento, la que cada documento declara en su marca
`eval_question`— más 5 fuera de dominio, al umbral calibrado:

| Configuración | Recall@3 | MRR | Abstención |
|---|---:|---:|---:|
| **Híbrido** (vector + léxica, RRF) | **78,1 %** (25/32) | **0,729** | **100 %** (5/5) |
| Vectorial solo | 71,9 % (23/32) | 0,688 | 100 % (5/5) |
| **Diferencia** | **+6,2 pp** | **+0,042** | 0 |

**La rama se queda.** Y el detalle importa más que el agregado: las **dos** preguntas que el
híbrido recupera y el vectorial pierde son las de `material-cuero` y `material-resina`, dos de
las cuatro fichas compactas — las de los materiales con menos surtido, cuyo texto es más corto y
comparte esqueleto con las demás. Es la predicción cumplida exactamente donde más apretaba.

**Y no cuesta abstención**: las dos configuraciones abstienen en las cinco preguntas fuera de
dominio. Esto es lo que no se podía dar por supuesto — una rama léxica que ganase recall a costa
de citar lo que no debe habría sido un mal negocio en un sistema de atribución.

### Lo que el híbrido no arregla

Siete preguntas siguen sin recuperar su documento en el top 3, y conviene mirarlas porque tres
de ellas **no son fallos de recuperación**:

- *«¿Se puede agrandar un anillo de oro y hasta cuántas tallas?»* y *«¿Se puede agrandar de talla
  un anillo de acero?»* devuelven `politica-reparaciones-y-ajustes#ajuste-de-talla-que-anillo-se-puede-y-cual-no`,
  que **responde la pregunta**. El fixture las cuenta como fallo porque asigna un documento
  esperado por pregunta, y el límite de ajuste vive a propósito en tres documentos que dicen lo
  mismo (D16). Es una limitación del fixture, no del índice, y se declara en lugar de maquillarse.
- Las cuatro restantes —`material-plata`, `material-laton`, `niquel-y-piel-sensible`,
  `piedras-materia-organica`— sí son fallos, y todas contra el embebedor *offline* del §3.

---

## 2. El umbral, calibrado *offline*: 0,81

> **Superado por el §8.** Este apartado registra lo que el barrido *offline* dio, que es lo que
> el change pudo medir sin proveedor. Con el índice real poblado, la misma regla da **0,51**, y
> ese —y no este— es el valor que `Settings` lleva. Se conservan los dos porque la diferencia
> entre ellos es el dato.

Sustituye al 0,65 provisional heredado de productos, que se calibró sobre documentos de 40-120
palabras y no sobre prosa de 130.

| Umbral | Recall@3 | MRR | Abstención | Citas fuera de dominio |
|---|---:|---:|---:|---:|
| 0,70 | 31,2 % | 0,297 | 100 % | 0 |
| 0,75 | 59,4 % | 0,578 | 100 % | 0 |
| 0,78 | 71,9 % | 0,703 | 100 % | 0 |
| **0,81** | **78,1 %** | **0,729** | **100 %** | **0** |
| 0,82 | 78,1 % | 0,729 | 100 % | 0 |
| 0,83 | 78,1 % | 0,729 | 100 % | 0 |
| 0,84 | 78,1 % | 0,729 | 80 % | **1** |
| 0,90 | 78,1 % | 0,734 | 20 % | 4 |

**La regla de D8, tal como está escrita, es una conjunción que ningún valor satisface**: pide el
valor más estricto que mantenga la abstención en cero *sin perder ninguna* pregunta con
respuesta, y el recall se agota en el 78 % mucho antes de que la abstención se rompa. Leída al
pie de la letra no calibraría nada. Se aplica por lo que significa:

1. **Cero citas fuera de dominio es una restricción**, no un término que se negocie contra el
   recall. Una cita bien formada sobre una pregunta que el corpus no cubre es el fallo que este
   change entero existe para evitar.
2. Dentro de esa banda, **se maximiza Recall@3**.
3. **Los empates los gana el valor más estricto**, que es la palabra que la propia regla usa.

Aflojar de 0,81 a 0,83 no responde **ni una pregunta más**, y a partir de 0,84 empieza a citar
lo que no debe: la primera que cae es *«¿Qué talla de zapato equivale a un 39 europeo?»*, la
trampa de vocabulario del fixture, que devuelve
`regalar-sin-saber-la-talla#si-es-un-anillo-como-averiguar-la-talla-sin-preguntar`. Funcionó
exactamente como estaba diseñada.

---

## 3. La limitación del método, declarada

**La medición corre sin proveedor, porque la spec lo exige** —*«MUST run offline, without calling
an embedding or language model provider»*— y porque su resultado no puede depender del día. El
barrido usa `knowledge/offline.py`: un embebedor determinista de bolsa de palabras con n-gramas
de carácter, 1.536 dimensiones y distancia coseno en `[0, 2]`, el mismo dominio que devuelve
`<=>`.

| Lo que compra | Lo que cuesta |
|---|---|
| Reproducibilidad exacta: mismo corpus y mismo fixture, mismos números en cualquier máquina, sin clave y sin contenedor. Una regresión en el troceado, en la fusión o en el umbral se ve como un número movido y no como ruido del proveedor | Realismo absoluto. Puntúa **solape léxico, no significado**: no sabe que «¿se puede mojar?» y «agua salada» son la misma pregunta. Su distribución de distancias **no** es la de `openai/text-embedding-3-small` |

**Consecuencia, y es la que hay que retener: lo que queda calibrado es la *regla*; el *número*
es provisional.** El 0,81 hay que volver a medirlo contra el embebedor de producción sobre un
índice real antes de que C30 lo ponga delante de un cliente. Queda como verificación posterior
declarada, no como supuesto.

> **Cerrada el 2026-09-06, y el aviso se quedó corto.** El §8 la ejecuta: contra el embebedor
> real el 0,81 **cita cuatro de las cinco preguntas fuera de dominio**. No era una imprecisión
> del número, era el mecanismo de abstención inoperante.

Los cuatro fallos genuinos del §1 son, casi con seguridad, artefactos del mismo método: son
preguntas —*«¿por qué se pone negra la plata?»*, *«¿por qué una pulsera dorada deja la muñeca
verde?»*— cuya respuesta correcta comparte pocas palabras con el documento que la contiene. El
78,1 % es, por tanto, un **suelo**.

---

## 4. Latencia, para que C30 la herede

Medida sobre PostgreSQL con pgvector, con los 161 fragmentos indexados, en caliente —pool, plan
y caché ya calientes— sobre cinco preguntas repetidas veinte veces:

| Configuración | media | p50 | p95 | máx |
|---|---:|---:|---:|---:|
| Híbrido | 60,9 ms | **60,7 ms** | 67,0 ms | 70,8 ms |
| Vectorial solo | 56,7 ms | 57,7 ms | 62,9 ms | 63,7 ms |

**La rama léxica cuesta unos 3 ms**, sobre un corpus de 161 fragmentos y dos ramas contra una
tabla diminuta.

Dos advertencias sobre cómo leer estas cifras:

- **Excluyen el embebido de la pregunta**, que en la medición está falseado. En caliente ese
  coste lo comparte con la rama de productos: mismo modelo, mismo cliente singleton y misma
  caché de proceso (D0), así que una consulta de conocimiento que sigue a una de catálogo lo
  encuentra en caché.
- Están tomadas contra un contenedor Docker en un host Windows, cuya sobrecarga de red no es la
  de un contenedor Linux contra RDS. **Sirven de orden de magnitud**, y el orden de magnitud es
  lo que importa: la consulta solo se dispara cuando el agente la pide, y el presupuesto de
  recuperación de C16 (2.500 ms) no se toca.

---

## 5. Re-medición contra `ai.product_document` — el §9.1 de la exploración, cerrado

El informe de exploración midió sobre un **proxy de texto** —emparejar las formas de superficie
del vocabulario contra `name + description`— y declaró tres sesgos conocidos. Con la base
levantada (1.168 documentos activos), estas son las cifras reales de los atributos que C09
extrajo:

### 5.1. Materiales

| Canónico | Proxy | Medido | Veredicto |
|---|---:|---:|---|
| `plata` | 630 | **634** | Confirmado |
| `oro` | 418 | **343** | **El sesgo era real**: el proxy absorbía los bañados, aunque menos de lo temido |
| `latón` | 77 | **78** | Confirmado |
| `hilo` | 63 | **37** | **Sesgo no previsto**: el proxy casi lo dobla |
| `baño de oro` | 36 | **38** | Confirmado |
| `resina` · `acero` · `cuero` | 4 · 3 · 1 | **4 · 3 · 1** | Confirmados exactamente |
| `perla` | 8 | **0** | **Hallazgo**: el extractor la clasifica **solo** como piedra, nunca como material |

El caso de `perla` corrige la exploración por partida doble. Aquella predijo *«contada dos veces
por estar en `materials` y en `stone_type`»*; la realidad es que **no está en `materials` en
absoluto**. La ficha `material-perla` sigue siendo obligatoria —la invariante de cobertura la
deriva del vocabulario, no del surtido—, y esto refuerza por qué esa invariante se lee del
vocabulario: si se leyera de los datos, la perla se habría quedado sin ficha.

### 5.2. Multi-material

| | Proxy | Medido |
|---|---:|---:|
| Piezas con dos materiales o más | 144 (12,0 %) | **91 (7,8 %)** |
| Par más frecuente | `oro+plata` 73 | **`oro+plata` 60** |
| Segundo par | `baño de oro+oro` 31 | **`baño de oro+plata` 14** |

El proxy inflaba el fenómeno en más de un 50 %, y desordenaba los pares. **La conclusión que
sostenía `material-piezas-mixtas` no cambia**: la mezcla sigue sin ser un caso raro y el
conflicto de cuidados entre un baño y un metal desnudo sigue existiendo solo ahí.

### 5.3. Tallas — la medición que funda D16 sale intacta

| Etiqueta | Proxy | Medido |
|---|---:|---:|
| `S` · `M` · `L` · `XL` · `XS` | 122 · 103 · 87 · 83 · 10 | **idénticos** |
| `mini` · `extramini` · `mediano` | 21 · 1 · 6 | **idénticos** |
| `pequeño` | 108 | **71** — inflado por prosa, tal como se predijo |
| `grande` | 15 | **14** |
| **`XXS` y `XXL`** | **0** | **0** |

**Las cinco letras se confirman al producto.** Y con ellas los dos pilares de D16: que `XXS` y
`XXL` no tienen ni una unidad —lo que justifica marcarlas *por encargo*— y que la letra es una
escala de prenda, no de dedo. A eso se suma un dato nuevo que la refuerza: **639 de los 1.168
documentos no llevan ninguna etiqueta de talla**, más de la mitad del surtido.

Lo que sí se mueve es el reparto por tipo de pieza: `pendientes` 23,5 % (era 24,4 %), `colgante`
13,7 % (era 16,0 %) y `cadena` **0,6 %** (era 4,2 %, y ahí el proxy se equivocaba de largo).

### 5.4. Piedras — el cambio más grande, y no invalida el bloque

`stone_type` es **una columna, no un array**: un producto tiene a lo sumo una piedra, mientras
que el proxy contaba menciones en el texto. De ahí que las cifras bailen tanto.

| Piedra | Proxy | Medido | | Piedra | Proxy | Medido |
|---|---:|---:|---|---|---:|---:|
| `piedra` (genérico) | 33 | **143** | | `coral` | 102 | **23** |
| `ónix` | 57 | **124** | | `ámbar` | 75 | **68** |
| `zafiro` | 23 | **39** | | `cuarzo` | 26 | **19** |
| `rubí` · `diamante` | 13 · 16 | **24 · 28** | | `nácar` · `madreperla` | 5 · 6 | **0 · 1** |

**El coral deja de ser la piedra más frecuente.** ¿Invalida eso el bloque C, que agrupa las
fichas por régimen de cuidado poniendo la materia orgánica primero? **No.** Sumadas, coral,
ámbar, perla y madreperla siguen siendo el grupo de cuidado más numeroso después del genérico
`piedra`, y siguen siendo el régimen más frágil y el que peor tolera el consejo genérico. La
decisión de agrupar **por régimen de cuidado y no por dureza** era lo que había que validar, y
sale intacta.

Las ocho piedras del vocabulario sin una sola aparición se confirman, y se les suma `nácar`, que
no recibe sección propia sino que comparte una con la perla.

### 5.5. Colecciones — confirmadas

Los topónimos menorquines se confirman al producto: `Menorca` 70, `Es Caló Blanc` 31,
`Biniacolla` 26, `Sa Mesquida` 23, `Cala Pregonda` 20, `Cala Presili` 19, `Fiestas Menorca` 15,
`Binibeca` 14, `Cavalleria` 12. **Que las líneas llevan nombre de calas y cabos reales sigue
siendo un hecho del catálogo**, que es lo que admitió el documento J.

---

## 6. El corpus no cuenta el catálogo — la corrección que esta re-medición provocó

**Y es el hallazgo más importante del informe, porque no es una cifra sino una regla.**

Al comparar el §5 con los documentos generados apareció el problema de fondo: **cuatro secciones
habían copiado las cifras medidas al texto citable**. Decían cosas como *«`pequeño` encabeza con
108»*, *«el 44,6 % del surtido no depende de talla»* o *«144 piezas declaran dos materiales»*.

Eso ata el corpus de conocimiento al catálogo de hoy. Entra un producto de oro, se agota el
último zafiro, y la sección queda falsa — **en silencio**, que es lo grave: la cita sigue
resolviendo y sigue localizando, así que la verificación estructural la sella como comprobada.
Es exactamente el modo de fallo que este change entero existe para evitar, entrando por una
puerta que nadie estaba mirando.

**La regla 5 pasa a tener dos mitades y la ingesta comprueba las dos** (D17): ni SKU, producto o
precio; **ni recuento ni proporción del surtido**. Se rechazan `144 piezas`, `1.168 productos`,
`veintiocho colecciones`, `el 24,4 % del catálogo`. Lo que se escribe es la forma duradera del
hecho —*la mayoría*, *buena parte*, *a bastante distancia*, *la excepción*—, que además es mejor
prosa de mostrador.

**El detector lee el vecindario, no el símbolo.** Prohibir el porcentaje a secas habría borrado
mineralogía legítima: *«el ópalo lleva entre un tres y un diez por ciento de agua»* seguirá
siendo verdad dentro de veinte años. Un porcentaje solo cae si está cerca de un sustantivo que
cuenta catálogo, y los numerales en letra cuentan a partir de *once*, porque *«dos piezas de oro
que comparten cajón se rayan»* es prosa corriente y *«veintiocho colecciones»* es un censo.

La evidencia medida no desaparece: **cambia de sitio**. Decide qué documentos existen y con
cuánta profundidad, y vive en los ocho prompts de bloque y en este informe. Nunca en el texto
citable.

Seis secciones reescritas, en cinco documentos: `tallas-como-se-miden-en-nuestro-catalogo` (tres),
`regalar-sin-saber-la-talla`, `material-piezas-mixtas`, `menorca-y-el-origen-de-las-colecciones` y
`niquel-y-piel-sensible`. Y el documento piloto escrito a mano tampoco se libró: decía *«la
limpieza que resuelve el noventa por ciento de los casos»*, una precisión inventada que ahora es
*«casi todos los casos»*.

---

## 7. Lo que queda abierto

1. ~~Re-calibrar `JPV_KNOWLEDGE_DISTANCE_THRESHOLD` contra el embebedor de producción.~~
   **Cerrada el 2026-09-06: §8.** El valor pasa de 0,81 a **0,51**.
2. **Confirmar la tabla de tallas de D16 con el negocio** antes de grabar el vídeo de la demo. Si
   sus tramos son otros, cambia **una** sección de **un** documento, y su marca `establecimiento`
   ya la señala como compromiso de la casa y no como hecho. No bloquea.
3. **El fixture asigna un documento esperado por pregunta**, y eso penaliza las respuestas
   correctas que salen del documento vecino (§1). Cuando C24 lo absorba con relevancia graduada,
   el Recall@3 real subirá sin que el índice haya cambiado.
4. La composición del corpus —**sintético, con un 15,5 % de secciones ilustrativas y verificación
   de citas estructural y no semántica**— está declarada en `ai-service/README.md` y en
   `data/knowledge/README.md`. No es un riesgo mitigado: es un riesgo declarado.

---

## 8. El índice real, y el umbral recalibrado contra él (2026-09-06, posterior al archivado)

El §7.1 quedaba abierto porque `sync-knowledge` nunca se había ejecutado: poblar el índice son
161 llamadas de pago y el DoD del change exigía no hacerlas. Ejecutado a petición, **cierra esa
verificación y corrige el valor que el change dejó por defecto**.

### 8.1. La indexación

```
documents=32 chunks=161 embedded=161 skipped=0 deleted_chunks=0 deleted_documents=0
version=openai/text-embedding-3-small:1536:knowledge/v1
```

20 segundos. Las 161 filas con `embedding` no nulo y con `tsv` poblado —columna generada, así que
el código no la escribe: `agua`→`agu`, `aclarado`→`aclar`, lematizado en español—. **Segunda
corrida: `embedded=0 skipped=161`**, idempotencia confirmada contra la base real y sin una sola
llamada de pago.

### 8.2. El 0,81 no abstenía

Probando la búsqueda de punta a punta, **dos de las tres primeras preguntas fuera de dominio
devolvieron cita**. Barrido completo del fixture sobre el índice real:

| Umbral | Recall@3 | MRR | Abstención | Citas fuera de dominio |
|---|---:|---:|---:|---:|
| 0,48 | 90,6 % | 0,844 | 100 % | 0 |
| 0,50 | 90,6 % | 0,859 | 100 % | 0 |
| **0,51** | **93,8 %** | **0,891** | **100 %** | **0** |
| 0,52 | 93,8 % | 0,891 | 80 % | 1 |
| 0,65 | 93,8 % | 0,891 | 20 % | 4 |
| **0,81** *(el que el change dejó)* | 93,8 % | 0,891 | **20 %** | **4** |

**No era una imprecisión del número: era el mecanismo de abstención inoperante.** A 0,81, cuatro
de cada cinco preguntas que el corpus no cubre reciben una cita bien formada, que es justo lo que
C30 necesita no tener para no poder inventar una atribución.

### 8.3. Con el embebedor real, la regla de D8 sí se puede cumplir

Distancia al fragmento más cercano, pregunta a pregunta:

| Grupo | mínimo | mediana | máximo |
|---|---:|---:|---:|
| **Con respuesta** (32) | 0,2485 | 0,3289 | **0,5062** |
| **Fuera de dominio** (5) | **0,5145** | — | 0,9135 |

Hay un **hueco limpio** entre 0,5062 y 0,5145, así que la regla —*el valor más estricto que
mantiene en cero las fuera de dominio sin perder ninguna de las que sí tienen respuesta*— deja de
ser la conjunción imposible del §2 y se aplica **literalmente**. Da **0,51**.

Fuera de dominio, ordenadas por cercanía: reloj de cuerda 0,5145 · talla de zapato 0,5872 ·
criptomonedas 0,6342 · horario de la tienda 0,6464 · capital de Australia 0,9135. Que la más
cercana sea la de relojería es el fixture funcionando: se escribió como trampa de dominio
contiguo, y es la que fija el margen.

**El margen es estrecho —8 milésimas— y por construcción.** Un fixture más ancho lo moverá. Es
una razón para re-derivar el umbral cuando cambien el corpus, el troceado o el modelo, no para
elegir un valor más generoso: a 0,52 ya se cita lo que no se debe.

### 8.4. Dos conclusiones del change que la medición real refina

- **El 78,1 % era un suelo, y se confirma.** Con el embebedor de producción el Recall@3 sube a
  **93,8 %** (30 de 32) y el MRR a **0,891**. El §3 lo predijo y acertó.
- **La rama léxica cambia de papel.** Ya no gana recall —93,8 % en las dos configuraciones— pero
  sigue mejorando el orden: **MRR 0,891 frente a 0,854**, +0,037. Sigue justificada, por
  **reordenar** y no por recuperar. El +6,2 pp del §1 era un efecto del sustituto léxico, no una
  propiedad del sistema.
- **Latencia en caliente ~250 ms** por consulta contra la base local, incluida la llamada de
  embebido de la pregunta que el §4 excluía. La primera, en frío, 3,9 s.

### 8.5. Lo que se cambió a raíz de esto

`KNOWLEDGE_DEFAULTS["jpv_knowledge_distance_threshold"]` pasa de **0,81 a 0,51**, y con él la
fila del README. En los tests, la constante se **parte en dos**: `OFFLINE_OPTIMUM` sigue siendo
0,81 y gobierna las mediciones *offline*, que sin proveedor no pueden usar otra escala; y el
test que ataba el default a esa constante —y que pasaba en verde mientras el defecto se
enviaba— ahora **comprueba que son distintos** y explica por qué copiarlos vuelve a romperlo.

Los artefactos archivados del change no se tocan: su `design.md` ya listaba esta re-calibración
como verificación posterior, así que el registro fechado es coherente con lo que se sabía
entonces. Lo que se corrige es el valor en vigor y el informe vivo al que apunta el setting.
