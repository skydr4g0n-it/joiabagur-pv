# QA — C32b `add-sales-assistant-agent-loop`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** implementación del **2026-09-20** al **2026-09-21** · **Rama:** `c32b-add-sales-assistant-agent-loop` · **Artefactos de partida:** `2c9fd6a`, árbol limpio · **Implementación: sin commitear al cerrar esta pasada** (45 rutas en `git status`).
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.
> **Alcance:** **77/77 tareas**. DoD del ticket: **14 de 16** casillas, marcadas en la verificación independiente con su evidencia; las dos que faltan no se cumplen literalmente y están anotadas en el ticket (`backend/.env.example` cambió; 11 tests preexistentes abren sockets). La primera versión de esta línea decía «16/16» sobre un DoD que no tenía ninguna marcada.
> **Este change SÍ mueve el contrato**, por primera vez desde C30a: `openapi.json` pasa de `43f70fda…` a `7c6a038e…`, y tras la verificación independiente a `d8d48f87…`. El §7 demuestra **hoja a hoja** que el movimiento es **adición pura** — 0 retiradas, 0 cambiadas — verificado contra la línea base de C32a y no contra una regeneración intermedia.
> **Este change llama a un proveedor real**, y el §9 documenta la pasada: 204 peticiones, dos brazos, **3,82 USD** (la primera versión decía ~2,60, ver §12.1) y 3,4 h, más **una pasada abortada y cuatro sondas** cuyo coste también se declara.
> **§12 — Segunda pasada: verificación independiente.** Tres hallazgos críticos y nueve avisos sobre el change ya declarado cerrado y verde, **todos corregidos o registrados**; suite al cierre **1.576 / 0** con 0 nombres desaparecidos.
> **Lo que esta pasada encontró:** un **defecto del bucle que la suite no podía cazar** —un fallo de proveedor reportaba que el modelo había terminado—, un **escenario de calibración que no medía lo que decía medir y no lo habría dicho**, el **fallo de C31 repitiéndose** en el prompt nuevo, **dos diagnósticos míos falsos** sobre el límite de tasa, y **tres defectos de construcción en mi propio conjunto de calibración**. Todo en el §10.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | **3.11.15** · Windows · `uv` — **con `--system-certs` en todas las llamadas `uv run`**, según `CLAUDE.md` |
| Proveedor de LLM | **Llamadas reales, y es la primera vez en esta rama de changes desde C31.** Requirió exportar el almacén de Windows a un PEM y apuntar `SSL_CERT_FILE`, porque `litellm` sale por `httpx`/`certifi` y **no** por el almacén del sistema. Demostrado en el §9.1 con la prueba en las dos direcciones |
| Proveedor de *embeddings* | **Llamadas reales durante la pasada** (las tools que embeben). En la suite, cero: `FakeEmbeddingClient` conduce el cliente real sobre un lote guionizado |
| PostgreSQL | **Ninguna de las 88 pruebas nuevas toca base de datos** — verificado con `pytest -m db` sobre los cuatro ficheros nuevos → `88 deselected`. La **pasada** sí usa la base de datos de desarrollo, que hubo que **arrancar** (§9.2) |
| Bucle de eventos | `asyncio.run` por escenario vía `support/assist_world.run`. **Un escenario, un bucle.** `evals/agent_sweep.py` instala `WindowsSelectorEventLoopPolicy` en `main()`, como exige `CLAUDE.md` para todo script suelto que abra el motor asíncrono |
| .NET | **no ejecutado.** El diff toca **un** fichero de `backend/` y es `backend/.env.example`, documentación de variables. **Ningún `.cs`, ningún `.csproj`, ninguna migración de EF Core** — verificado por `grep` sobre `git status -- backend` (§8) |
| Frontend | **no ejecutado**: `git status -- frontend` vacío (§8) |
| Contrato | `ai-service/openapi.json` **regenerado dos veces** y verificado hoja a hoja en las dos (§7) |
| Migraciones | **ninguna**. `alembic heads` → **`d7c4e91b25a0`**, la misma revisión que dejó C31 |
| Congelados | `git status --porcelain` **vacío** en `frontend/`, `terraform/`, `.github/`, `ai-service/alembic/` y **`ai-service/evals/golden/`** (§8) |

---

## 1. Suites automáticas

La línea base se midió **antes de tocar una línea de código**, sobre el árbol limpio en `2c9fd6a`,
que sólo contenía los cuatro artefactos del change. `git status --porcelain` respondió vacío, que
es la condición correcta de línea base — **no hizo falta `git stash`**, y por eso no se usó, aunque
la tarea 1.1 lo proponía. La suite de `ai-service` **está verde de fábrica**, al contrario que las
de `backend/` y `frontend/` que documenta `CLAUDE.md`: aquí un rojo es del autor.

| Ejecución | Resultado |
|---|---|
| **Línea base** `ai-service` (`2c9fd6a`, árbol limpio) | **1.469 passed**, 0 failed, 244,7 s |
| Tras la fase 2 (biblioteca: puerto, transcripción, bucle, prompts) | **1.520 passed**, 0 failed, 113,9 s |
| Tras la fase 3 (contrato y ruta), **primera pasada** | **2 failed**, 1.534 passed — los dos, tests que pinchaban la *ausencia* de lo que el change entrega (§10.6) |
| Tras reconciliar los dos | **1.536 passed**, 0 failed, 83,2 s |
| Tras la fase 4 (instrumentos) | **1.554 passed**, 0 failed, 117,3 s |
| Tras la fase 5, **primera pasada** | **2 failed** — el *snapshot* del contrato, obsoleto por el motivo de parada nuevo (§10.3) |
| Tras regenerar el contrato | **1.557 passed**, 0 failed, 95,2 s |
| Tras fijar los presupuestos con las cifras medidas | **1.557 passed**, 0 failed, 85,5 s |
| **Definitiva, tras la revisión del conjunto de calibración** | **1.558 passed**, 0 failed, 80,9 s |
| `openspec validate --all --strict` en todas las puntas | **59 passed, 0 failed** |
| `openspec validate add-sales-assistant-agent-loop --strict` | `Change 'add-sales-assistant-agent-loop' is valid` |
| Comprobador de enlaces al cierre | **1.053 enlaces, 0 rotos** |
| `dotnet test` · `npm run test` | **no ejecutados**: fuera del diff. Ver §8 |

> Las dos filas en rojo se dejan escritas a propósito. Un QA que sólo enseña la pasada final
> describe un trabajo que no ocurrió, y las dos veces que la suite se puso roja fueron informativas:
> la primera porque los tests hacían su trabajo, la segunda porque el contrato se derivaba solo.

### 1.1. La comparación por nombres, que es la que vale

`CLAUDE.md` y las tareas 1.1 y 15.1 exigen comparar por **nombres de test** y no por recuento. Se
capturaron los *node id* en las dos puntas (`pytest --collect-only`), se ordenaron y se compararon
con `comm`.

```
ANTES    1469 nombres
DESPUÉS  1558 nombres
comm -23 (desaparecidos de la línea base)  →  0
comm -13 (añadidos)                        →  89
```

**Cero nombres desaparecidos.** Ningún test retirado y ninguno renombrado — incluido el caso
difícil del §10.6, que se resolvió **conservando el nombre** en vez de renombrarlo.

### 1.2. Desglose de los 89 nuevos, y la aritmética cierra

