# QA — C03 `add-dotnet-ai-gateway-client`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-09 · **Rama:** `c03-add-dotnet-ai-gateway-client` · **Commit de implementación:** `47c63ad`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| SDK | .NET 10.0.302 |
| Solución | `backend/src/JoiabagurPV.sln` |
| Marco de pruebas | xUnit + FluentAssertions + Moq (convención existente) |
| Paquetes nuevos en test | `Microsoft.Extensions.TimeProvider.Testing` 10.8.0 (`FakeTimeProvider`) |
| Servicio de IA | `jbg-ai` en Docker Compose, `8001:8000`, `STUB_MODE=true` — **solo para el humo**; la suite no lo necesita |
| Contrato | `ai-service/openapi.json`, sin modificar |

---

## 1. Suite automática

| Ejecución | Aprobados | Fallos | Total |
|---|---|---|---|
| **Baseline** (`git stash -u`, sin código de C03) | 265 | 10 | 275 |
| Tras implementación | 302 | 10 | 312 |
| Tras cerrar los huecos del verify | **305** | **10** | **315** |

**Los 10 fallos son preexistentes y están verificados como tales**, no asumidos: se ejecutó la suite completa con el árbol de trabajo guardado en `git stash`, sobre el commit `1a6f1c0`, y la lista de fallos resultó **idéntica** nombre por nombre. Afectan a `ImageCompressionServiceTests` (5), `QrCodeServiceTests` (2), `InventoryServiceTests` (2) y `ExcelImportServiceTests` (1) — imágenes, PDF, Excel y transacciones, ninguna zona que este change toque.

**40 tests nuevos, cero regresión.** `dotnet build` de la solución: **0 errores**.

### Los quince tests exigidos por el ticket

| Test | Criterio | Resultado |
|---|---|---|
| `SearchAsync_WhenServiceReturns200_MapsResponse` | 1 | ✅ |
| `SearchAsync_WhenFamilyIdIsNull_MapsToNullWithoutThrowing` | 1 | ✅ |
| `BuildToken_IncludesPosAndRoleClaims` | 2 | ✅ |
| `BuildToken_UsesSnakeCaseClaimNames` | 2 | ✅ |
| `BuildToken_OmitsAudienceAndIssuer` | 2 | ✅ |
| `BuildToken_ExpiresAfterConfiguredTtl` | 2 | ✅ |
| `ForPointOfSale_WhenPointOfSaleIsEmpty_ThrowsArgumentException` | 3 | ✅ |
| `SearchAsync_WhenTimeout_ThrowsAiUnavailable` | 4 | ✅ |
| `SearchAsync_WhenCircuitOpen_FailsFastWithoutCall` | 4 | ✅ |
| `SearchAsync_WhenServiceReturns501_DoesNotRetryAndThrowsNotImplemented` | 5 | ✅ |
| `SearchAsync_WhenServiceReturns401_DoesNotRetry` | 5 | ✅ |
| `SearchAsync_WhenServiceReturns503_RetriesOnceThenSucceeds` | 5 | ✅ |
| `AddAiGateway_WhenSecretMissing_FailsOnStart` | 6 | ✅ |
| `SearchAsync_SendsBearerTokenAndTraceHeader` | 7 | ✅ |
| `Dtos_MatchCommittedOpenApiSchema` | 9 | ✅ |

### Tests añadidos por encima de lo exigido

