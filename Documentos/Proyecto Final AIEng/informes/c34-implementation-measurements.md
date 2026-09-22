# C34 — informe de implementación: el card de venta en .NET, y lo que la implementación precisa

**Change:** `add-dotnet-assist-and-recommendation-endpoints` (C34) · **Rama:** `c34-add-dotnet-assist-and-recommendation-endpoints`
**Fecha:** 2026-09-21 · **Historia:** [HU-AIENG-034](../../Historias/AI-Eng/HU-AIENG-034.md) · **Ticket:** [T-AIENG-034](../../../openspec/changes/add-dotnet-assist-and-recommendation-endpoints/ticket.md) · **Exploración:** [c34-exploration-decisions.md](c34-exploration-decisions.md)
**Capability nueva:** `ai-sales-assist` — 15 requisitos, 45 escenarios · **Modificada:** `ai-gateway-client` — 1 `ADDED` (5 escenarios) y 5 `MODIFIED` (23 escenarios)

C34 entrega **el primer consumidor .NET de `POST /v1/assist/sale` y de `POST /v1/retrieval/substitutes`**:
dos rutas ancladas a una pieza —`POST /api/ai/products/{productId}/sales-assist` y
`GET /api/ai/products/{productId}/substitutes`—. Las dos autorizan el punto de venta y **comprueban
que la tienda lleva la pieza antes de gastar una llamada**; hidratan contra el catálogo de esa tienda;
resuelven `{{price}}`/`{{stock}}` contra la pieza anclada; y degradan sin romperse. Con ellas, el
cliente del gateway gana su tercera familia de ruta, la generativa, y la demo queda configurada para
generar.

**Lo primero que hay que decir es que ninguna decisión cerrada se ha movido y ninguna spec ha
necesitado corrección**: D-A, D-B, D-E y D-N se implementan tal cual, y `openspec validate --all
--strict` da 60 / 0 sin tocar una línea de las deltas. Lo que la implementación precisa son ocho
detalles que los artefactos no podían saber sin el árbol, en el §2. **Lo segundo es la latencia**
(§4): medida de extremo a extremo en Docker Compose, sin el interceptor de Norton y con proveedor
real, da **p95 7,1 s y máximo 7,9 s** sobre 80 peticiones, así que **`AssistTimeoutMs` se queda en
10.000**. **Lo tercero es lo que no está**: la credencial de la demo, su despliegue y la nueva medición
de memoria (11.3, 11.4) son pasos manuales del desarrollador; quedan declarados en el §6 con su motivo,
y **no se ha inventado ninguna cifra para cubrirlos**.

---

## 1 · Qué se entregó

| Pieza | Fichero | Estado |
|---|---|---|
| DTO del contrato de assist (`AssistRequest`, `AssistResponse`, `AssistGroup`, `AssistGroupMember`, `Citation`) | `Application/DTOs/Ai/AiAssistSaleDtos.cs` | **nuevo** |
| DTO del contrato de sustitutos (`SubstitutesRequest`, `SubstitutesResponse`, `SubstituteResult`, `SimilaritySignals`) | `Application/DTOs/Ai/AiSubstitutesDtos.cs` | **nuevo** |
| DTO hacia el frontend, `PitchStatus` y `SubstitutesOutcome` en *snake_case* | `Application/DTOs/Ai/SalesAssistDtos.cs` | **nuevo** |
| `AiRequestRejectedException` y `AiGatewayOutcome.Rejected` | `Application/Exceptions/`, `DTOs/Ai/AiGatewayOutcome.cs` | **nueva** / ampliado |
| `AssistSaleAsync` y `SubstitutesAsync`, con su traducción del 422 | `IAiGatewayClient.cs`, `AiGatewayClient.cs` | ampliados |
| Cliente `ai-assist` en el hueco reservado de la L148, y el suelo de 8 s | `AiGatewayServiceCollectionExtensions.cs`, `AiGatewayOptions.cs`, `appsettings.json` | ampliados |
| `AiSalesAssistOptions` y su validación al arranque | `Configuration/AiSalesAssistOptions.cs`, `Extensions/AiSalesAssistServiceCollectionExtensions.cs` | **nuevos** |
| Política `AiSalesAssistRateLimit`, particionada por usuario | `API/Extensions/ServiceCollectionExtensions.cs` | ampliado |
| Comprobación de acceso y de pieza compartida | `Services/SalesCardAccess.cs` | **nuevo** |
| Resolvedor de marcadores, unidad pura | `Services/PitchPlaceholderResolver.cs` | **nuevo** |
| Servicio de asistencia | `Services/SalesAssistService.cs` | **nuevo** |
| Servicio de sustitutos | `Services/SubstitutesService.cs` | **nuevo** |
| Validadores FluentValidation | `Validators/SalesAssistRequestValidator.cs` | **nuevo** |
| `AiSalesAssistController` con `[Route("api/ai/products")]` | `API/Controllers/AiSalesAssistController.cs` | **nuevo** |
| Clase base `ThrowingAiGatewayClient` y los siete dobles migrados | `Tests/TestHelpers/`, cuatro ficheros de integración | **nueva** / migrados |
| `FakeHttpMessageHandler`: conexión no abierta, cuelgue real, cuerpos leídos | `Tests/TestHelpers/FakeHttpMessageHandler.cs` | ampliado |
| Demo: modelo y credencial en `jbg-demo-ai`, interruptor y presupuesto en la API | `compose.demo.yaml`, `deploy/demo/deploy.sh`, `deploy/demo/README.md` | ampliados |