| Fichero | Nuevos |
|---|---|
| `tests/assist/test_agent.py` | **44** |
| `tests/evals/test_agent_sets.py` | **19** |
| `tests/api/test_agent_route.py` | **13** |
| `tests/assist/test_transcript.py` | **12** |
| `tests/data/test_envload.py` (uno añadido a un fichero existente) | **1** |
| **Total** | **89** |

`1.469 + 89 = 1.558`. Cierra exacto.

### 1.3. Ninguna prueba nueva abre un socket ni toca base de datos

```
pytest -m db tests/assist/test_agent.py tests/assist/test_transcript.py \
             tests/api/test_agent_route.py tests/evals/test_agent_sets.py
  →  88 deselected
```

Las 88 pruebas de los cuatro ficheros nuevos están **fuera** de la marca `db`. La 89ª vive en
`test_envload.py`, que sólo lee un fichero.

**Y una de ellas llegó a abrir un socket, lo cual es exactamente lo que este apartado existe para
detectar.** Está en el §10.4.

---

## 2. La puerta de entrada (grupo 1)

| Tarea | Comprobación | Resultado |
|---|---|---|
| 1.1 | Línea base por nombres, guardada | 1.469 *node id* en fichero, no un recuento |
| 1.2 | `openspec validate --all --strict` **antes** de tocar nada | **59 passed / 0 failed** |
| 1.3 | `sha256` de `openapi.json` guardado antes de empezar | `43f70fdadd2bd9aa90068d3e74ec2ee25c8d3b3b530f6d33907b1e73d068c684` — **idéntico al que registró C32a**, así que el contrato no se había movido entre changes |
| 1.4 | `assist/tools.py` no importado desde `jbg_ai.api` | Verificado por `grep` sobre `src/jbg_ai/api/`: **ninguna referencia**. Las únicas a `build_registry` estaban dentro de `assist/` |

---

## 3. Los 48 escenarios de las dos deltas

**44** en `sales-assistant-agent` (22 requisitos) y **4** en el `## MODIFIED` de
`sales-assistant-tools`. Cada uno se comprobó contra un test nombrado o contra una medición de la
pasada. La tabla completa escenario↔test está en el **§6 del informe de implementación**; aquí se
registra el método y las excepciones.

| Forma de comprobación | Escenarios |
|---|---|
| Test automático offline | **41** |
| Medición de la pasada con proveedor | **5** — pivote por etiqueta, granularidad, techo de llamadas observado, presupuestos con su distribución, sobrecoste |
| Test automático **más** medición | 2 |

**Las cinco que sólo una pasada puede comprobar** son, por construcción, las que el diseño declaró
como salidas del change y no como entradas: los valores de tres presupuestos (O-1), si la
granularidad de seis es correcta (O-2), si la etiqueta basta para el pivote (O-3), si el brazo
barato sostiene la selección (O-4) y si hay que compactar (O-5). Ninguna es testeable con dobles,
y decirlo es parte del QA.

### 3.1. El `## MODIFIED` reproduce el bloque **entero**, verificado programáticamente

La tarea 11.1 exige que el bloque copiado sea el entero y no un extracto. Comprobado con un guion
que parsea las dos specs:

```
live block lines: 14   delta block lines: 28
titles identical: True
SHALL line identical: True
live scenarios: 2   delta scenarios: 4
live scenarios MISSING from the delta: none
preserved scenarios byte-identical: True
```

La delta **añade** dos escenarios y dos párrafos y **no modifica ni una línea** de lo que la spec
viva ya decía.

---

## 4. Los catorce escenarios de la HU

Trazados uno a uno en el **§6 del informe**. Aquí las tres observaciones de método:

1. **El escenario 8 se comprueba en dos mitades.** La mecánica —«los sustitutos llegan al
   argumentario como grupo distinguido»— tiene test offline. La conductual —«y una pieza en últimas
   unidades **no** dispara el pivote»— es una propiedad del modelo y **sólo la pasada la mide**:
   0 % de sobre-pivote en las tres etiquetas donde sería caro.
2. **El escenario 12 no puede tener test**: dice que los números vengan de una pasada real y no de
   un juicio. Su evidencia es el artefacto y el §3 del informe.
3. **El escenario 14 tiene tres evidencias independientes**: un test de forma sobre la ruta
   determinista, un test hoja a hoja sobre el contrato, y dos tests sobre el golden set.

---

## 5. Las validaciones que `tasks.md` exige, grupo a grupo

| Grupo | Exigencia | Evidencia |
|---|---|---|
| 2 | El techo de llamadas **derivado** y nunca escrito como dígito | `MAX_AGENT_PROVIDER_CALLS = MAX_ROUTER_PROVIDER_CALLS + MAX_AGENT_ITERATIONS + MAX_PITCH_PROVIDER_CALLS` → 8, con test que reproduce la suma |
| 2.5 | `constants.py` sigue sin importar nada | Verificado con `ast`: el único `import` es `from __future__` |
| 3 | El tipo del puerto sin campo de prosa | `dataclasses.fields(AgentStep)` recorrido en test; los cinco campos enumerados |
| 3.5 | El paquete importable sin proveedor | El test preexistente `test_the_assist_package_imports_no_provider_client` recorre **todo** el paquete y cubre los tres módulos nuevos sin tocarlo |
| 4 | Los tres topes, y el delimitado por turno | 12 tests, incluida la fuga por marca de cierre que el diseño no contemplaba |
| 5 | Un test por condición de parada y uno por presupuesto | 6 motivos de parada y 5 presupuestos con test propio |
| 6 | Una sola clasificación sea cual sea la longitud | Test con transcripción de 8 turnos → `router.call_count == 1` |
| 7 | Ninguna etiqueta de disponibilidad en el *payload* | Test sobre una petición que **sí** leyó disponibilidad (el caso que importa) |
| 8.3 | `assist/v3` intacto | Test que compara sección a sección v3 contra v4 |
| 9.7 | Contrato verificado hoja a hoja | §7 |
| 9.8 | `/v1/assist/sale` idéntico | Test de conjunto de campos **más** subárbol del contrato |
| 10.4 | Ni la traza ni el log llevan argumentos | Dos tests, uno sobre la traza del cable y otro sobre la línea de log |
| 11.3 | `openspec validate --all --strict` | **59 / 0** |
| 12.4 | El golden set no se toca | Dos tests, en las dos direcciones, normalizando acentos |
| 13.3 | `SSL_CERT_FILE` con la raíz del interceptor | §9.1, con la prueba negativa |
| 13.4 | `--dry-run` y prueba de humo antes de la larga | §9.3 |
| 14.1-14.5 | Las cifras con p50 y p95 | §3 del informe |
| 15.1 | Comparación por nombres | §1.1 |

---

## 6. El invariante de solo-lectura, y el registro de evidencia

Este change **añade un objeto al grafo que el invariante de C32a inspecciona**, así que había que
demostrar que no lo debilita. Medido sobre el registro construido:

```
ledger public methods:      []
is_collaborator(ledger):    False
write_methods_of(ledger):   []

buscar_catalogo          -> ['CountingEmbeddings', 'FakeProductSearch']
buscar_sustitutos        -> ['FakeProductSearch']
listar_familia           -> ['FakeProductSearch']
consultar_conocimiento   -> ['CountingEmbeddings', 'FakeProductSearch', 'InMemoryKnowledgeIndex']
consultar_disponibilidad -> ['FakeProductSearch', 'ProjectionFreshness']
pedir_aclaracion         -> []
```

**El conjunto de colaboradores capturados es el mismo que dejó C32a.** El *ledger* no aparece en
ninguno, y no porque esté excluido: **no declara ningún método público**, así que
`_is_collaborator` no lo clasifica como colaborador en absoluto.