| Test | Qué protege |
|---|---|
| `AiCallScope_ExposesNoPublicConstructor` | Que el ámbito siga siendo clase sellada: un `struct` tendría `default` con punto de venta vacío |
| `ForPointOfSale_WhenRoleIsBlank/UserIsEmpty_ThrowsArgumentException` | Los otros dos argumentos de la fábrica |
| `BuildToken_UsesHmacSha256` · `BuildToken_WhenTraceIdIsBlank_Throws` | Algoritmo y precondición del emisor |
| `SearchAsync_WhenServiceOverFetches_ReturnsEveryCandidate` | Que el cliente **no trunca**: truncar es de C15 |
| `SearchAsync_WhenTransportFails_ThrowsAiUnavailableAfterOneRetry` | Fallo de red frente a fallo de estado |
| `AddAiGateway_WhenSecretTooShort/BaseUrlNotAbsolute_FailsOnStart` | Las otras dos validaciones de arranque |
| `AddAiGateway_WhenDisabled_RegistersNothingAndDoesNotValidate` | Que una integración apagada no impida arrancar |
| `SearchRequest_OmitsPosIdEvenThoughTheContractAcceptsIt` | Que no se envíe un campo que el servicio ignora |
| `SerilogEnvironmentProfileTests` (4) | El render por entorno y la trampa de fusión de configuración |
| `SearchAsync_WhenCallCompletes_EmitsCompletionEventWithLatencyAndCounts` | Evento de finalización observable |
| `SearchAsync_WhenCallFails_EmitsFailureEventWithOutcomeAndBaseUrl` | `outcome` y `base_url` en el fallo |
| `SearchAsync_QueryTextNeverRisesAboveDebug` | **Regla de privacidad** del diseño §8.5 |

---

## 2. Smoke end-to-end contra el servicio real

Es la única comprobación que ejercita el **validador PyJWT auténtico** en lugar de una creencia sobre él, y por eso es la de más peso del change.

```text
docker compose up -d jbg-ai      → Container jpv-pv-jbg-ai Started
curl http://localhost:8001/health → 200 {"status":"OK","version":"0.1.0"}
SearchAsync(top_k = 5)            → candidates_returned = 15, Results.Count = 15
                                     trace_id devuelto = "smoke-trace-001"
                                     effective_pos_id presente
```

Cuatro cosas quedan demostradas de una vez:

1. **El token se acepta.** La decisión de no emitir `aud`, `iss` ni `nbf` es correcta contra la implementación real, no contra mi lectura de su código fuente.
2. La regla de sobre-recuperación `min(top_k × 3, 60)` se cumple y **el cliente no trunca**.
3. El `trace_id` del claim viaja y vuelve en la respuesta.
4. La serialización `snake_case` funciona en ambas direcciones contra el servicio real.

El test temporal se eliminó tras la ejecución y el contenedor se detuvo, para que la suite siga pasando sin `jbg-ai` levantado.

---

## 3. Verificación manual de la detección de deriva de contrato

Tarea 10.3. Se insertó una propiedad `DriftProbe` en `AiDebugInfo`, ausente del contrato congelado:

```text
Dtos_MatchCommittedOpenApiSchema(model: AiDebugInfo, schemaName: "DebugInfo") [FAIL]
Con error: 1, Superado: 5
```

La guarda muerde. Sonda retirada y suite restaurada a verde. A partir de aquí, renegociar el contrato rompe **los dos** builds, no solo el de Python.

---

## 4. Cross-check del contrato, campo por campo

Extraídos los esquemas de `ai-service/openapi.json` y comparados con los modelos .NET:

| Esquema | Propiedades del contrato | Coincidencia |
|---|---|---|
| `RetrievalRequest` | `filters`, `mode`, `pos_id?`, `query`, `top_k` | ✅ (`pos_id` omitido a propósito) |
| `RetrievalFilters` | `category?`, `exclude_product_ids`, `family_id?`, `materials` | ✅ |
| `RetrievalResult` | `debug?`, `family_id?`, `match_reasons`, `materials`, `product_id`, `score`, `sku`, `variant_label?` | ✅ |
| `RetrievalResponse` | `candidates_returned`, `effective_pos_id`, `low_confidence`, `results`, `trace_id` | ✅ |
| `DebugInfo` | `lexical_score?`, `notes`, `rerank_score?`, `vector_score?` | ✅ |

