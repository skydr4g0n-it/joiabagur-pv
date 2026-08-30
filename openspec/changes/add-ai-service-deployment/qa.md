# QA — C17 `add-ai-service-deployment`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-29 · **Rama:** `c17-add-ai-service-deployment` · **Commit de artefactos:** `00cc529`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| SDK | .NET 10 (`net10.0`), solución `backend/src/JoiabagurPV.sln` |
| Frontend | Vite + Vitest + RTL |
| `ai-service` | Python 3.11, `uv 0.11.7`, pytest 9 |
| Docker | 29.7.2, Docker Desktop |
| Terraform | 1.15.4 |
| **Cuenta AWS de demostración** | **No dada de alta.** Prerrequisito externo (tarea 1.4). Bloquea 5.10, 8.6, 8.7, 9.\*, 10.1 y 10.3 — **no** el código, ni las pruebas, ni la construcción de imágenes |
| Contrato | `ai-service/openapi.json` — **sin cambios**, verificado por `git diff` vacío y por su prueba de deriva |

---

## 1. Líneas base, medidas con el árbol limpio

`CLAUDE.md` avisa de que en este repositorio el recuento de rojos **no** es señal de regresión, y de que la comparación se hace por **nombres de test**. Las tres líneas base se midieron con el árbol ya limpio, antes de tocar nada.

| Suite | Comando | Línea base |
|---|---|---|
| Backend | `dotnet test` en `backend/src` | **53 fallos, 837 verdes, 890 totales** — nombres guardados |
| Frontend | `npm run test -- --run` | **116 fallos, 413 verdes, 529 totales**, 15 ficheros en rojo de 44 — nombres guardados |
| `ai-service` | `uv run pytest -q` | **0 fallos, 306 verdes, 41 omitidos** |

> La primera invocación de la suite de backend falló con `MSBUILD : error MSB1003`: la solución no está en `backend/` sino en `backend/src/`. Anotado porque es el primer tropiezo de cualquiera que siga el README.

---

## 2. Comparación de cierre, por nombres

### 2.1. Backend

| Ejecución | Resultado |
|---|---|
| Línea base | 53 fallos / 837 verdes / **890** |
| Cierre | **54 fallos / 843 verdes / 897** |

Los 7 tests de más son los 7 nuevos de C17, **los 7 en verde** (comprobado también con filtro: `AiGatewayHealthTests` + `AiHealthControllerTests` → *7 superados, 0 con error*).

La diferencia de nombres no es un subconjunto limpio, así que **no basta con mirarla**: 10 nombres aparecen y 9 desaparecen, todos dentro de `InventoryIntegrationTests` salvo tres (`ReturnsControllerTests.GetEligibleSales_WithValidProductAndPOS_ReturnsEligibleSales`, `ProductsControllerTests.Update_WithValidData_ShouldReturnUpdatedProduct`, `SalesControllerTests.CreateSale_OperatorNotAssignedToPOS_ReturnsBadRequest`).

**Se comprobó que ese vaivén es inherente, no de C17.** Ejecutando en aislamiento las dos clases que más se mueven, sobre el mismo árbol y sin recompilar:

```
dotnet test --no-build --filter "FullyQualifiedName~InventoryIntegrationTests|FullyQualifiedName~ReturnsControllerTests"
→ 14 con error, 31 superados, 45 totales
```

Ese conjunto de 14 **no coincide ni con la línea base ni con la pasada de cierre**: incluye nombres que no fallaron en ninguna de las dos (`GetStock_WithNonExistentPOS_ShouldReturnEmpty`, `Admin_AccessAllPOS_ShouldSucceed`, `ExcelImport_DownloadTemplate_ShouldSucceed`…). Es decir, **tres ejecuciones del mismo código dan tres conjuntos distintos**, que es exactamente la dependencia de orden que `CLAUDE.md` documenta para esta suite.

Ninguna de las clases que se mueven es tocada por C17: el change no entra en inventario, devoluciones, productos ni ventas. Lo que sí toca —`AiGatewayClient`, `AiGatewayOptions`, el registro del gateway, `IAiGatewayClient`, `AiHealthController` y `AiGatewayTestHost`— está cubierto por los 7 tests nuevos, todos verdes.

> Efecto colateral honesto: la clase de integración nueva entra en la misma colección compartida, que reinicia la base entre clases. Añadir una clase cambia el orden y los tiempos, y por tanto **cuáles** de los tests dependientes del orden caen. No cambia que caigan.

### 2.2. Frontend