**Sin migración de EF Core, sin tocar `ai-service/`, `frontend/`, `terraform/` ni `.github/`**, y
`AssistedSearchService` y `POST /api/ai/search` intactos. El `AuthoriseAsync` de C15 **se replicó** en
`SalesCardAccess` en vez de extraerse: es privado, devuelve el tipo de resultado propio de la búsqueda,
y moverlo tocaba una ruta que este change promete dejar exactamente como estaba.

### Las puertas

| Puerta | Resultado |
|---|---|
| Suite de backend, **por nombres** | ver §3 |
| `ai-service/openapi.json` | **`sha256 d8d48f87b279d45d22bce80a67c4fd51caef6e679363c413f5b697c99ec2b875`** al empezar y al terminar: **idéntico byte a byte** |
| `git diff` en `ai-service/`, `frontend/`, `terraform/`, `.github/` y `Infrastructure/Migrations/` | **vacío** |
| `openspec validate --all --strict` | **60 passed / 0 failed** al empezar y al terminar: las 59 specs vivas y este change, el único activo |
| `docker compose -f compose.demo.yaml config` | resuelve **con y sin** `ASSIST_LLM_API_KEY` |
| `bash -n deploy/demo/deploy.sh` | sintaxis correcta |

---

## 2 · Lo que la implementación precisa de la HU, el ticket y el design

Ninguna de las ocho toca una decisión cerrada ni obliga a corregir una spec. Se anotan porque cada una
habría costado tiempo a quien la descubriera después.

### 2.1 · `AssistRequest.product_id` es nulable en el contrato, así que la garantía vive en una guarda y no en el tipo

**Lo que decían los artefactos.** El ticket esboza `AiAssistSaleRequest` con `product_id (siempre)`, y
la delta de `ai-gateway-client` exige que *«a sale assistance request without a product MUST NOT be
issued»*.

**Lo que hay en el árbol.** `openapi.json` declara `product_id` como `anyOf [string, null]`, porque
Python sirve también la consulta libre. `AiContractSnapshotTests` **falla** si el modelo .NET no es
nulable donde el contrato lo es — está hecho exactamente para eso. Así que el DTO lleva `string?
ProductId` y la garantía es una **guarda en `AssistSaleAsync`** que lanza `ArgumentException` antes de
emitir nada (`AssistSaleAsync_WithoutProduct_IsRejectedBeforeAnyRequest`). La spec se cumple igual; lo
que cambia es dónde vive.

### 2.2 · `EnqueueHang` no simula un timeout que el *pipeline* vea, y el suelo de 8 s impide acortar el presupuesto

**Lo que decía la tarea 3.4.** `AssistSaleAsync_WhenTimeout_DoesNotRetry`, con `AiGatewayTestHost`
ampliado.

**Lo que hay en el árbol.** El doble de C03, `FakeHttpMessageHandler.EnqueueHang()`, **lanza
`TaskCanceledException` en el acto**: el `TimeoutStrategy` de Polly nunca ve expirar su presupuesto, y
el predicado de reintento recibe una cancelación y no un `TimeoutRejectedException`. Con él, un test
«no reintenta el timeout» pasaría **aunque el predicado sí reintentara timeouts**, porque el fallo que
ve no es un timeout. Y el remedio obvio —un presupuesto de 60 ms como el del test de recuperación— lo
prohíbe el suelo de 8.000 ms que este mismo change valida al arranque.