Nombres y **nulabilidad** verificados en ambos sentidos, a mano al escribir los modelos y automáticamente después.

---

## 5. Comprobaciones de disciplina y alcance

| Comprobación | Resultado |
|---|---|
| `git diff ai-eng...HEAD -- ai-service/` | **vacío** — contrato congelado intacto |
| `git diff ai-eng...HEAD -- terraform/ .github/ frontend/` | **vacío** |
| Migraciones EF Core en el diff | **ninguna** |
| Controladores nuevos | **ninguno** |
| Referencias a los otros siete endpoints | **ninguna** |
| Cabecera del requisito `Structured Logging` (delta vs spec vivo) | **idéntica** |
| Escenarios originales conservados en el delta | **los dos, literalmente** |
| `openspec validate --all --strict` | **30 passed, 0 failed** |
| Credenciales en los ficheros nuevos de configuración | **ninguna** |

---

## 6. Huecos detectados en el verify y cerrados

El verify encontró **tres escenarios declarados en la spec sin ninguna aserción automática**, todos del requisito *Gateway calls are traceable end to end*. El comportamiento estaba implementado, pero no había una sola aserción sobre eventos de log en toda la suite del change: un refactor podía haber quitado `base_url` del evento de fallo, o subido la consulta del operador a `Information`, sin que nada fallase.

El tercero era el grave: la regla de que el texto de la consulta no rebase el nivel `Debug` viene de §8.5 del diseño y es de **privacidad**. Estaba sostenida por convención, no por construcción — exactamente el patrón que este change ya había corregido dos veces (el `default` del struct y el `aud` del token).

Cerrados con `RecordingLoggerProvider` (helper nuevo en `TestHelpers`, reutilizable) y tres tests:

| Escenario de la spec | Antes | Ahora |
|---|---|---|
| `Correlation identifier travels in claim and header` | ✅ | ✅ |
| `Completed call is observable` | ❌ | ✅ `...EmitsCompletionEventWithLatencyAndCounts` |
| `Failed call records where it was pointing` | ❌ | ✅ `...EmitsFailureEventWithOutcomeAndBaseUrl` |
| `Query text stays out of production logs` | ❌ | ✅ `SearchAsync_QueryTextNeverRisesAboveDebug` |

**Cobertura de escenarios: 26/27.**

---

## 7. Tres correcciones que salieron del propio proceso de verificación

Ninguna fue preferencia; en los tres casos el código o un test contradijo el plan.

1. **`AiCallScope` pasó de `record struct` a clase sellada.** Todo struct tiene un `default` implícito, es decir un ámbito con punto de venta vacío: justo el estado que la fábrica existe para impedir, y una contradicción del requisito «no debe existir ninguna vía de construcción sin punto de venta». Anclado con `AiCallScope_ExposesNoPublicConstructor`.

2. **La validación de `BaseUrl` era insuficiente.** `Uri.TryCreate("localhost:8001", UriKind.Absolute, out _)` **devuelve true**: interpreta `localhost` como esquema. Es la errata típica en configuración de producción, y la validación original la habría aceptado. Ahora se exige esquema `http` o `https`, y lo cubre `AddAiGateway_WhenBaseUrlIsNotAbsolute_FailsOnStart`.

3. **La trampa de Serilog era más profunda de lo documentado.** La forma con clave resuelve la fusión de arrays por índice, pero la configuración de .NET fusiona **por clave hoja**, así que los `Args` del fichero base sobrevivían al override: el sink recibía `outputTemplate` **y** `formatter`, sin sobrecarga que acepte ambos. **Producción habría escrito texto pareciendo bien configurada.** Descubierto porque `ProductionProfile_LeavesNoTextRenderingBehind` falló, no leyendo el código. Solución: el fichero base declara el sink sin argumentos y cada entorno aporta los suyos.

---

## 8. Hallazgos de configuración que bloquearon el commit