**Esto importa porque la alternativa fácil era peor.** Nombrarlo en `_INERT_TYPES` habría
funcionado, y apoyarse en que `record_` no está en `WRITE_METHOD_VERBS` también — pero eso segundo
sería **explotar el hueco que el propio informe de C32a declaró** (`put_`, `store_`, `record_`,
`commit`, `flush`). Un *ledger* con un `save()` **sí** sería colaborador y **fallaría** la
comprobación, que es el desenlace correcto. Pinchado en
`test_the_evidence_ledger_is_inert_to_the_read_only_check_by_construction`.

Y los **51 tests de C32a siguen verdes sin tocar ninguno**: la forma de la observación no cambió.

---

## 7. El contrato, verificado hoja a hoja y dos veces

El movimiento **no** se comprobó leyendo un diff. Los dos documentos se aplanan a `ruta → escalar`
y la diferencia se parte en tres conjuntos: **adición pura** significa que los de retiradas y
cambiadas están **vacíos**, y que toda adición cae dentro de la ruta nueva y sus modelos.

| Comprobación | Resultado |
|---|---|
| Hojas antes → después | **1.103 → 1.289** |
| **Retiradas** | **0** |
| **Cambiadas de valor o de tipo** | **0** |
| Añadidas | **186** |
| Añadidas **fuera** de `/v1/assist/agent` y sus seis modelos | **0** |
| Campos de `AssistResponse` | los **once** de C31, comparados **como conjunto** |
| `Usage` compartido | **sin `calls`** — el recuento vive en `AgentUsage` |
| `POST /v1/assist/sale` | subárbol **idéntico** |
| `git diff --stat openapi.json` | **393 inserciones, 0 supresiones** |

**Se verificó dos veces, y la segunda es la que vale.** La primera regeneración fue en la fase 3.
Después, en la fase 5, añadir `fallo_proveedor` al vocabulario cerrado **movió la descripción de
`stop_reason`** — porque esa descripción **se deriva de la constante** en vez de estar reescrita a
mano — y el *snapshot* quedó obsoleto. La segunda verificación se hizo **contra la línea base de
C32a** y no contra mi propia regeneración intermedia, que es la comparación que responde a la
pregunta real.

| | `sha256` |
|---|---|
| Antes (C32a) | `43f70fdadd2bd9aa90068d3e74ec2ee25c8d3b3b530f6d33907b1e73d068c684` |
| Tras la fase 3 | `f55719bd1b1cd9c322d0c22e2dba89834f4d6ed51205386098237de7e46eb80c` |
| Final de la implementación | `7c6a038e9f749df2f9d23c024201e9fb2c4d2383cb7ff45eaf63a461ecaccc65` |
| **Tras la verificación independiente** (§12) | **`d8d48f87b279d45d22bce80a67c4fd51caef6e679363c413f5b697c99ec2b875`** |

> **Estos digests son del checkout de Windows con `core.autocrlf=true`**, no del contenido que guarda
> git: otra máquina obtiene otros. Como *blob* de git (finales LF) la secuencia es `dd8df91d…` (C32a)
> → `befdf436…` (implementación) → **`8dd52feb…`** (verificación). Añadido por la verificación
> independiente, que no reprodujo los de arriba con `git show` hasta dar con la causa.

---

## 8. Alcance negativo, demostrado

| Zona | `git status --porcelain` | Veredicto |
|---|---|---|
| `frontend/` | vacío | intacta |
| `terraform/` | vacío | intacta |
| `.github/` | vacío | intacta |
| `ai-service/alembic/` | vacío | **sin migración**, `alembic heads` = `d7c4e91b25a0` |
| **`ai-service/evals/golden/`** | **vacío** | **el golden set no se ha tocado** |
| `backend/` | **1 fichero** | **excepción declarada**, ver abajo |

**La excepción de `backend/` es `backend/.env.example` y nada más.** Es el fichero de
documentación de variables de entorno, y se amplió con el bloque de los tres ajustes nuevos a
petición explícita, para poder separar la facturación del bucle. Verificado que **no hay ningún
`.cs`, ningún `.csproj` y ninguna migración de EF Core** en el diff:

```
git status --porcelain -- backend | grep -Ei "\.cs$|\.csproj|Migrations/"  →  ninguno
```

El ticket dice *«no se tocan `backend/`…»* en el sentido de código y contrato .NET. Un fichero de
ejemplo de variables no es ninguna de las dos cosas, pero **la desviación se declara aquí en vez de
esconderse detrás de la lectura generosa**.

---

## 9. La pasada con proveedor real

### 9.1. La precondición de TLS, comprobada en las dos direcciones

`CLAUDE.md` avisa de que `--system-certs` arregla `uv` pero **no** el proceso Python, porque
`litellm` sale por `httpx`/`certifi` y no por el almacén de Windows, donde vive la raíz del
interceptor. Se exportó el almacén a un PEM **sin filtrar por la bandera de confianza**, como el
propio aviso exige.

| Prueba | Resultado |
|---|---|
| Certificados exportados | **132**, de los cuales **sólo 25 llevan la bandera de confianza** — filtrar por ella habría tirado 107 |
| `httpx` **sin** el bundle | ❌ `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate` |
| `httpx` **con** `SSL_CERT_FILE` | ✅ HTTP 401 — llegó a la API |
| Emisor del certificado servido | **Norton Web/Mail Shield** — el interceptor está activo |

La prueba negativa es la que vale: sin ella, «configuré el PEM» es una afirmación sin contraste.

### 9.2. La base de datos hubo que arrancarla

El contenedor `jpv-pv-postgres` llevaba **cinco días parado**, y el primer intento de conexión
**se colgó** en vez de fallar rápido. Se arrancó **sólo ese contenedor** —no `docker compose up`—
sin recrear nada y con el volumen intacto. Estado verificado tras arrancar:

| | |
|---|---|
| `ai.product_document` | 1.168 filas, 1.168 activas, 1.168 con *embedding* |
| `ai.pos_projection` | 6.720 filas · **456 de MAO-AIR** |
| `ai.knowledge_chunk` | 161 |

### 9.3. La secuencia completa de ejecuciones, con su coste

| # | Qué | Peticiones | Coste | Para qué |
|---|---|---|---|---|
| 1 | `--dry-run` | 0 | 0 | Procedencia y tamaño, nada ejecutado |
| 2 | Prueba de humo | 3 | 0,0792 $ | **Cazó el fallo de C31 repitiéndose** (§10.2) |
| 3 | Diagnóstico de C01 | 1 | 0,0253 $ | Aislar la causa del argumentario retirado |
| 4 | Verificación del arreglo | 1 | 0,0345 $ | Confirmar 0 violaciones tras corregir el prompt |
| 5 | **Pasada abortada** | 67 | ~0,30 $ | Murió en la petición 6 por límite de tasa (§10.3) |
| 6 | Sonda tras separar claves | 10 | ~0,28 $ | **Refutó mi hipótesis**: volvió a romper igual |
| 7 | Sonda del regulador | 8 | ~0,22 $ | **0 rate limits** donde antes 63 |
| 8 | **Pasada completa** | **204** | **~2,60 $** | El artefacto que el change publica |
| | **Total** | **294** | **~3,54 $** | |

**El coste total es mayor que el de la pasada publicada, y se declara.** El ticket estimaba ~7 USD
para la pasada; el gasto real de *todo* el trabajo con proveedor fue **~3,54 USD**, de los cuales
**~0,90 USD se gastaron en diagnósticos y en una pasada que hubo que tirar**.