**Lo que se hizo.** Un `EnqueueHangUntilCancelled()` que espera de verdad a la cancelación, y un
`FakeTimeProvider` registrado **antes** de `AddAiGateway`: el *pipeline* de resiliencia lo toma del
contenedor, el test avanza 10.001 ms y la estrategia de timeout dispara como en producción. Medido: el
test corre en milisegundos, y el registro de fallo dice `outcome=timeout`. **El test de recuperación
existente, `SearchAsync_WhenTimeout_ThrowsAiUnavailable`, sigue usando `EnqueueHang` y por tanto no
ejercita el timeout de Polly**; no se toca porque es de C03 y pasa, pero queda dicho aquí.

### 2.3 · El registro de servicios no cabe en `AddApplication()`

**Lo que decía la tarea 8.4.** *«Registrar los servicios en `Application/Extensions/ServiceCollectionExtensions.cs`»*.

**Lo que hay en el árbol.** Las opciones necesitan `IConfiguration`, y la firma de `AddApplication()`
—sin parámetros— la usan los tests de integración. El precedente es `AddAssistedSearch(configuration)`
de C15, en su propio fichero y llamado desde `Program.cs`. Se sigue ese precedente
(`AddSalesAssist`), y **la tarea 8.4 se corrigió en `tasks.md`** para decir dónde quedó.

### 2.4 · Poner la clave de assist en la demo enciende también el cliente del enrutador

**Lo que decía el ticket.** *«El enrutador de C31 no hace falta en la demo para C34: M2 y M3 no lo
invocan.»* Cierto, y verificado en `orchestrator.py`: el clasificador corre **sólo** en
`AssistMode.QUERY_ONLY`.

**Lo que el ticket no dice.** `_resolve_router_client` repliega a `JPV_ASSIST_LLM_API_KEY` cuando no
hay `JPV_ROUTER_LLM_API_KEY`, y se resuelve en cada petición a `/v1/assist/sale`. Con la clave puesta,
**el log de `jbg-demo-ai` mostrará dos líneas**: la esperada `stage=assist_client … credential=assist`
y además `stage=router_client … credential=assist_fallback`. La segunda no gasta nada —el enrutador
sólo corre en M1, que C34 no expone—, pero quien siga el runbook y la vea sin aviso pensará que algo
está mal configurado. Queda escrito en `deploy/demo/README.md` §5.6b, en `compose.demo.yaml` y en la
entrada de `DEFERRED_TASKS.md`.

### 2.5 · La entrada diferida de C30b nombraba un prompt que ya no es el vigente

La verificación de la entrada decía que `prompt_version` pasaría *«de `null` a `assist/v1`»*. La
versión vigente para M2 y M3 es **`assist/v3`** (`assist/constants.py:150`). Corregido en la entrada.

### 2.6 · Tres huecos que los artefactos no cubren, resueltos por la opción más estrecha

La regla del ticket para un detalle no listado es *«la más estrecha que no abra migración, no toque
`ai-service/`, no cambie `POST /api/ai/search` y no afloje ninguna regla de logs»*:

| Hueco | Lo que se hizo | Test |
|---|---|---|
| La respuesta de la IA **no trae** un grupo con la pieza anclada (imposible por contrato en M2/M3) | La pieza se sirve sola, primera, y se registra un aviso: un card sin su propia pieza es lo único que el operario no puede sortear | `SalesAssist_WhenTheAiGroupLacksTheAnchor_ServesTheAnchorAlone` |
| La IA devuelve un código de stock (`stock_critical`, `family_members_out_of_stock`) | Se **descarta** del lado de la IA antes de añadir los de .NET: la spec dice que no se derivan de ningún valor de la respuesta | `SalesAssist_StockCodesInTheAiResponse_AreNotTakenAsTheirOwn` |
| La ventana de sustitutos incluye la pieza misma | Se excluye: una pieza no es su propio sustituto | `Substitutes_NeverOfferTheProductItself` |

Y un cuarto, de forma y no de regla: **`intent` es nulable en la respuesta hacia el frontend**. En el
camino degradado no contestó ninguna IA, y el ticket lo esbozaba como `string`; un valor inventado
(`product_pitch`) diría que la IA clasificó algo que no clasificó.

### 2.7 · El log distingue el motivo de la degradación con un campo que D13 no listaba

