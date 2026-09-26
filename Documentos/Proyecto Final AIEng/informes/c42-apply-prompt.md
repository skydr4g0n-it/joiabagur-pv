# Prompt para implementar C42 en una sesión nueva

Copia desde la línea siguiente hasta el final del documento y pégalo en un chat nuevo de Claude Code,
abierto en la raíz del repositorio y en la rama `c42-add-frontend-agent-panel`.

---

/opsx:apply add-frontend-agent-panel

Implementa C42 en la rama `c42-add-frontend-agent-panel`, que ya existe, sale de `ai-eng` y está
publicada. El árbol está limpio y los artefactos de partida están en el commit **`946eb42`**. Los
cuatro commits de la rama sobre `ai-eng` son la apertura del change, la exploración y los artefactos:
**no hay una línea de código de C42 escrita todavía.**

**Qué hace este change, en una frase:** el agente de venta —`POST /v1/assist/agent`, entregado y
medido desde C32b y al que **nadie llama**— gana una pantalla: ruta propia `/sales/new/agent`, cuarta
tarjeta en el hub de venta, y un hilo de conversación donde **cada turno es dueño de su bloque de
respuesta**, con los grupos rotulados por procedencia, la traza de llamadas visible y los diez motivos
de parada en castellano. Por el camino se arregla que su argumentario se retire por construcción.

**Sin ruta nueva bajo `/v1`, sin migración de EF Core ni de Alembic, sin séptima herramienta, y sin
tocar `assist/v5` ni los dos componentes de frontend que se reutilizan.**

## Lee esto antes de escribir una línea, y en este orden

1. **`openspec/changes/add-frontend-agent-panel/tasks.md`** — 12 grupos, **75 tareas**. Es el plan de
   ejecución y su orden **no es arbitrario** (ver *El orden no se reordena*, abajo).
2. **`openspec/changes/add-frontend-agent-panel/specs/**/spec.md`** — **7 ficheros, 25 requisitos, 85
   escenarios**. Es el contrato: 2 capabilities nuevas (`ai-agent-assist`, `sales-agent-panel`) y 5
   modificadas (`sales-assistant-agent`, `assist-generation`, `ai-gateway-client`,
   `ai-free-query-search`, `ai-service-auth`).
3. **`openspec/changes/add-frontend-agent-panel/design.md`** — **10 decisiones con sus alternativas ya
   descartadas y el motivo escrito**. No se reabren. Tu trabajo es comprobar que el código hace lo que
   la decisión dice, no volver a elegir.
4. **`openspec/changes/add-frontend-agent-panel/ticket.md`** — 657 líneas. Su **§2 es la tabla del
   estado actual del código verificada fichero a fichero**: úsala en vez de re-explorar, y si algo no
   coincide, anótalo (ver *Si algo del ticket sale falso*).
5. **`Documentos/Historias/AI-Eng/HU-AIENG-042.md`** — 16 escenarios de aceptación en
   Dado/Cuando/Entonces, y la tabla de las **16 decisiones cerradas** (D1–D16).
6. **`Documentos/Proyecto Final AIEng/informes/c42-exploration-decisions-v2.md`** — **el informe que
   gobierna**. Todas las cifras de abajo salen de él, medidas sobre artefactos ya escritos y **sin
   llamar al proveedor**. El v1 sigue en el repositorio y su §11 está **corregido** por el v2: no lo
   uses como fuente sin leer el §0 del v2.
7. **`openspec/project.md` y `CLAUDE.md`** — convenciones y trampas del repositorio. **`CLAUDE.md` no
   es opcional**: cinco de las trampas que te van a morder están escritas ahí.

## El orden no se reordena, y el motivo es que ya se intentó al revés

El v1 de la exploración pedía **medir antes de escribir la primera tarea**. Eso **no era ejecutable**:
el arnés del agente no cuenta marcadores y no registra la antigüedad de la proyección. De ahí nace el
grupo 2, y va **antes que cualquier tarea funcional**.

```
 1. Puerta de entrada       ← líneas base de las TRES suites, por NOMBRES
 2. Tramo 0 · instrumentos  ← sin esto no hay cifra ni auditoría
 3. Tramo 1 · ai-service    ← origin PRIMERO, luego v6, luego la ruta
 4. Tramo 2 · backend       ← EL QUE GOBIERNA: hoy no hay ningún camino
 5-8. Tramo 3 · frontend    ← ordenado por FRECUENCIA MEDIDA
 9. Tramo 4 · el coste      ← el único que no arregla nada que hoy engañe
 10. Medición · UNA pasada
 11. Specs, validación y las dos anotaciones
 12. Cierre · incluida la comprobación MANUAL
```

Dos cosas del orden que parecen raras y son deliberadas:

- **`origin` (3.1–3.3) va antes que el prompt (3.4–3.7).** `buscar_sustitutos` se invocó **125 veces**
  en la pasada medida: rotular la procedencia es lo que más veces impide que la pantalla mienta.
- **El tramo 1 NO es «sin esto no hay pantalla».** El que gobierna es el **tramo 2**:
  `IAiGatewayClient` tiene siete métodos y ninguno es el del agente, que es el **100 %**. El arreglo
  del prompt es real y **su urgencia es pequeña** — ver abajo.

## Las cifras que ya están medidas: no las re-derives ni las contradigas sin medir

Todas de `ai-service/evals/results/c32b-agent-sweep-293fe5c6e470.json` (204 peticiones, proveedor
real) y de los dos artefactos de marcadores de C40. **Gobiernan el diseño del frontend.**

| | **`gpt-4o`** · el arm que se sirve | `gpt-4o-mini` |
|---|---|---|
| Latencia p50 / p95 / **máx** | 5.311 / 9.021 / **11.917 ms** | 6.216 / 10.348 / 14.276 ms |
| `partial: true` | **2 de 102 · 2,0 %** | 60 de 102 · **58,8 %** |
| `presupuesto_tools` | **2** | **56** |
| Respuestas **sin ninguna pieza** | **19,6 %** | 19,6 % |
| Argumentario retirado | **13,1 %** | 16,0 % |

- **Una de cada cinco respuestas no trae ninguna pieza**, y de las 20 por arm, **14 son repregunta o
  rechazo**; sólo **6 de 102 (5,9 %)** son «busqué y no encontré nada». **Por eso el bloque sin filas
  es lo primero del frontend** (8.1–8.3) y por eso **no es «sin resultados»**.
- **Citas vacías en el 92,2 %** y **avisos vacíos en el 96,1 %**. Son la excepción, no el caso normal.
- **La cinta de respuesta incompleta sirve al 2,0 %** en el arm servido, y va **la última** (8.9).
- Argumentario: **p50 386, p95 514, máx 605** caracteres. De aquí sale que la conversación son **6
  intercambios y no 12**.
- `dangling_citation`: **85 en el primer intento, 72 supervivientes** — la reparación arregla 13 de
  85. **Ésta es la causa que de verdad retira el argumentario**, no el marcador.
- Herramientas: `consultar_disponibilidad` 376, `buscar_catalogo` 166, **`buscar_sustitutos` 125**,
  `consultar_conocimiento` 113, `listar_familia` 94, `pedir_aclaracion` 24.
- **~13.000 tokens por petición contra 25.000 TPM = una petición por minuto.** Es lo que sostiene la
  decisión del circuito y lo que hace que una pasada de 204 peticiones cueste **2 h 44 min**.

### La cifra que hay que leer con cuidado

**El arreglo del prompt no va a mover casi nada, y eso está medido.** La frase que ordena escribir
marcadores es **idéntica palabra por palabra** en `ai-service/prompts/assist/v3.md:47` y
`v4.md:59`, y la tarea del agente (`v4.md:132-166`) **no menciona precio ni stock**: hereda esa regla
y nada más. Así que C40 ya midió este caso exacto sobre 90 consultas libres con payload sin anclar:
**3 de 90 generaciones con marcador y 0 retiradas tras la reparación**. Y la reparación **no es una
por comprobación**: `assist/pitch.py:24` dice *«One repair, not one per check»* y recibe la lista
entera, así que un marcador **se suma a la lista** y no gasta un turno que otra causa fuera a usar.

**Consecuencia práctica:** si al ejecutar 10.4 la cifra de marcadores sale ~0, **eso es lo esperado y
no un fallo del instrumento**. Compruébalo con un caso sintético que sí lleve marcador antes de
concluir que el contador no cuenta.

## Seis trampas de este change en concreto

Además de las de `CLAUDE.md`, que siguen aplicando enteras.

1. **El arnés y el camino de servicio leen cosas distintas, y el arnés no lo nota.**
   `retrieval/search.py:490-499` resuelve el surtido con un `SELECT` crudo declarado *«Read by the
   evaluation only»* (`retrieval/ports.py:204`) y **sin comprobación de frescura**, mientras el camino
   de servicio consulta `projection_synced_at()` y, pasado el techo, **no aplica el prefiltro**
   (`retrieval/orchestrator.py:305`, `degraded=unscoped`). **Una pasada dura más que el techo de 3.600
   s**, así que sin el registro por fila del grupo 2 no se distingue una pasada fresca de una
   degradada. Ya pasó: parte de las cifras de recuperación de C32b describen una recuperación sin
   ámbito, y **no se pueden limpiar a posteriori**.