> **Corregido por la verificación independiente (§12.1).** La columna de coste mezclaba métodos:
> unas filas con la fórmula vieja del arnés, la pasada con la corrección del informe, y ninguna
> tarifaba el clasificador por lo que mide el artefacto. Coste **exacto**, cada etapa con su modelo,
> de los seis artefactos conservados: humo `f289aa53ba8b` **0,0792 $** · diagnóstico `d45b017266ea`
> **0,0273 $** · verificación `40a9bb0f7911` **0,0276 $** · sonda de claves `3ba27f2d72a8`
> **0,1593 $** · sonda del regulador `582b8517a235` **0,2113 $** · **pasada `293fe5c6e470`
> 3,8248 $**. Suman **4,33 $**, más los ~0,30 $ declarados de la pasada abortada, que no dejó
> artefacto y no se pueden verificar: **~4,6 USD** en total.

### 9.4. Los artefactos que quedan en `evals/results/`

Se conservan **los seis**, y no por descuido: son el rastro de evidencia de la tabla de arriba.

| Artefacto | Tamaño | Qué es |
|---|---|---|
| `c32b-agent-sweep-293fe5c6e470.json` | 618 K | **La pasada que el change publica** |
| `c32b-agent-sweep-582b8517a235.json` | 29 K | Sonda del regulador: 0 *rate limits* |
| `c32b-agent-sweep-3ba27f2d72a8.json` | 26 K | Sonda que **refuta** la hipótesis de las claves |
| `c32b-agent-sweep-f289aa53ba8b.json` | 10 K | Prueba de humo que cazó el `dangling_citation` |
| `c32b-agent-sweep-40a9bb0f7911.json` | 8 K | Verificación del arreglo del prompt |
| `c32b-agent-sweep-d45b017266ea.json` | 7 K | Diagnóstico de C01 |

Borrar los cinco pequeños dejaría el directorio más limpio y el rastro incompleto. Un QA que
afirma «la prueba de humo encontró X» y no conserva su artefacto pide que se le crea.

> **Dos límites de este rastro, declarados por la verificación independiente.** Los seis
> registran `agent/v1` y `assist/v4` con el mismo `git_sha…+dirty` y **sin digest del texto**,
> aunque los dos prompts se editaron entre una ejecución y otra (§10.2 y §3.6 del informe): las
> sondas midieron textos que ya no existen con la etiqueta de los que sí. Y **la pasada abortada
> no está aquí** porque el arnés sólo escribía el artefacto al final: murió sin dejar nada, y lo
> que se sabe de ella viene de una consola que no se conservó. Desde §12 el arnés registra el
> `sha256` de cada prompt y escribe cada fila según la produce.

### 9.5. Procedencia del artefacto publicado

`run_id 293fe5c6e470` · `git_sha 2c9fd6a…` **+dirty** · prompts `agent/v1`, `assist/v4`,
`router/v3` · credenciales resueltas `agent`, `router`, `assist` · 1.168 documentos de índice ·
surtido **416** · piezas resueltas por etiqueta registradas · 9.870,8 s de espera del regulador.
*(La primera versión decía «surtido 456»: 456 son las filas de proyección de MAO-AIR del §9.2; el
artefacto registra `assortment_size: 416`. Corregido en la verificación independiente.)*

**El `+dirty` es correcto y deliberado.** El árbol llevaba la implementación sin commitear, así que
la pasada **no la produjo el commit que nombra**, y `provenance.py` ya tenía la regla escrita desde
que C25 se quemó con esto.

---

## 10. Incidencias de esta pasada

### 10.1. Un escenario de pivote sin referencia no mide el pivote — **CRÍTICO, y silencioso**

**Encontrado leyendo mi propio conjunto antes de gastar dinero.** Los seis escenarios de
disponibilidad decían «el cliente quiere **esta pieza**, ¿la tenemos?». El modelo no tiene ninguna
referencia que pasar a `consultar_disponibilidad`: buscaría primero y comprobaría **lo que
encontrara**, que no es la pieza cuya etiqueta declara el `fixture`.

**La tasa de pivote por etiqueta —una de las dos preguntas que C32a dejó abiertas— se habría
calculado sobre piezas elegidas al azar, y nada lo habría indicado.** Los escenarios pasan, el
artefacto se escribe, la cifra se publica y es basura.

**Corregido** con un marcador `{pieza}` que el arnés resuelve contra la proyección, y un test que
lo **exige** donde hay `fixture` y lo **prohíbe** donde no lo hay. Las cuatro etiquetas se
verificaron además **a través de la propia tool** que el bucle llama, no sólo por el bucket.

### 10.2. El fallo de C31 repitiéndose en `assist/v4` — **CRÍTICO, cazado por la prueba de humo**

El primer escenario devolvió `pitch_chars: 0`: **cinco `dangling_citation`**, cuatro sobrevivieron
a la reparación y el argumentario se retiró entero. Es **literalmente** el defecto que v2→v3
corrigió en C31 para la tarea de catálogo, reaparecido en la sección que escribí para el agente: la
redacción de v3 funciona porque enuncia el hecho sin condicional **y dice la consecuencia**, y la
mía lo enterraba en un «si no traen ninguno…» omitiendo el «el argumentario entero se retira por
ello».

| | antes | después |
|---|---|---|
| Violaciones iniciales | **5** | **0** |
| Llamadas de generación | 2 | **1** |
| Argumentario | **ninguno** | 443 caracteres |

**Sin la prueba de humo, la pasada entera habría medido tokens, reloj y coste sobre peticiones que
no sirven prosa**, y el informe habría concluido algo falso sobre la arquitectura.

**No quedó cerrado.** Ver §10.8.

### 10.3. Un fallo de proveedor reportaba que el modelo había terminado — **CRÍTICO, ningún test lo habría cazado**

La pasada abortada topó un límite de tasa en la petición 6, y **las 46 siguientes volvieron con
`stop_reason=sin_mas_herramientas` y `partial=false`**: «el modelo dejó de pedir herramientas»
sobre peticiones cuya llamada nunca llegó. **Cuarenta y seis respuestas indistinguibles de una
completa.**

> **El «46» no es verificable** (§12.7). La pasada no dejó artefacto y la cifra se apuntó de su
> consola, que no se conservó; el §3.9 del informe y el arnés decían «64» para la misma pasada. El
> defecto sí está verificado: la sonda `3ba27f2d72a8`, posterior al arreglo, ya informa
> `fallo_proveedor` en 4 de sus 10 filas.

La suite nunca lo habría encontrado: **un doble guionizado no se cae en mitad de una tanda.** Hizo
falta que un proveedor real fallara 46 veces seguidas.

Corregido con `fallo_proveedor` en el vocabulario cerrado y `partial=true`, con dos tests. Y
**llegó hasta el contrato publicado**, porque la descripción de `stop_reason` se deriva de la
constante — lo que puso en rojo los dos tests del *snapshot* y obligó a la segunda verificación del
§7.

### 10.4. Un test mío abrió un socket, y la suite lo habría tolerado — **defecto mío**

La primera versión de `test_the_credential_chain…` construía el cliente real con una clave falsa y
servía una petición: `litellm` salió a la red, murió con `CERTIFICATE_VERIFY_FAILED` y el
clasificador agotó su *timeout* de 2 s. **El test pasaba en todo menos en la aserción del log.**

Reescrito para pilotar el resolutor directamente: **5,87 s → 1,72 s**. La lección, que contradice
una suposición cómoda de este repositorio: *«la suite no abre sockets»* **no es una propiedad que
la suite compruebe sola**.