D13 enumera los campos de `stage=sales_assist` y la spec exige que *«the log MUST record that the
switch, and not an outage, produced the answer»*. Ningún campo de D13 lo dice, así que la línea lleva
además **`degraded_reason`** (`switched_off`, `ai_unavailable`, `product_not_indexed`,
`credential_rejected`, `not_implemented`, `unclassified`) y la de sustitutos **`reason`**. `pitch_len`
es la longitud del argumentario **entregado** (0 si se retira); la del texto crudo ya la lleva
`ai_gateway_assist_completed` con el mismo `trace_id`.

### 2.8 · El MITM de Norton no alcanza a los contenedores, así que `SSL_CERT_FILE` no hace falta en Docker

**Lo que decían la tarea 10.1 y CLAUDE.md.** Medir *«sin pasar por el interceptor TLS de Norton (o
declarando que pasa)»*, y la nota de que *«cualquier llamada real al proveedor […] muere con
`CERTIFICATE_VERIFY_FAILED`»* salvo que se apunte `SSL_CERT_FILE` a un PEM con la raíz de Norton.

**Lo que se midió.** Desde un contenedor `python:3.11-slim-bookworm`, el TLS de `api.openai.com` y de
`pypi.org` **se verifica con el bundle del sistema**, y el emisor es la CA real (*Google Trust Services*
y *GlobalSign*). La reconstrucción de la imagen de `jbg-ai` bajó sus dependencias sin tocar certificados,
y las 81 peticiones del §4 llegaron al proveedor sin un error de TLS. **La nota de CLAUDE.md sigue
siendo cierta para Python en el host** —`uv run`, un *spike*, `evals`—, que es lo que describe; en
Docker no aplica. Se añade esa precisión a CLAUDE.md, en una línea.

---

## 3 · La suite, por nombres

| | Línea base (árbol limpio, `6030aa3`) | Cierre (con C34) |
|---|---|---|
| Tests | **1.060** | **1.239** (+179) · **1.240** con `SalesAssist_KnowledgeNotCovered_IsPassedThrough`, añadido tras la corrida y pasado aparte |
| En rojo | **46** | **46** |
| Nombres de la línea base ausentes al cierre | — | **0** |
| Nombres nuevos (de C34) en rojo | — | **0** |
| Duración | 7 min 29 s | 16 min 52 s (§3.2) |

**El recuento coincide, pero el conjunto no, y eso es lo que había que mirar.** Cuatro nombres entran en
rojo y otros cuatro salen:

| Entran en rojo al cierre | Salen del rojo al cierre |
|---|---|
| `InventoryIntegrationTests.Admin_AccessCentralizedInventory_ShouldSucceed` | `InventoryIntegrationTests.AssignProduct_WithNonExistentProduct_ShouldReturnNotFound` |
| `InventoryIntegrationTests.GetStock_WithNonExistentPOS_ShouldReturnEmpty` | `InventoryIntegrationTests.MovementHistory_WithPagination_ShouldReturnPagedResults` |
| `InventoryIntegrationTests.MovementHistory_WithDateRangeFilter_ShouldFilterCorrectly` | `InventoryIntegrationTests.ProductCatalog_AsAdmin_ShouldSeeAllProducts` |
| `ProductsControllerTests.Update_WithValidData_ShouldReturnUpdatedProduct` | `InventoryIntegrationTests.StockValidation_WithLowStockAfterSale_ShouldReturnWarning` |

- **Los cuatro que entran pasan ejecutados aislados sobre el árbol con C34** (5 de 5, junto con el test
  añadido después).
- **Los tres de `InventoryIntegrationTests` son la rotación documentada**: [testing-backend.md](../../testing-backend.md)
  registra que esa clase *«baraja los suyos de una vez a otra»*. Ni C34 ni sus tests tocan inventario.
- **`Update_WithValidData_ShouldReturnUpdatedProduct` es una carrera de reloj que no estaba registrada.**
  El mensaje: *«Expected updated.UpdatedAt to be on or after <…13.279962>, but found <…13.279326>»*:
  `UpdatedAt` queda **0,6 ms antes** que `CreatedAt`, en `ProductsController`, que C34 no toca. Pasa
  aislado. Se anota aquí como hallazgo para el inventario de fallos conocidos; no se arregla, porque no
  es de este change.

**Los tests de C15 no cambian de resultado** (tarea 9.3): `AiSearchControllerTests` (15),
`AiSearchRateLimitTests` (3) y `AssistedSearchServiceTests` (37), en verde en la línea base y al
cierre. **Y ninguna de las clases que alojan los siete dobles migrados cambia**: `AiCatalogControllerTests`
(10), `AiHealthControllerTests` (3), `FamilyReviewControllerTests` (28) y `FamilySuggestionControllerTests`
(12), en verde en las dos corridas.