2. **El drenaje vive en el ciclo de vida de FastAPI y el arnés es un CLI que no drena nada.**
   `api/lifespan.py:50` arranca el planificador; `evals/agent_sweep.py` tiene **cero** apariciones de
   `scheduler` y de `drain`. Así que la pasada **exige el contenedor `jbg-ai` levantado** con
   `JPV_POS_SYNC_SCHEDULER_ENABLED=true`, comprobado en la sección `projection` de `GET /health`
   **antes** de arrancar (tarea 2.6, y de nuevo 10.1). Tener C41 archivado **no basta**.
3. **La etiqueta de disponibilidad NO está guardada por la rancidez, y el prefiltro SÍ.**
   `assist/tools.py:873` lee `availability_bucket` directamente y la antigüedad viaja al modelo
   (`:880`), con la regla *«degrade, never remove»* (`:891`). Por eso el pivote 3 de 3 sobrevive a la
   contaminación y **las piezas por respuesta no**. No mezcles las dos cosas al interpretar nada.
4. **El tope de caracteres del transcript suma TODOS los turnos**, incluidos los del asistente:
   `api/schemas/assist.py`, `_within_the_total_cap`. Con el argumentario reenviado, **el tope de 12
   turnos muerde a los 6 intercambios**. Un contador que cuente sólo lo que el operario teclea llega a
   la mitad de su cuenta con el 422 ya disparado — que es exactamente lo que el contador existe para
   evitar. Es la tarea **7.3**, y su test es `should count the assistant turns towards the transcript
   caps`.
5. **El cortafuegos de Polly recibe un resultado de transporte y NO ve el cuerpo.** Un 200 con
   `stop_reason=fallo_proveedor` es un éxito en esa capa. La decisión está cerrada: **no se cuenta**,
   se instrumenta como métrica, y se escribe el motivo en el comentario. El *pipeline* de `ai-assist`
   ya lo declara —*«a 200 the service degraded internally… is not a failure»*
   (`AiGatewayServiceCollectionExtensions.cs:190`)—. **No construyas un handler que lea el cuerpo ni un
   circuito de dominio**: las dos alternativas están descartadas en el design con su motivo.
6. **El presupuesto del cliente `ai-agent` NO se ajusta al máximo observado.** El máximo medido es
   **11.917 ms** y el techo de reloj del servicio son 15 s; el presupuesto va **por encima de ese
   techo más el margen de red**. Apretarlo tiene un modo de fallo caro: cortar una petición que Python
   **ya pagó entera**. `AssistTimeoutMs` **no se toca**: el agente lleva opción propia.

## Lo que no se toca, y es alcance

Comprobable con `git status` al cerrar:

- **`ai-service/prompts/assist/v5.md`** — sin diff. Tiene cifras publicadas y **C38 va a medirlo**.
- **`PROMPT_VERSION`** — sin cambio. Sólo se mueve `AGENT_PITCH_PROMPT_VERSION`.
- **`ai-service/prompts/assist/v4.md`** — sin diff. Las cifras de C32b se midieron contra él.
- **`frontend/src/components/sales/assisted-search-result-row.tsx`** — sin diff. Se consume entero.
- **`frontend/src/components/sales/sales-assist-card/pitch-block.tsx`** — sin diff. Se consume tal cual.
- **`AssistGroup`** del esquema compartido — sin ensanchar. `origin` va en la **subclase** del agente,
  por el precedente de `AgentUsage`.
- **Las seis herramientas** y sus dos ausencias deliberadas.
- **Ninguna migración**, ni EF Core ni Alembic.
- **`substitutes-block.tsx`** no es reutilizable y no se intenta: se alimenta de señales que llegan por
  otro endpoint y que el miembro del agente no lleva.

## Lo que sí se mueve, y con qué cuidado

- **`ai-service/openapi.json`** se regenera por **adición pura** (`origin`). Hay que **sustituir el
  *fixture*** de `test_openapi_snapshot_is_stable` declarando la adición permitida — el propio test
  escribe que *«the next change that moves the contract replaces this fixture… deliberately»*, y C40
  fue el anterior que lo hizo. Tarea **3.10**. Comprueba que el diff del contrato es **sólo** adición.
- **`openspec/DEFERRED_TASKS.md`**, entrada de C32b: se cierra **por refutación y no por ejecución**,
  con la aritmética de una petición por minuto escrita. Tarea **11.3**.

## Entorno, antes de la primera tarea del grupo 10

- **`uv sync` y `uv run` necesitan `--system-certs`** en esta máquina.
- **`--system-certs` no arregla al proceso Python.** Cualquier llamada real al proveedor muere con
  `CERTIFICATE_VERIFY_FAILED` si no exportas un PEM del almacén de Windows en `SSL_CERT_FILE` (y
  `REQUESTS_CA_BUNDLE`). No afecta a los tests, que no llaman al proveedor, ni a los contenedores.