### 10.5. Dos diagnósticos míos falsos sobre el límite de tasa — **método**

Antes de acertar propuse dos causas y las dos eran falsas:

1. *«Es la clave nueva, que tiene poca cuota.»* Falso: el bucle seguía funcionando con esa misma
   clave mientras el clasificador fallaba.
2. *«Es que el arnés usa una sola clave para las tres etapas.»* **Falso, y lo probé gastando una
   sonda**: separé las tres cadenas y volvió a romper en la petición 6, exactamente igual.

La causa real la dio la aritmética: **55.649 tokens en 33 s ≈ 100.000 tokens/min** contra un techo
de **tokens por minuto de la organización**. Se deja escrito porque la segunda hipótesis costó
dinero y porque separar las cadenas **había que hacerlo igualmente** — sin ello el arnés medía una
configuración que la ruta nunca sirve.

### 10.6. Dos tests de C32a pinchaban la ausencia de lo que C32b entrega — **previsible y previsto a medias**

`test_snapshot_covers_the_frozen_surface` enumeraba diez rutas;
`test_the_registry_publishes_no_route_and_declares_no_iteration_budget` afirmaba que no existe ruta
de agente. Los dos aparecieron **sólo en la pasada completa**, porque las suites parciales que fui
corriendo no los incluían.

El segundo es el caso que la tarea 15.1 —*«sin retirar ni renombrar ninguno»*— no anticipa: **un
test cuyo nombre afirma la ausencia de lo que el change entrega**. Se resolvió **conservando el
nombre** y leyéndolo al alcance que declara: el *registro* no publica ruta —no define `APIRouter`—
y no declara presupuesto alguno. Lo que deja de ser cierto lo pincha ahora el otro test, que es su
sitio.

### 10.7. Tres defectos de construcción en mi conjunto de calibración — **defectos míos**

Seis escenarios fallaron su expectativa; **tres eran defectos del escenario y no del bucle**:

| # | Qué estaba mal |
|---|---|
| **C05** | «¿de ese hay más tallas?» sobre un turno que **no nombraba ninguna pieza**, y prohibiendo `buscar_catalogo`, sin el cual no hay pieza cuya familia listar. **Insatisfacible** |
| **C16** | Codificaba `expects: []` exigiendo el rechazo del clasificador, mientras su propio `why` decía *«lo que no puede pasar es que se obedezca»*. **No se obedeció** |
| **C17** | El `why` dice «cualquiera de las dos» y usaba `expects`, que el fichero declara como **todas** *(la primera versión decía «que el arnés lee como todas»: el arnés no leía `expects` en absoluto y la puntuación se hizo a mano; ver §12.6)* |

Corregidos. `C19` se deja como **discrepancia declarada**: cambiar esa expectativa a la vista del
resultado sería la contaminación de la que el conjunto se protege. `C03` y `C11` son fallos reales
del brazo barato — y **C11 destapó un modo de fallo que no estaba anotado**: `gpt-4o-mini` llamó
con `sku: '637'` cuando la referencia era `SKU637`, **mutilando el identificador**.

**Y se añadió una regla para que el error de C17 no se repita**:
`test_a_scenario_that_admits_alternatives_says_so_in_the_format_and_not_in_its_prose` exige que un
escenario cuya prosa ofrezca una elección use `expects_any`.

### 10.8. Lo que queda abierto, medido y no cerrado

**`dangling_citation` al 13,1 %** contra el 2,2 % de la ruta determinista. La anatomía es de una
sola causa: **el 100 % ocurre cuando la lista de citas llega vacía**, y **la reparación no salvó
ninguno de los 18 casos en que se gastó**. El 12 % paga doble generación para nada.

> **Precisado por la verificación independiente.** El 13,1 % es la retirada **por cualquier causa**
> en `gpt-4o` (11 de 84). La atribuible a `dangling_citation` es **9,5 %** (8 de 84); de las otras
> tres, **dos son *timeouts* del argumentario**, que este QA no mencionaba, y una es otra causa. En
> `gpt-4o-mini`, 12 de 13 (**14,8 %**). La anatomía de arriba (20 casos, 20 sin citas, 18
> reparaciones, 0 salvadas) reproduce al dígito.

**Y una limitación del arnés que esto destapó:** las filas guardan la **causa** de la violación
pero no su **detalle**, que es donde viaja el identificador inventado. De esta pasada **no se puede
saber qué identificadores se inventó el modelo**. Es la misma omisión que ya obligó a añadir las
violaciones a las filas a mitad de la preparación.

---

## 11. Lo que esta pasada **no** verifica, dicho aquí

1. **La calidad del argumentario del agente.** Ningún juez, ninguna métrica de fidelidad. Es del
   change de evaluación, y este QA no lo suple.
2. **El comportamiento bajo concurrencia real.** Las 204 peticiones fueron **secuenciales**, y el
   regulador de tokens las separó a una por minuto. El tope de 4 llamadas concurrentes **por
   vuelta** sí está probado, pero contra un doble que cuenta solapamiento — **no contra el pool de
   conexiones real bajo carga**.
3. **Que 8 llamadas a herramienta basten.** De las cuatro peticiones que el techo de 6 truncó,
   nadie sabe cuántas habrían usado. El 8 es un juicio informado por la distribución.
4. **Que el modelo obedezca la regla nueva del prompt de forma estable.** Se observó que la obedece
   —de 3 de 21 peticiones en el techo a 4 de 102— pero es comportamiento, no garantía.
5. **La ruta bajo un consumidor .NET.** No existe. Su política de *timeout* y circuito queda en
   `DEFERRED_TASKS.md` con la medición que la hace necesaria.
6. **Reproducibilidad de la pasada.** Es una **medición fechada**, no una fila reproducible: llama
   a un proveedor, y por eso vive fuera del arnés que se re-ejecuta en cada evaluación.
7. **Los 15 s síncronos en un mostrador real.** Medido p95 9,0 s en una máquina de desarrollo a
   través de un interceptor TLS, con la base de datos en local. No es una medición de producción.

---

## 12. Segunda pasada: verificación independiente

> Ejecutada sobre el árbol **ya commiteado** en `0f444f9`, reproduciendo contra el repositorio y
> contra el artefacto `c32b-agent-sweep-293fe5c6e470.json` cada cifra y cada «✅» de los §1–§11 en
> vez de releerlos, con la hipótesis de trabajo de que algo se había escapado. **Sin una sola
> llamada al proveedor**: todo sale del artefacto commiteado, de dobles o de sondas locales.
>
> La distinción que importa: los §1–§11 los escribió quien implementó, y esta sección la escribió
> quien la comprobó. **Tres hallazgos críticos, nueve avisos y cuatro menores.** Dos críticos son
> defectos de código, uno es un dato sin fuente que sostenía la cifra central del informe, y
> **cuatro tests no afirmaban lo que su nombre decía**. Cada corrección se aprobó una a una antes
> de ejecutarse; ninguna retira ni renombra un test, y ninguna necesitó volver a medir.

### 12.1. El sobrecoste ×7,6 descansaba en un coste del clasificador que nadie había medido — **CRÍTICO, dato; corregido**

El informe «corrigió a mano» el coste del arnés sustituyendo el clasificador por **0,00205 USD,
atribuido a C31**. Esa cifra **no está** en el informe de C31 ni en ninguno de sus diez artefactos
(ninguno guarda tokens): aparece por primera vez en la HU de este change. El artefacto sí la mide:

```
filas rechazadas (sólo corre el clasificador, calls=1)   8   ->  3.305–3.312 tokens de prompt · 16–17 de salida
filas sin argumentario (lo que sobra del bucle)          39  ->  3.301–3.312 tokens de prompt
modelo del clasificador                                  gpt-4o (DEFAULT_ROUTER_MODEL y backend/.env)
coste por clasificación                                  0,0084 USD, no 0,00205
```

**Control**: la fórmula vieja del arnés, que tarifaba todo al precio del brazo, daba **0,0334 USD**
para `gpt-4o`: **más cerca de la verdad que la corrección**, porque tarifaba bien el clasificador y
sólo se equivocaba con el argumentario. Había **tres cifras en circulación** —el resumen embebido
en el artefacto, la del informe y la real— y la del informe era la peor.

| | Bucle | Clasificador | Argumentario | Total por petición | vs *pipeline* |
|---|---|---|---|---|---|
| `gpt-4o` | 0,01862 | 0,00841 | 0,00039 | **0,02742 USD** | **×2,98 – ×3,04** |
| `gpt-4o-mini` | 0,00125 | 0,00841 | 0,00041 | **0,01008 USD** | **×1,10 – ×1,12** |

El intervalo es el denominador: *pipeline* con el argumentario de C30b (0,00077) o con el de
consulta libre estimado desde `c31-free-query-gate-387fa94e792a` (~0,00058). La pasada costó
**3,82 USD**, no ~2,60. **Q-7 sobrevive intacta**: «el brazo barato no sabe parar» es conducta y no
precio.

**Qué se hizo.** `AgentRun` guarda el uso de cada etapa (`router_usage`, `loop_usage`,
`pitch_usage`); el arnés tarifa cada una con su modelo y registra los modelos de las tres etapas en
la procedencia; `--rescore` recalcula todo desde un artefacto escrito, derivando el clasificador de
las filas del propio artefacto cuando éstas son anteriores al desglose, y lo declara en su salida
(`c32b-agent-sweep-293fe5c6e470.rescore.json`). Informe §3.3, README, `epicas.md`, plan de changes y
`config.yaml` reescritos. `test_the_rescore_of_the_committed_pass_reproduces_the_figures_the_report_publishes`
fija las cifras. **El mensaje del commit `0f444f9` conserva ×7,6**: la rama está publicada y la
historia no se reescribe.

### 12.2. `pivot_rates` reventaba con el conjunto de calibración commiteado — **CRÍTICO, código; corregido**

```
pivot_rates([fila de C05])  ->  KeyError: 'availability'      (C05 lleva {family: con_variantes})
```

Se evaluaba **dentro** de la escritura del artefacto, así que la próxima pasada habría perdido las
204 filas al final, tras ~3,8 USD y 3,4 h. **Control**: `scenario_turns` sí resuelve C05; el fallo es
sólo del agregado. `agent_sweep.py` **no tenía ningún test**: `grep` sobre `tests/` no lo importaba.
Además sumaba los dos brazos (§12.8) y sólo leía `expects`.

**Qué se hizo.** Sólo cuentan los `fixture` de disponibilidad; resultado por brazo; debe/no debe
pivotar leído de `expects` y de `forbids` por fila; infra- y sobre-pivote aparte. El arnés **escribe
cada fila según la produce** (`.partial.jsonl`) y compone el JSON final al terminar, así que ni un
fallo al resumir ni una pasada abortada pierden lo pagado; `--rescore` lee también el parcial. Trece
tests nuevos en `tests/evals/test_agent_sweep.py`, **los primeros del arnés**.

### 12.3. El presupuesto de reloj no acotaba la petición — **CRÍTICO, código; corregido**

El reloj sólo se comprobaba **antes** de cada vuelta. La vuelta en curso gastaba su propio *timeout*
pasado el límite y el argumentario corría después. Medido con dobles:

```
deadline 0,2 s · vuelta 0,15 s · argumentario 0,00 s   ->  0,355 s  (1,77x)   stop=presupuesto_reloj
deadline 0,2 s · vuelta 0,15 s · argumentario 0,15 s   ->  0,479 s  (2,40x)   el argumentario corrió tras el corte
peor caso por construcción                              ->  15 + 8 + 2 x 4 = 31 s, más las herramientas
```

Contradecía el docstring de la constante («the whole request, argument included»), el §3.1 del
informe («tensa el peor caso de 20 s a 15 s») y D-7.

**Qué se hizo.** El bucle corre contra el *deadline* **menos la reserva del argumentario**
(`AGENT_PITCH_RESERVE_SECONDS`, derivada de sus dos llamadas a su *timeout*; la ruta y el arnés la
recalculan con el *timeout* configurado), y cada `decide` se acota con lo que queda: si vence, el
motivo es `presupuesto_reloj` y la traza lo marca con `cut_by_clock`, no como fallo de proveedor.
**Sale gratis, según el artefacto**: en `gpt-4o` el bucle tarda **p95 4,7 s · máx 5,8 s** y
clasificador + argumentario **p95 5,2 s · máx 8,0 s**; con 7 s para el bucle se habrían cortado **0
de 102** peticiones de `gpt-4o` y 3 de 102 del brazo barato. **Control del arreglo**: con *deadline*
de 1 s y 0,4 s de reserva, la segunda vuelta se corta a 0,6 s y la petición acaba por debajo de 1 s;
el bucle viejo habría servido a ~1,36 s. Las herramientas de la vuelta en curso **no se cancelan**
—cancelar una sesión en un pool de 5 sin *overflow* invalida la conexión— y se declara. Escenario
nuevo en la delta; `test_the_wall_clock_budget_stops_the_loop` declara reserva cero para seguir
midiendo lo que medía.

### 12.4. Cuatro tests que no afirmaban lo que decían — **defectos de test; corregidos**

El patrón que el §11 del QA de C32a dejó escrito, cuatro veces:

| Test | Qué afirmaba de verdad | Ahora |
|---|---|---|
| `test_the_published_contract_moved_by_addition_only` | Sólo `committed == generated`: el *snapshot* al día. **Nunca comparaba contra C32a**; habría pasado sobre un campo retirado tras regenerar | Particiona retiradas / cambiadas / añadidas contra `tests/api/fixtures/openapi-c32a-baseline.json` (el *blob* `dd8df91d…`) |
| `test_the_evidence_ledger_is_inert_to_the_read_only_check_by_construction` | Sólo la dirección negativa, que se cumpliría igual si el recorrido nunca llegase al *ledger*. El QA decía «pinchado» el caso `save()` | Un *ledger* con `save()` pasado por `build_registry` **debe ser rechazado**; el hueco de C32a (`record()`) queda fijado aparte |
| `test_an_injection_in_an_earlier_turn_does_not_change_the_system_message` | `agent_system_message() == agent_system_message()`: una función sin argumentos comparada consigo misma, y la inyección en el **último** turno | Compara los mensajes de sistema que recibieron las llamadas reales del bucle y del argumentario, con la inyección en el turno 3 de 5 |
| `test_no_availability_label_reaches_the_generation_payload`, cláusula del argumento | `label not in outcome.pitch` sobre un argumentario guionizado que no puede llevarla | Aserción retirada; el argumento **se mide** (§12.5) |

**Medición de la afirmación que el segundo test no sostenía**, por introspección real y con control:

```
recorrido desde cada tool      -> alcanza el ledger a profundidad 1 en 5 tools (no en pedir_aclaracion)
colaboradores capturados       -> los mismos que dejó C32a; el ledger en ninguno
SavingLedger (save)            -> rechazado: "tool 'buscar_catalogo' captures SavingLedger ... ['save']"
RecordingLedger (record)       -> construido: el hueco declarado de C32a
```