### 3.1 · Los tests nuevos

| Clase | Tests | Tipo |
|---|---|---|
| `AiGatewayAssistTests` | 19 | pipeline real con socket falso |
| `AiContractSnapshotTests` | +11 (26) | contrato contra `openapi.json` |
| `AiGatewayRegistrationTests` | +3 (10) | arranque |
| `AiGatewayClientTests` | +1 (15) | `SearchAsync_When422_StillThrowsUnavailable` |
| `PitchPlaceholderResolverTests` | 16 | unidad pura |
| `SalesAssistServiceTests` | 42 | servicio con dobles |
| `SubstitutesServiceTests` | 19 | servicio con dobles |
| `SalesAssistConfigurationTests` | 39 | opciones, validadores, forma del cable |
| `AiSalesAssistControllerTests` | 27 | integración: Testcontainers + doble del gateway **que se comprueba invocado** |
| `AiSalesAssistRateLimitTests` | 3 | integración, host propio con límite 2 |

**Los de integración llegan al gateway, a diferencia de los de C15.** El host enciende
`AiSalesAssist:EnabledByDefault` de forma explícita y sustituye el gateway por un doble que cuenta sus
llamadas; cada test servido afirma el recuento, y cada rechazo afirma **cero**.

### 3.2 · Por qué la corrida de cierre tardó más del doble

No es C34. La suma de duraciones por test pasa de 113 s a 216 s, pero **las clases que más crecen son
previas y no se han tocado**: `RateLimitingTests` 14,7 → 33,7 s, `ProductFamiliesControllerTests`
10,6 → 28,8 s, `FamilyReviewControllerTests` 12,2 → 26,8 s. Las diez clases nuevas suman **~10 s**, y
ninguna está entre las catorce más lentas. La máquina estaba más cargada durante la segunda corrida.

---

## 4 · La latencia de extremo a extremo (tarea 10.1): `AssistTimeoutMs` se queda en 10.000

**Montaje.** `jbg-ai` reconstruido desde el árbol actual y levantado en el `backend/docker-compose.yml`
local con un *override* temporal fuera del repositorio (`STUB_MODE=false`, `JPV_ASSIST_LLM_MODEL=openai/gpt-4o-mini`
—el de la demo y el de todas las cifras de C30b— y las claves interpoladas desde `backend/.env`, sin
escribirlas en ningún fichero); índice local completo (1.168 documentos de producto y 161 fragmentos del
corpus, `/health` en `ok`). La API .NET en el host, `Development`, con `AiSalesAssist__EnabledByDefault=true`
y el límite de peticiones subido **sólo para la medición** (80 peticiones de un usuario agotan los 10
por minuto). Cronómetro en el cliente: **cliente → .NET → `jbg-ai` en Docker → proveedor**.

**Sin el interceptor de Norton, y comprobado, no supuesto.** Desde un contenedor, el TLS de
`api.openai.com` se verifica con el bundle del sistema y lo firma su CA real (*Google Trust Services*):
el MITM de Norton intercepta el tráfico del host, no el de la VM de Docker. Es el caso limpio que la
tarea pedía.

**Muestra.** Las **40 piezas** de `ai-service/evals/assist/sweep-sample.yaml` (20 de un material y 20
de dos o más), cada una en el punto de venta activo que más unidades tiene de ella —las 40 con stock—.
Por pieza, una petición **M2** (sin pregunta) y una **M3** (con una de cuatro preguntas de mostrador,
rotando): **80 peticiones en serie**, más una de calentamiento que queda fuera porque paga la
construcción perezosa de los clientes (4,6 s). 2026-09-22, de madrugada, desde España.

| | n | p50 | p95 | máx | mín | > 8 s | > 10 s |
|---|---|---|---|---|---|---|---|
| **M2** | 40 | **3,64 s** | **7,28 s** | **7,93 s** | 2,35 s | 0 | 0 |
| **M3** | 40 | **5,39 s** | **7,04 s** | **7,54 s** | 1,30 s | 0 | 0 |
| **Todas** | 80 | **4,42 s** | **7,13 s** | **7,93 s** | 1,30 s | 0 | 0 |

**El tiempo es la IA, no .NET.** Cruzando cada petición con su línea `stage=sales_assist` por
`trace_id` (80 de 80): `ai_ms` p50 4,40 s · p95 7,12 s · máx 7,91 s; **`total_ms − ai_ms` = p50 4 ms,
máx 13 ms** —autorización, dos hidrataciones, avisos y marcadores—; y el tramo HTTP del cliente a
`total_ms`, p50 7 ms.