| Ejecución | Resultado |
|---|---|
| Línea base | 116 fallos / 413 verdes / 529, 15 ficheros de 44 |
| Cierre | **113 fallos / 420 verdes / 533**, 14 ficheros de 45 |

**Diferencia por nombres: ningún fallo nuevo.** El conjunto de cierre es un **subconjunto estricto** del de partida; los tres que dejaron de fallar son los conocidos por ser dependientes del orden:

```
src/pages/sales/__tests__/assisted.test.tsx > should clear the results when the point of sale changes
src/pages/sales/__tests__/assisted.test.tsx > should ignore a stale response when the point of sale changed
src/pages/sales/__tests__/assisted.test.tsx > should skip the selection report when no search event id was returned
```

Los cuatro tests de más (529 → 533) son los del fichero nuevo `src/pages/dashboard/ai-service-status.test.tsx`, los cuatro en verde.

> `vitest` sale con **0** cuando se canaliza su salida, así que el veredicto se leyó en la **línea de resumen**, nunca en el código de salida.

### 2.3. `ai-service`

| Ejecución | Resultado |
|---|---|
| Línea base (Docker parado) | 306 verdes, **41 omitidos**, 0 fallos |
| Cierre, `-m "not db"` | **316 verdes, 41 deseleccionados, 0 fallos** |
| Cierre, suite completa con Docker levantado | 355 verdes, **2 fallos** |

316 = 306 de la línea base **+ 10 tests nuevos** de `tests/api/test_health_report.py`. Con el mismo conjunto que la línea base midió, **el resultado es idéntico y en verde**.

**Los 2 fallos de la pasada completa no son de C17**, y se comprobó en lugar de suponerse:

```
tests/retrieval/test_orchestrator.py::test_malformed_exclusions_are_ignored
tests/retrieval/test_orchestrator.py::test_trace_id_appears_in_stage_logs
```

| Comprobación | Resultado |
|---|---|
| `pytest tests/retrieval/test_orchestrator.py` (solo) | **13 verdes** |
| `pytest tests/api tests/retrieval` **con** el fichero nuevo | **129 verdes**, 0 fallos |
| `pytest tests/api tests/retrieval` **sin** el fichero nuevo | 119 verdes, 0 fallos |
| `pytest tests/migrations tests/retrieval/test_orchestrator.py` | **2 fallos** |
| Lo mismo **con `git stash push -u`**, árbol limpio | **los mismos 2 fallos** |

Es una dependencia de orden preexistente: ambos tests leen registros con `caplog`, y las pruebas de migraciones —que sólo se ejecutan cuando Docker está levantado, y por eso estaban omitidas en la línea base— dejan la configuración global de `logging` en un estado en el que no se captura nada. La línea base no los vio porque midió con Docker parado. `git stash pop` restauró el árbol sin incidencias.

---

## 3. Comprobaciones de construcción (tarea 10.5)

| Comprobación | Resultado |
|---|---|
| `dotnet build JoiabagurPV.sln` | **0 errores** (avisos `NU1902/NU1903` y `ASPDEPR005` preexistentes) |
| `npm run build` | **✓ built in 25.50s** |
| `uv run pytest` | verde con el alcance de la línea base — ver §2.3 |
| `openspec validate --all --strict` | **45 passed, 0 failed** |
| `terraform fmt -check -diff` en `terraform/demo` | sin diferencias |
| `terraform init -backend=false` | inicializado, `aws ~> 5.0` resuelto a 5.100.0 |
| `terraform validate` | **no ejecutable en esta máquina**: el plugin del proveedor muere al pedirle el esquema (`Plugin did not respond`), también fuera del sandbox. No es del módulo — no hay HCL que validar más allá de lo que `fmt` ya parsea. El plan real es la tarea 5.10, bloqueada por la cuenta |

---

## 4. Contexto de construcción (tareas 2.1–2.2)

Medido con una imagen sonda (`FROM scratch` + `COPY . /ctx`) y `--progress=plain`, leyendo la línea `transferring context`:

| Estado | Contexto |
|---|---|
| **Antes**, sin `.dockerignore` | **1,18 GB**, 267 s de transferencia |
| **Después** | **47 MB** de árbol restante (`du` con las exclusiones aplicadas) — **~96 % menos** |

Reparto de lo excluido, medido con `du -sh`: `frontend/node_modules` 711 MB · `ai-service/.venv` 265 MB · `bin/` + `obj/` ~145 MB · `.git` 36 MB · `data/` 30 MB.