**Cada test nuevo o reescrito se comprobó contra su mutación**: deshacer el arreglo lo pone en rojo
(anclas ignoradas, tope sin prioridad, `decide` sin acotar, sin reserva, rama global eliminada,
`KeyError` restaurado, brazos sumados, todo tarifado al modelo del bucle). Los ocho casos, rojos.

### 12.5. La cláusula «el argumento no contiene etiquetas» no la hace cumplir nada — **criterio; medido en vez de asegurado**

```
verify("Esta pieza está disponible en tu tienda...")        ->  sin violación
verify("Quedan últimas unidades ... sin_existencias ...")    ->  sin violación
verify("Quedan 3 unidades de esta pieza.")  (control)       ->  stock_adjacent_figure
```

Hacerla cumplir en `verify()` movería `/v1/assist/sale`; una comprobación sólo en esta ruta
retiraría argumentos legítimos («disponible en talla M» sale del roster) con una causa nueva en el
vocabulario de otra capability. **Qué se hizo**: la spec dice ahora lo que se garantiza —ninguna
etiqueta llega a la generación— y que la salida **se mide**; el arnés cuenta los términos de
disponibilidad de cada argumento servido (`pitch_availability_terms`, un número, nunca el texto). La
pasada `293fe5c6e470` es anterior al recuento y no lo tiene.

### 12.6. El arnés no puntuaba la calibración; C19 sólo estaba declarado en prosa — **código y redacción; corregidos**

Nada en `src/` leía `expects`, `expects_any` ni `forbids` salvo `pivot_rates`, que sólo miraba
`expects`: **la tabla OK/MISS del informe se puntuó a mano**, y «`expects`, que el arnés lee como
todas» (YAML de C17 y §10.7) era falso. Reproducida con un evaluador propio antes de corregir nada:
**16/4 y 14/6** tal como se corrió, **18/1 y 16/3** con el fichero actual. **Qué se hizo**:
`expectation_verdict` con la semántica declarada; campo `declared_discrepancy` en C19, que se
puntúa aparte (hoy: `gpt-4o` 18 OK / 0 MISS / 1 declarada; `gpt-4o-mini` 16 / 2 / 1); un escenario
cuyo texto cambió después de la pasada se lista como no comparable (C05) en vez de puntuarse.

### 12.7. La procedencia no identifica el texto medido, y tres cifras no son verificables — **criterio y redacción; corregido lo corregible**

Las seis ejecuciones registran `agent/v1` y `assist/v4` con el mismo `git_sha…+dirty` y **sin
digest del texto**, aunque los dos prompts se editaron entre ellas. De ahí:

| Cifra | Dónde | Qué se sabe |
|---|---|---|
| «3 de 21 → 0 de 33» en el techo | informe §3.6 | Ningún artefacto conservado suma 21 ni 33; la última sonda antes de la pasada (`582b8517a235`) tiene **6 de 8** en el techo |
| «46» respuestas sin herramientas | §10.3, informe §2.6, `constants.py`, test | La pasada abortada **no dejó artefacto**; el informe §3.9 y el arnés decían «64». Ninguna de las dos es verificable |

**Qué se hizo.** La procedencia registra el `sha256` de cada prompt (hoy: `agent/v1` `1505d99a…`,
`assist/v4` `cbf34f02…`, `router/v3` `7e892d01…`) y los modelos de las tres etapas; las cifras se
marcan como no verificables donde aparecen. **No se elige entre 46 y 64** sin el registro de
consola. El preámbulo de `agent/v1` citaba un test inexistente y se corrigió **fuera de `## Sistema`**:
el mensaje de sistema es byte a byte el mismo (`49681c5c…` antes y después), aunque el digest del
fichero cambia.

### 12.8. La tabla de pivote mezclaba los dos brazos — **redacción; corregido**

«6 escenarios, 5 pivotó, 83 %» eran 3 escenarios × 2 brazos, y el único infra-pivote era del brazo
**descartado** (C11, el SKU mutilado). Por brazo: `gpt-4o` **3 de 3** en `sin_existencias` y 0 de 1
en cada una de las otras tres; `gpt-4o-mini` 2 de 3. La conclusión pasa de «la etiqueta basta» a
«es compatible con que baste, sobre un escenario por etiqueta».

### 12.9. «Sin red y sin BD» es cierto de los tests del change, no de la suite — **redacción; lo preexistente, registrado**

Guardia de sockets y de `psycopg` (validado con controles: caza una resolución externa y un
`connect` a `localhost:5432` sin romper el bucle `asyncio`), con PostgreSQL **arrancado**:

```
89 tests nuevos de la implementación       ->  0 eventos
suite entera bajo el guardia                ->  1.486 passed · 72 skipped · 0 failed
  72 tests db                               ->  PostgreSQL real vía testcontainers (103 PASSED en esos ficheros sin guardia)
  11 tests de test_assist_generation.py     ->  12 resoluciones de api.openai.com, 1 de raw.githubusercontent.com
```

Los once son de C30b/C31: el mismo defecto que el §10.4 corrigió en su propio test. **Fuera de
alcance**, registrados en `DEFERRED_TASKS.md` con la forma de arreglarlos; informe y README dicen
ahora exactamente de qué tests es cierta la afirmación.

### 12.10. `usage` suma tres modelos bajo un solo `model` — **criterio; resuelto en proceso, declarado en el contrato**

Con dobles de tres modelos distintos: `usage.model` = el del argumentario, mientras 6.000 de los 8.200
tokens de prompt eran del bucle. Quien tarifase `usage × model` repetiría en el cable el error de
§12.1. **Qué se hizo**: el desglose en proceso (§12.1); `AgentUsage.model` redeclarado con una
descripción que dice que no es clave de precio —**el contrato se mueve sólo en dos descripciones de
un esquema nuevo de C32b**—; el comentario falso de `TokenUsage.__add__` («no puede ocurrir aquí»)
corregido. El desglose en el cable queda en `DEFERRED_TASKS.md` hasta que la ruta tenga consumidor.

### 12.11. La spec decía «sin credencial no se llama al proveedor» — **redacción de la spec; corregida**

El código clasifica antes de mirar si hay cliente del agente, como hace `/sale` sin credencial de
generación y como pide el ticket; el propio test afirmaba `router.call_count == 1`. El escenario dice
ahora que no corre el bucle ni se llama al proveedor **del agente**, y que el guardarraíl sigue
clasificando si tiene su credencial.

### 12.12. Tras un pivote, la pieza abandonada encabezaba el argumento — **criterio de diseño; corregido**

```
pivotes de gpt-4o tras una búsqueda de catálogo           7 de 10
  en los que el ancla estaba entre los candidatos           7 de 7   (su SKU sólo pudo salir de la búsqueda)
  en los que el payload tocó el tope de 8 piezas            5 de 7   (5 candidatos + 3 sustitutos)
```

`assist/v4` manda decir primero «lo que encaja», y la pieza que no servía era una coincidencia de
catálogo: contradecía la regla de `agent/v1` de no encabezar con una pieza que no se puede vender.
**Qué se hizo**: `_pieces` excluye de las coincidencias las piezas sobre las que el bucle pidió
sustitutos —por su decisión, no por la etiqueta, que sigue fuera del *payload*— y, cuando el tope
aprieta, descarta coincidencias antes que sustitutos **sin cambiar el orden** del *payload*. **Se
declara**: la pasada midió la proyección anterior; los tokens no se mueven (el tope es el mismo), la
calidad del argumento es del change de evaluación.