**Lo que devolvió.** **0 degradadas** (`aiAvailable: true` en las 80); **74 `generated`** y **6
`withheld_by_ai`** (3 y 3: las puertas de Python retirando); **0 argumentarios con `{{` o `}}`
sobrantes**. De los 37 generados en M2, **22 llevan el precio de catálogo** formateado (59 %, en línea
con el 69 % de «disponible por {{price}}» que C30b midió); en M3 sólo 3 de 37, porque una respuesta
sobre cómo limpiar una pieza no habla de precio. `knowledge_not_covered` apareció en 9 de las 40 M3:
el código pasa tal cual, que es lo que C36 necesita para no fingir que se contestó.

**La política de logs, comprobada sobre el log real de esta corrida y no sólo en test:** en las líneas
del backend **no aparece ni un «€»** —el precio resuelto—, **ni un `{{`**, ni ninguna de las cuatro
preguntas. Y el log de `jbg-ai` da exactamente las dos líneas que el §2.4 anticipa:
`stage=assist_client model=openai/gpt-4o-mini timeout_s=4.0 credential=assist` y
`stage=router_client model=openai/gpt-4o timeout_s=2.0 credential=assist_fallback`.

**La decisión: `AssistTimeoutMs` se queda en 10.000, y no se baja.** El máximo medido, **7,91 s en la
IA**, está al 99 % del suelo de 8.000: bajar al suelo dejaría sin margen justo las peticiones más
lentas, que son las que hacen la reparación del argumentario y que 5 s ya cortaban. 10 s deja **2,1 s
por encima del máximo observado** y cubre el peor caso declarado (2 × 4 s más las lecturas, ≈ 8,5 s).
**Y nada justifica subirlo**: ninguna de las 80 pasó de 8 s.

**Lo que esta cifra no es.** n = 80, una máquina de desarrollo, una franja horaria y un proveedor sin
carga de otros operarios. **No sustituye la medición en la demo** (eu-west-1, `t3.small`), que es la
11.4 y queda pendiente con ella. Los datos crudos —estado, longitud y tiempos, **sin el texto de ningún
argumentario**— se guardaron en el *scratchpad* de la sesión (`latency-results.json`).

---

## 5 · Mutaciones de control

Un test en verde a la primera no demuestra nada si no se ha visto fallar. Se hicieron tres mutaciones
a mano, se comprobó que rompían exactamente los tests que debían romper, y se revirtieron:

| Mutación | Tests que fallaron |
|---|---|
| `AiSimilaritySignals.StyleSimilarity` renombrada a `StyleScore` | `Dtos_MatchCommittedOpenApiSchema(AiSimilaritySignals, "SimilaritySignals")` — *«`style_score`, which must exist in schema SimilaritySignals»* |
| `family_has_variants` nunca se retira (`Count < 0`) | `SalesAssist_FamilyHasVariantsDroppedWhenOneMemberSurvives` |
| La regla de pieza agotada ignora la pregunta | `SalesAssist_AnchorOutOfStock_WithholdsPitchWithoutQuestion_KeepsItWithQuestion` |

Un primer intento de la mutación de contrato, sobre `AiCitation.ClaimScope`, **no demostró nada**:
rompía la compilación de otro test y la suite corrió contra los binarios anteriores. Se repitió sobre
una propiedad que ningún test nombra.

---

## 6 · Lo que no se hizo, y por qué

| Tarea | Estado | Motivo |
|---|---|---|
| **11.3** Crear `/jbg-demo/ASSIST_LLM_API_KEY` y desplegar | **pendiente, manual** | Es un secreto: se crea a mano como los otros seis, fuera de Terraform. El comando y lo que hay que ver en el log están en `deploy/demo/README.md` §3 y §5.6b |
| **11.4** Memoria de `jbg-demo-ai` y cuota de tokens por minuto | **pendiente** | Sólo tiene sentido tras 11.3. Estaba en **232,5 MiB de 512** sin generación; `DEFERRED_TASKS.md` (*Instance sizing*) dice qué anotar |

**La HU pide una cifra que este informe no da**: el escenario 12 («la demo enseña el argumentario»)
queda sin cubrir hasta 11.3. La medición local del §4 enseña que el mecanismo funciona con el proveedor
real —74 argumentarios generados y resueltos, 0 con marcadores—, pero no es la demo.

---

## 7 · Limitaciones que se declaran y no se cierran