> La segunda medición con Docker no es comparable: BuildKit cachea el contexto local por contenido, así que tras la pasada de 1,18 GB una nueva sólo transfiere lo que cambió (152 kB). Por eso el «después» se midió con `du` y no con la sonda.

**Hallazgo que estuvo a punto de dejar la tarea en nada:** `.gitignore` ignoraba `.dockerignore` en su bloque *Docker*. Los dos ficheros nuevos no se habrían versionado y cada build habría corrido con las exclusiones que tuviera la máquina de turno. Corregido, con el porqué escrito en el propio `.gitignore`.

---

## 5. Imágenes (tareas 2.4–2.5)

| Comprobación | Resultado |
|---|---|
| `docker build -f ai-service/Dockerfile … ai-service` | **construye** (multietapa, `uv` fijado a `0.11.7`) |
| Usuario del proceso | `uid=999(appuser) gid=999(appuser)` — **no root** |
| `GET /health` en el contenedor | `{"status":"OK","version":"0.1.0","database":"not_configured","index":{"documents":0,"model":null,"configured_model":"openai/text-embedding-3-small","status":"unavailable"},"provider":"missing"}` |
| `alembic --version` dentro de la imagen | `alembic 1.19.1` — el despliegue puede migrar desde el contenedor |
| `docker build -f backend/src/JoiabagurPV.API/Dockerfile.demo --build-arg VITE_API_BASE_URL=/api .` | **construye** |

El arranque en frío del contenedor de IA confirma además el comportamiento de §6: sin `DATABASE_URL` el estado es `not_configured` y `status` sigue siendo `OK`.

---

## 6. Salud enriquecida (tareas 6.1–6.11)

Diez tests nuevos en `ai-service/tests/api/test_health_report.py`, todos verdes, sin base de datos, sin proveedor y sin red:

| Test | Qué fija |
|---|---|
| `test_health_reports_database_index_and_provider` | Los tres campos nuevos, con el índice poblado |
| `test_health_reports_missing_provider_credential_without_failing` | Credencial ausente → 200 y `provider: missing` |
| `test_health_reports_model_mismatch_when_index_disagrees` | `model_mismatch`, **ambos modelos nombrados**, `status: degraded` |
| `test_health_never_calls_the_embedding_provider` | Con `forbid_network` activo: ninguna conexión sale del proceso |
| `test_health_result_is_cached_between_probes` | Dos llamadas, **una sola** sonda a la base |
| `test_health_degrades_when_database_is_unreachable` | 200 con `database: unavailable` y `status: degraded` |
| `test_health_reports_an_empty_index_as_zero_not_as_a_mismatch` | Índice vacío → recuento 0, **no** discrepancia |
| `test_health_without_a_configured_database_is_not_a_degradation` | `not_configured` con `status: OK` |
| `test_health_keeps_the_fields_earlier_changes_promised` (×2) | `status` y `version` siguen presentes |

**`test_openapi_snapshot_is_stable` sigue en verde y `git diff ai-service/openapi.json` está vacío.** El retorno del manejador sigue siendo `dict[str, Any]` y no hay ruta nueva.

### 6.1. Un estado que no estaba en la ficha: `not_configured`

Al enriquecer la sonda aparece un caso que ni el ticket ni la spec nombran: **la base de datos no configurada**. El servicio está especificado para arrancar y responder **sin** base de datos —es lo que garantiza `ai-service-dev-compose` y de lo que depende `STUB_MODE`—, así que colapsar ese caso en `unavailable` habría puesto en `degraded` toda ejecución local y toda pasada de la suite, y habría roto `test_health_returns_ok_with_version`, que estaba verde.

Se resolvió con un tercer valor, `database: not_configured`, que mantiene `status: OK`. En el entorno de demostración la variable siempre está puesta, así que **ese valor no aparece nunca allí**, y la verificación posterior al despliegue exige `ok`, no «no roto». Es la opción más estrecha que no rompe nada existente.

---

## 7. Estado del servicio en backend y panel (tareas 7.1–7.15)

### 7.1. Backend — 7 tests nuevos, todos verdes

| Test | Zona |
|---|---|
| `AiHealth_ReturnsUnauthorized_ForAnonymousRequest` | `IntegrationTests/AiHealthControllerTests` |
| `AiHealth_ReturnsForbidden_ForOperatorRole` | idem |
| `AiHealth_DoesNotLeakConnectionStringOrApiKey` | idem |
| `AiHealth_BypassesCircuitBreaker_WhenGatewayCircuitIsOpen` | `UnitTests/Application/AiGatewayHealthTests` |
| `HealthAsync_MapsTheReportFromTheWireContract` | idem |
| `HealthAsync_CarriesAModelMismatchThrough` | idem |
| `HealthAsync_WhenServiceUnreachable_ThrowsWithoutRetrying` | idem |