**`appsettings.Development.json` y `appsettings.Production.json` estaban en `.gitignore`**, bajo la sección «Secrets and sensitive files». Detectado al preparar el commit, no después. Tres consecuencias, todas verificadas:

- El perfil de producción nunca habría llegado al repo ni a `Dockerfile.bundled`: producción habría corrido con el sink base sin argumentos, en texto.
- `SerilogEnvironmentProfileTests` pasaba **solo en esta máquina**; en un clon limpio o en CI habría fallado. Verde por la razón equivocada.
- En un clon limpio se habría perdido además la plantilla de consola actual.

La primera propuesta fue una excepción acotada en el `.gitignore`, **descartada por incoherente**: ignorar algo para exceptuarlo acto seguido no es una regla, es una contradicción. La corrección adoptada separa configuración de secretos:

- `appsettings*.json` son **configuración** y se versionan — como ya hacía el `appsettings.json` con sus marcadores de desarrollo (`Password=password`, `Jwt:SecretKey`).
- `appsettings*.Local.json` quedan ignorados como vía de override personal.
- Los secretos reales viven en **user-secrets** en local y en **SSM** en producción, nunca en el árbol de trabajo.

Comprobado tras el cambio: los dos ficheros ya no se ignoran, los `*.Local.json` sí, y `secrets.json`, `*.secrets.json` y `*.pem` siguen ignorados. Ningún `appsettings` preexistente de otro proyecto pasa a rastrearse — solo existen tres en todo el repo.

---

## 9. Lo que **no** se ha comprobado

- **Producción.** El despliegue es C17. La dirección `http://jbg-ai:8000` presupone una red Docker de usuario que hoy no existe: el despliegue arranca los contenedores en la red *bridge* por defecto, donde no hay resolución por nombre. Queda como prerrequisito nombrado sobre C17, con los dos parámetros SSM.
- **Render JSON en un proceso arrancado con perfil de producción.** Se verificó la **configuración** que lo produce, no la salida de un arranque real: el arranque ejecuta migraciones de EF Core y exige base de datos.
- **Tests de integración con Testcontainers.** No se ejecutaron; el change no toca controladores ni base de datos. `ValidateOnStart` sí afecta al arranque de `WebApplicationFactory`, y la sección `AiGateway` está presente en `appsettings.json`, pero la suite de integración completa queda para el verify de C15.
- **Carga y latencia reales.** El objetivo p95 < 500 ms del diseño no se mide aquí; los stubs responden en microsegundos.
- **`ai-service`.** Intacto por diseño; su suite no se ha reejecutado porque no se ha tocado.

---

## 10. Riesgos vivos tras la verificación

| Riesgo | Estado |
|---|---|
| La dirección de producción no resuelve por falta de red de usuario | **Abierto**, documentado como prerrequisito de C17 |
| `ValidateOnStart` no detecta una `BaseUrl` presente pero obsoleta | **Mitigado parcialmente**: `base_url` viaja en el evento de fallo. Mitigación definitiva en el `/health` enriquecido de C17 |
| Token administrativo sin punto de venta | **Aplazado con dueño**: primer change entre C08 y C13 |
| `backend/docker-compose.prod.yml` presenta un despliegue obsoleto como el de producción | **Abierto**, deuda documentada para C17, incluida la corrección del README |
| Los 10 fallos preexistentes de la suite | **Fuera de alcance**, verificados como anteriores a este change |

---

## Veredicto

**Sin problemas críticos.** 305 tests aprobados, cero regresión frente al baseline, 26 de 27 escenarios con cobertura automática y el restante (`Contract drift breaks the build`) verificado a mano con evidencia registrada. El único punto abierto de `tasks.md` es 11.5, deliberado: nada en `Documentos/` quedó desactualizado —`modelo-c4.md:652` ya describe este componente— y solo falta marcar HU-AIENG-003 como hecha en `epicas.md`, que corresponde al archivado.

**Listo para archivar.**