1. **El 11,7 % de los argumentarios escribe `{{stock}}` donde un número no encaja** («y en
   {{stock}}»). La sustitución por un entero lo deja gramaticalmente torpe pero no falso. Arreglarlo
   es un cambio de prompt con su pasada de medición, en Python.
2. **Cuando .NET retira el argumentario, las citas son sólo las que ese argumentario usó**, un
   subconjunto de las que fundamentaron la respuesta. Python, cuando lo retira él, devuelve todas. .NET
   no puede reconstruir la diferencia.
3. **En el cuerpo de `/sales-assist` el 422 no se distingue de la caída** (D11): los dos dan
   `aiAvailable: false`. El log sí los distingue (`degraded_reason=product_not_indexed`). Si C36
   necesita decir «esta pieza aún no está preparada», se añade un campo sin romper nada.
4. **Una familia editada tarda en verse** en el camino nominal hasta la siguiente sincronización del
   índice; el degradado lee `ProductFamily` y no tiene ese desfase.
5. **El test de timeout de recuperación de C03 no ejercita el timeout de Polly** (§2.2). No es de este
   change y no se toca.
6. **`ProductsControllerTests.Update_WithValidData_ShouldReturnUpdatedProduct` es intermitente** por una
   carrera de reloj de 0,6 ms (§3), y no estaba en el inventario de fallos conocidos. No es de este
   change y no se toca.
7. **La latencia es de una máquina de desarrollo** (§4): n = 80, una franja horaria, sin concurrencia.
   La de la demo, en eu-west-1, es la 11.4.

---

## 8 · Trazabilidad de los trece escenarios de la HU