Dos detalles que la guía del repositorio anticipa y que se aplicaron:

- El test de 401 pide **un cliente nuevo a la factoría**. El que la clase guarda ha hecho logins y conserva sus cookies: con él, la aserción de 401 pasaría como 403 y no probaría nada.
- La aserción de no-filtración se hace sobre el **cuerpo crudo**, no sobre el objeto deserializado. Una filtración llegaría como un campo que el modelo no declara, y deserializar lo descartaría en silencio.

Añadir `HealthAsync` a `IAiGatewayClient` rompió la compilación de tres dobles de test preexistentes en `AiCatalogControllerTests`. Implementados los tres, cada uno con el comportamiento que ya tenía para los otros métodos.

### 7.2. Frontend — 4 tests nuevos, todos verdes

`should show ai service status card when user is administrator` · `should not show ai service status card when user is operator` · `should render model mismatch as an error state` · `should report an unreachable ai service without breaking the rest of the dashboard`.

**Todos los servicios se mockean con `vi.mock`**, ninguno se deja al simulador de red: `src/test/setup.ts` arranca con `onUnhandledRequest: 'warn'`, así que una llamada sin manejador imprime un aviso, devuelve nada, y el test pasa **sin haber probado nada**. Mockear el módulo convierte la ausencia de llamada en un fallo.

La tarjeta se construyó con `card`, `badge`, `alert`, `skeleton` y `separator` ya existentes; no se añadió ningún componente a `components/ui/`.

---

## 8. Composición y frontera (tareas 3.1–3.10)

```
docker compose -f compose.demo.yaml config
```

Válido, y el barrido de `published:` sobre la salida devuelve **exactamente dos entradas, ambas de `jbg-demo-proxy`** (80 y 443). Ni el servicio de IA, ni la API, ni la base de datos declaran puertos publicados — que es la frontera de S15 escrita en el fichero y no en un documento.

Comprobaciones de sintaxis: `bash -n` sobre `deploy/demo/deploy.sh` y `deploy/demo/verify.sh`, y carga YAML de `compose.demo.yaml` y `.github/workflows/deploy-demo.yml`. Todo correcto.

---

## 9. Camino del dato — punto de partida verificado (tarea 1.5)

Medido contra el Postgres local, que se arrancó para la comprobación y **se dejó parado como estaba**:

| Magnitud | Valor |
|---|---|
| `Products` | **1.200** |
| `Collections` | **38** |
| `PointOfSales` | **12** |
| `Inventories` | **6.720** |
| `ProductAiProfiles` en `Approved` | **1.200** |
| `ai.product_document` | **1.200** |
| `DISTINCT embedding_model` | **`openai/text-embedding-3-small`** |

La última fila es la que más importa: coincide con el literal versionado de `compose.demo.yaml`, así que el volcado y el entorno no van a comparar dos espacios vectoriales distintos. Si no coincidiera, el `/health` lo reportaría como `model_mismatch` y la verificación posterior tumbaría el despliegue.

> `ReviewStatus = 1` es `Pending` y `2` es `Approved`. La primera consulta usó `1` y devolvió 0 perfiles; corregida, salen los 1.200.

---

## 10. Lo que NO se ha podido verificar, y por qué

Todo lo siguiente depende del **alta de la cuenta AWS de demostración** (tarea 1.4), que es un prerrequisito externo. No hay código pendiente por ninguno de estos motivos.

| Tarea | Qué falta |
|---|---|
| 5.10 | `terraform plan` real y la verificación de que no lista ningún recurso ajeno al módulo |
| 8.6 · 8.7 | Ejecutar el workflow por `workflow_dispatch` y crear la rama `demo` y su GitHub Environment |
| 9.1 – 9.6 | Aprovisionamiento, volcado, sustitución de cuentas, restauración, sincronización de reconciliación y verificación de extremo a extremo |
| 10.1 | Medir el presupuesto de recuperación **en la demo** — anotado en `DEFERRED_TASKS.md` con qué medir y cómo leerlo |
| 10.3 | `docker stats` sobre los cuatro contenedores y confirmación del dimensionado |

El punto de corte declarado en el ticket se respeta: lo entregado cubre las cuatro zonas de código y de configuración, y lo que queda es ejecución contra una cuenta que todavía no existe.