- **Cualquier script suelto que abra el motor asíncrono necesita
  `WindowsSelectorEventLoopPolicy`**, y **un escenario, un bucle**: dos `asyncio.run` en un test fallan
  con `InterfaceError`.
- **Escribir ficheros largos con la herramienta de escritura y nunca con heredoc.** El cuerpo del
  heredoc viaja en la línea de comandos y Windows la corta en 32.767 caracteres; el error dice
  `ENAMETOOLONG` y **miente sobre la causa**.

## Las tres líneas base, y por qué se comparan por nombres

La tarea **1.1 no se salta**. Las tres suites están rojas o inestables antes de que toques nada:

| Suite | Estado de partida | Cómo se juzga |
|---|---|---|
| `dotnet test` | **~50 rojos preexistentes**, con ~15 nombres que rotan entre pasadas del mismo commit | Por **nombres**, y el churn se confina a `InventoryIntegrationTests`, `PaymentMethodsControllerTests`, `ReturnsControllerTests` |
| `npm run test` en `frontend/` | **~113-114 de 729 en 14 ficheros**, con al menos tres ficheros que rotan | Por **nombres**. Un rojo nuevo en un fichero que tocas es regresión; uno más en `scan.test.tsx` es ruido |
| `uv run pytest` en `ai-service/` | **verde** | Cualquier rojo es tuyo |

**Y se lee la línea de resumen, no el código de salida**: `vitest` sale 0 al pipearlo, y un
`JoiabagurPV.API.exe` vivo hace que `dotnet test` salga 0 **con cero tests ejecutados**.

**El juicio que importa: cero nombres rojos nuevos en tu propia área.**

## Si algo del ticket o de la spec sale falso

Este repositorio lleva nueve changes seguidos cuya exploración refuta lo escrito antes, y eso **es el
comportamiento deseado**. Si al implementar descubres que una afirmación del ticket, una decisión del
design o un escenario de la spec no se sostiene:

1. **No lo implementes en silencio de otra manera.** Para, dilo, y propón.
2. Si la corrección es clara y estrecha, **enmienda la spec del change** —no la spec viva— y **escribe
   la refutación con su medición** en el informe de implementación.
3. Si mueve el alcance, **pregunta antes de seguir**.
4. Las tareas que no se ejecuten como están redactadas **se marcan con su razón en la propia línea**,
   como hizo C41 con tres de las suyas. Un verificador que lea `tasks.md` tiene que poder entender por
   qué sin abrir una incidencia falsa.

## Definición de hecho

- Las **75 tareas** marcadas, o marcadas con su razón escrita.
- **`openspec validate --all --strict` con `0 failed`** — y no `openspec validate` a secas, que
  **valida nada** y sale 1.
- **`dotnet build`** en 0 errores y **`npm run build`** en verde.
- **`tsc --noEmit` filtrado a tus ficheros**, sin errores nuevos. **Los dos son necesarios**: Vite
  transpila con esbuild y el build es verde sobre un error de tipos. C40 se comió un DTO desalineado
  por no hacer esto.
- **`uv run pytest`** en verde, sin llamadas reales a proveedor, embeddings ni base.
- Las tres suites comparadas **por nombres** contra la línea base de 1.1.
- `git status` limpio sobre la lista de *Lo que no se toca*.
- **La pasada de medición tomada con el contenedor arriba y el drenaje encendido**, con las **siete
  cifras** publicadas y el artefacto persistido con `run_id`, `git_sha`, `prompt_version` y antigüedad
  de proyección.
- **Las dos anotaciones** escritas (11.4 y 11.5).
- **La comprobación manual en el entorno levantado, con los dos roles** (12.1). Es la única puerta
  capaz de cazar la clase de defecto que C40 dejó pasar con 136 escenarios en verde, y un change que
  nace de dar superficie a algo que nadie había visto funcionar no se cierra sin ella.
- El informe `Documentos/Proyecto Final AIEng/informes/c42-implementation-measurements.md` escrito.

## Cómo quiero que trabajes

- **Commits por tramo**, no uno por tarea ni uno al final. Mensaje en castellano sin tildes, explicando
  **por qué** y no sólo qué, y terminando con la línea de coautoría que el repositorio usa.
- **Marca las tareas en `tasks.md` a medida que cierras cada una**, no al final.
- Cuando un tramo cierre, **di qué midió** si midió algo, y sigue. No pidas permiso para continuar con
  el siguiente tramo salvo que algo del alcance se haya movido.
- Si una decisión cerrada te parece equivocada, **dilo una vez, con el argumento, y respeta la
  decisión** si te confirmo que sigue en pie.