| # | Escenario | Tests |
|---|---|---|
| 1 | El argumentario llega con precio y stock reales | `SalesAssist_ReplacesPlaceholdersWithRealValues` · `SalesAssist_M2_ServesTheHydratedGroupAndTheResolvedArgument` *(int.)* · `PlaceholderResolver_ReplacesBothTokens_WithAnchorValues` · `PlaceholderResolver_Stock_IsAnInvariantWholeNumber` |
| 2 | Una pregunta devuelve citas con su alcance; viaja en el cuerpo; el corpus que no cubre lo declara | `SalesAssist_WithQuestion_ReturnsCitationsCarryingClaimScope` · `SalesAssist_M3_ReturnsCitationsWithTheirScope` *(int.)* · `SalesAssist_QuestionTravelsInTheBodyNeverInTheUrl` *(int.)* · `SalesAssist_KnowledgeNotCovered_IsPassedThrough` · `AssistSaleAsync_WhenServiceReturns200_MapsResponseInFull` |
| 3 | Un marcador sin resolver retira el argumentario y no la respuesta | `SalesAssist_WhenPlaceholderUnresolved_WithholdsThePitchInsteadOfShippingTheRawTemplate` · `SalesAssist_UnresolvedPlaceholder_WithholdsTheArgumentAndKeepsTheRest` *(int.)* · `PlaceholderResolver_UnknownPlaceholder_Withholds` · `PlaceholderResolver_VariantSpelling_Withholds` · `PlaceholderResolver_MalformedToken_Withholds` |
| 4 | Pieza agotada: sin argumento de venta, con respuesta a la pregunta | `SalesAssist_AnchorOutOfStock_WithholdsPitchWithoutQuestion_KeepsItWithQuestion` · `SalesAssist_SoldOutAnchor_WithholdsTheArgumentWithoutQuestion_AndAnswersWithOne` *(int.)* · `SalesAssist_AnchorWithZeroStock_IsServed` *(int.)* · `SalesAssist_WithheldByAi_WinsOverOutOfStock` |
| 5 | Avisos de stock de .NET; variantes ajustadas a la tienda | `SalesAssist_StockWarningsComputedAfterHydration_NotTakenFromPython` · `SalesAssist_FamilyHasVariantsDroppedWhenOneMemberSurvives` · `SalesAssist_FamilyHasVariantsKeptWhenTwoMembersSurvive` · `SalesAssist_FamilyHasVariantsNeverAddedOnTheServedPath` · `SalesAssist_DropsMembersThePointOfSaleDoesNotCarry` · `SalesAssist_ZeroStock_IsNotCriticalStock` · `SalesAssist_CriticalStock_FollowsTheDefaultThreshold` |
| 6 | Permisos antes de gastar una llamada | `SalesAssist_AsOperatorOfAnotherPos_Returns403` · `SalesAssist_AnchorNotCarriedAtPos_Returns404WithoutCallingAi` · `SalesAssist_WhenPointOfSaleInactive_IsRefused` · `SalesAssist_WithoutPointOfSale_Returns400WithoutCallingAi` · `Substitutes_AsOperatorOfAnotherPos_Returns403` · `Substitutes_AnchorNotCarriedAtPos_Returns404WithoutCallingAi` *(todos int., con el doble contando cero llamadas)* |
| 7 | Los sustitutos se pueden vender hoy en esa tienda | `Substitutes_ExcludeProductsWithoutStockAtTargetPos` · `Substitutes_KeepTheOrderOfTheAiService` · `Substitutes_TruncateToThePageAfterFiltering` · `Substitutes_AlwaysRequestsTheLargestWindow` · `Substitutes_ShortPage_DoesNotTriggerASecondCall` · `Substitutes_OfferOnlyWhatTheShopCanSellToday_InTheOrderOfTheAi` *(int.)* |
| 8 | Los cuatro vacíos se distinguen | `Substitutes_DistinguishesTheFourEmptyOutcomes` (×4) · `Substitutes_TheFourOutcomesAreDistinguishable` *(int., ×4)* · `SubstitutesAsync_When422_ThrowsRequestRejected_NotUnavailable` |
| 9 | Con la IA caída el card sale igual | `SalesAssist_WhenAiUnavailable_ServesAnchorAndFamilyFromCatalog` · `SalesAssist_WhenAiUnavailable_ServesTheFamilyFromTheCatalog` *(int.)* · `SalesAssist_AnyGatewayFailure_DegradesAndNeverThrows` (×4) · `SalesAssist_WhenCredentialRejected_DegradesAndLogsError` · `SalesAssist_When422_DegradesAndLogsProductNotIndexed` |
| 10 | Un timeout no se reintenta; el presupuesto cubre el peor caso | `AssistSaleAsync_WhenTimeout_DoesNotRetry` · `AssistSaleAsync_When503_DoesNotRetry` · `AssistSaleAsync_WhenConnectionNeverOpened_RetriesOnce` · `AssistSaleAsync_WhenItsCircuitOpens_RetrievalKeepsWorking` · `AddAiGateway_WhenAssistBudgetBelowServiceWorstCase_FailsAtStartup` · y la medición del §4: máximo 7,9 s, **0 de 80** por encima de 8 s |
| 11 | Nada de lo que se pregunta ni se responde queda en un log | `SalesAssist_ResolvedPitchIsNeverLogged` · `SalesAssist_QuestionIsLoggedOnlyAtDebug` · `SalesAssist_LogLine_CarriesTheFieldsOfTheDesign` · `Substitutes_LogsTheFunnel` · `AssistSaleAsync_CompletionEvent_CarriesNoArgumentText` · y el log real del §4: ni un «€», ni un `{{`, ni una pregunta |
| 12 | La demo enseña el argumentario | **pendiente de 11.3 / 11.4** (§6). La configuración está verificada con `docker compose config`, y el mecanismo, con proveedor real en local (§4) |
| 13 | Fuera de alcance: ni consulta libre, ni agente, ni contrato de Python | `SalesCard_ExposesNoRouteForAFreeQuestionOrTheAgent` *(int.)* · `AssistSaleAsync_WithoutProduct_IsRejectedBeforeAnyRequest` · `sha256` idéntico (§1) · `git diff` vacío en migraciones · los tests de C15 sin cambio de resultado (§3) · `SearchAsync_When422_StillThrowsUnavailable` |

---

## 9 · Cómo se reproduce

```bash
# Línea base y cierre, por nombres (el árbol limpio hace del stash un no-op)
git stash push -u && dotnet test backend/src/JoiabagurPV.sln --logger "trx;LogFileName=x.trx"; git stash pop

# Contrato
sha256sum ai-service/openapi.json            # d8d48f87…c2b875

# Gate de OpenSpec
openspec validate --all --strict             # 60 passed, 0 failed

# Demo, sin desplegar
docker compose -f compose.demo.yaml config   # con variables de ejemplo exportadas

# Latencia (§4): jbg-ai real en el compose local con un override que ponga STUB_MODE=false y pase
# JPV_EMBEDDING_API_KEY / JPV_ASSIST_LLM_API_KEY por interpolación desde backend/.env; la API en el
# host con AiSalesAssist__EnabledByDefault=true; 40 piezas de sweep-sample.yaml × {M2, M3}, en serie.
docker compose -f backend/docker-compose.yml -f <override> up -d --no-deps jbg-ai
```