### 12.13. Menores — corregidos

| Qué | Dónde | Corrección |
|---|---|---|
| `pitch_prompt_text` y `agent_prompt_text` sin llamador; el primero ni se usaba | `run_agent` | Retirados: un texto sin su versión es como `enrichment/` selló una respuesta con un prompt que nunca corrió |
| Tope global de contexto inalcanzable con los valores por defecto, y rama sin test | `constants.py` | Documentado por qué es así (Q-4) y cuándo actúa; test que ejecuta la rama |
| El stub emitía dos avisos que la ruta nunca emite | `stubs/responses.py` | Avisos vacíos; grupos y argumentario se mantienen, como en el stub de `/sale` |
| «1.557 / 88», «surtido 456», «16/16 del DoD», `context_chars` «as sent», digests sólo del checkout CRLF, coste del §9.3 por métodos mezclados | informe §1, §9.5, cabecera, `IterationTrace`, §7, §9.3 | Corregidos en el sitio, con la cifra correcta y su fuente |

### 12.14. Al sincronizar: `sales-assistant-tools` seguía diciendo que el bucle «is a later change» — **redacción de la spec viva; corregida**

Encontrado al sincronizar las deltas en el archivado, no en la verificación. El requisito
«The registry is not wired to any route and the frozen contract does not move» y el `## Purpose` de
la spec viva, escritos en C32a, llamaban al bucle agéntico «a later change» y afirmaban que el
*snapshot* no se movía. La línea normativa seguía siendo cierta —esta capability no añade rutas—,
pero la prosa describía un estado anterior a C32b. **Qué se hizo**: un segundo `## MODIFIED` en la
delta de `sales-assistant-tools` con la línea SHALL idéntica y el párrafo explicativo nombrando
`POST /v1/assist/agent` y la capability `sales-assistant-agent`, sincronizado bloque a bloque; y la
frase equivalente del `## Purpose`, que no es materia de delta, corregida en la spec viva durante
la misma sincronización. Así, la delta pasa a tener **dos** requisitos modificados, no uno como dice
el §3; `sales-assistant-tools` sigue con 13 requisitos y `openspec validate --all --strict` da
**60 / 0** con la capability nueva.

### Lo que la segunda pasada **sí** reprodujo

Todo esto se midió, no se leyó, y coincidió con lo escrito:

- **Suite**: 1.558 passed / 0 failed en `0f444f9`, con el conjunto de nombres que pasa idéntico al
  recolectado.
- **Nombres**: línea base medida en un `git worktree` de `2c9fd6a` → **1.469**; `comm` → **0
  desaparecidos, 89 añadidos** (44 · 19 · 13 · 12 · 1).
- **Sin red ni BD en las pruebas nuevas**: 0 eventos bajo el guardia, con el contenedor arrancado.
- **Contrato**: `43f70fda…` → `7c6a038e…` en el checkout; hoja a hoja contra C32a **1.103 → 1.289, 0
  retiradas, 0 cambiadas, 186 añadidas**, todas en la ruta y sus seis modelos; `/sale` idéntico;
  `AssistResponse` con sus 11 campos; `Usage` sin `calls`.
- **Gate de specs** 59 / 0 y el change válido; enlaces **1.054 / 0**.
- **Alcance negativo**: `evals/golden/`, `frontend/`, `terraform/`, `.github/` y migraciones sin
  diff; en `backend/` sólo `.env.example`; `assist/v1-v3`, `router/`, `routing.py` y `router_llm.py`
  intactos; `constants.py` sólo importa `__future__`.
- **Los 29 tests citados en la trazabilidad de la HU existen.**
- **La pasada, al dígito**: tokens p50/p95/máx 12.870 / 18.781 / 23.210 (y 19.129 / 24.866 en el
  barato); contexto 1.847 / 4.709 / 17.053; reloj 5,3 / 9,0 / 11,9 s (10,3 / 14,3 s en el barato);
  curva 1.974 / 2.620 / 2.712 / 3.152 / 3.470; herramientas p50 2 · p95 5 · máx 6 con **4 de 102** en
  el techo; llamadas al proveedor p50 5 · máx 8 · **0 por encima de 8**; *embeddings* p50 1 · máx 6;
  Q-7 entera (1 vs 50 `presupuesto_tools`, 0 vs 4 de iteraciones, 1/82 vs 54/82, 5 vs 168
  `presupuesto_agotado`, 87 vs 233 y 7 vs 110 llamadas, 0 nombres inventados, las seis herramientas
  usadas); `dangling_citation` 84/11 y 81/13, 20 en primer intento, 20 sin citas, 18 reparaciones, 0
  salvadas; el 2/89 de C31 (`c31-free-query-gate-387fa94e792a`); el ×0,8 de la fórmula vieja en el
  brazo barato.
- **La invarianza del *ledger*** (§6): cierta, medida con controles en las dos direcciones.

**No reproducido**: el «46/64», el «3 de 21 → 0 de 33», la prueba TLS del §9.1 (necesita proveedor)
y los recuentos de base de datos del §9.2 (no se consultó la base de datos).

### El gate al cierre de la segunda pasada

| Comprobación | Resultado |
|---|---|
| Suite `ai-service` | **1.576 passed / 0 failed** (132 s) |
| Por nombres contra la línea base (1.469) | **0 desaparecidos** |
| Por nombres contra el cierre de la implementación (1.558) | **0 desaparecidos · 18 añadidos** (5 en `test_agent.py`, 13 en `test_agent_sweep.py`) · ninguno retirado ni renombrado |
| Ficheros tocados bajo el guardia de red y BD | **108 passed · 0 eventos** |
| `openspec validate --all --strict` | **59 passed / 0 failed** |
| `openapi.json`, checkout CRLF | `7c6a038e…` → **`d8d48f87b279d45d22bce80a67c4fd51caef6e679363c413f5b697c99ec2b875`** |
| `openapi.json`, *blob* LF | `befdf436…` → **`8dd52feb66d90e1e99e81653199eedb454a48d4a7a74cf933aff55199338885e`** |
| Hoja a hoja contra C32a (`43f70fda…` / `dd8df91d…`) | **1.103 → 1.289 · 0 retiradas · 0 cambiadas · 186 añadidas**, todas en la ruta y sus seis modelos; `/sale` y `Usage` idénticos. Ahora lo comprueba un test |
| Artefacto de la pasada | **sin tocar**: `sha256` LF `331057da…` igual al *blob* de git |
| Comprobador de enlaces | **1.056 enlaces · 0 rotos** |

### Lo que esta pasada no cambió, dicho aquí

1. **El mensaje del commit `0f444f9`** sigue diciendo ×7,6, «46 respuestas» y «`dangling_citation`
   retira el 13,1 %». La rama está publicada y la historia no se reescribe; este §12 es la fe de
   erratas.
2. **El resumen embebido en el artefacto** conserva la fórmula vieja: el artefacto es una medición
   fechada. Las cifras válidas son las de su `.rescore.json`, que se generó sobre el árbol de
   trabajo antes de commitear (`git_sha 0f444f9…+dirty`); regenerarlo después reproduce las mismas
   cifras y sólo cambia la procedencia.
3. **La pasada midió el código anterior** en dos puntos que esta verificación cambió: el reloj (sin
   reserva, *deadline* de 20 s) y la proyección tras un pivote. Ninguno mueve lo que la pasada
   publica; lo segundo cambia lo que el argumentario recibe, y eso lo medirá el change de evaluación.
