# HU-AIENG-003: Cliente tipado .NET hacia `jbg-ai` con resiliencia y token de servicio

## Formato estándar

Como **desarrollador del proyecto**, quiero **un cliente .NET tipado (`IAiGatewayClient`) que hable con `jbg-ai` firmando el JWT interno, propagando el `trace_id` y degradando con timeout, reintento único y circuit breaker** **para** **que el endpoint de búsqueda asistida (C15) se construya sobre una integración probada, y para que un fallo del servicio de IA nunca tumbe el punto de venta**.

---

## Descripción

Tercera y última pieza de la Ola 0 del Proyecto Final de IA (change OpenSpec `add-dotnet-ai-gateway-client` / C03). Sobre el contrato congelado en [HU-AIENG-002](HU-AIENG-002.md), construye el **primer consumidor** de ese contrato: un cliente tipado en el backend .NET que llama a `POST /v1/retrieval/products` contra los stubs deterministas de C02.

El valor no es de usuario final —esta historia no entrega pantalla— sino de **desbloqueo y de disciplina de integración**. Verificado en el repositorio: el backend .NET **no tiene hoy ningún cliente HTTP saliente**, ni Polly, ni `Microsoft.Extensions.Http`. Todo lo que se decida aquí (dónde vive el cliente, cómo se firma el token, cómo se traducen los errores, cómo se traza la llamada) lo heredan literalmente C12 (feeds de indexación), C15 (endpoint de búsqueda) y C34 (venta asistida).

La regla de frontera que se materializa es la del diseño v3 §6.2: *Python calcula parecidos y redacta; .NET calcula números y decide*. Y la de §6.4: **el sistema nunca se cae por culpa de la IA**.

**Alcance de esta historia (sí):**

- `IAiGatewayClient` + `AiGatewayClient` (typed `HttpClient`) en `JoiabagurPV.Application`, con **un único método**: `SearchAsync` contra `POST /v1/retrieval/products`.
- DTOs .NET espejo del contrato congelado, con serialización `snake_case` y nulabilidad real en `family_id` y `variant_label`.
- `AiCallScope`: tipo que transporta `user_id`, `role` y `pos_id`, con **una única fábrica** `ForPointOfSale(...)`.
- Emisión y firma del JWT interno HS256 con los cuatro claims obligatorios en `snake_case`, **sin `aud` y sin `iss`**, TTL configurable y `TimeProvider` inyectado.
- Propagación del `trace_id`: en el claim del token **y** en la cabecera `X-Trace-Id`, mediante `ITraceContextAccessor` implementado en la capa API.
- Resiliencia con `Microsoft.Extensions.Http.Resilience` (Polly v8) en un *named client* propio: timeout de 0,8 s, **reintento único** y circuit breaker con umbrales explícitos.
- Mapa de errores del contrato traducido a excepciones tipadas, con la regla de qué se reintenta y qué no.
- Logging estructurado por llamada (`ai_gateway_call_started` / `_completed` / `_failed`) y salida JSON bajo perfil de producción.
- Fail-fast de configuración al arrancar: sin `BaseUrl` absoluta o sin `JwtSecret`, la API no arranca.
- Tests unitarios con `HttpMessageHandler` falso —sin red y sin `jbg-ai` levantado— más un test de contrato contra `ai-service/openapi.json`.

**Fuera de alcance (no):**

- `AiController`, `POST /api/ai/search`, hidratación de precio y stock desde PostgreSQL, descarte de candidatos tras hidratar, fallback al buscador léxico existente y feature flag por punto de venta → **C15**.
- Los otros siete endpoints del contrato (`substitutes`, `assist/sale`, `inventory/propose`, `enrich/products`, `index/sync`, `index/status`, `evals/runs`): el cliente crece en el change que los consuma (C34, C13, C08).
- Firma de tokens **sin** punto de venta, necesaria para las rutas de catálogo global → primer change que la necesite entre C08 y C13.
- `ProductAiProfile` y entidades .NET nuevas → C08. Feeds de indexación → C12.
- Migración de EF Core: esta historia **no toca el modelo de datos**.
- Frontend: la SPA nunca habla con Python y no ve nada de este cambio.
- Despliegue, secretos en SSM y `BaseUrl` de producción → C17.

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Anchura del cliente | **Solo `SearchAsync`.** Añadir un método C# es un diff pequeño, no una negociación entre dos personas: el argumento que justificó congelar ancho el contrato de C02 no se traslada al cliente |
| Ubicación | `JoiabagurPV.Application`. Forzado por el layering: `JoiabagurPV.Infrastructure.csproj` solo referencia a `Domain`, así que implementarlo allí obligaría a meter los DTOs de IA en el dominio. Precedente: `ImageRecognitionService`, `JwtTokenService` |
| Ámbito de la llamada | `AiCallScope` con única fábrica `ForPointOfSale(userId, role, pointOfSaleId)`. No existe forma de construir un ámbito sin punto de venta real, porque a partir de C22 el `pos_id` del token será **el único filtro duro** del recuperador |
| Autorización | El cliente **no autoriza**: quien construye el ámbito ya ha validado la asignación del usuario al punto de venta contra `UserPointOfSale`. Eso es C15 |
| Token | HS256 con secreto propio (`AiGateway:JwtSecret`), distinto del de usuario. Claims literales `user_id`, `role`, `pos_id`, `trace_id`. **Sin `aud` ni `iss`**, y sin `nbf` |
| Reutilización de `JwtTokenService` | **No.** Otro secreto, otros claims, otro TTL y otro destinatario. Compartir el servicio arrastraría `aud`/`iss` al token de servicio |
| Resiliencia | `Microsoft.Extensions.Http.Resilience` con pipeline explícito. `AddStandardResilienceHandler()` por defecto (30 s totales, 3 reintentos) contradice el diseño |
| Aislamiento de circuitos | *Named client* propio para recuperación, con hueco preparado para asistencia en C34. Breakers independientes: un modelo de lenguaje lento no debe apagar la búsqueda ni disparar el fallback léxico de C15 |
| Qué se reintenta | 408 y 5xx **salvo 501**, más timeouts y fallos de transporte. **Nunca** 401 (es configuración) ni 501 (C02 eligió ese código precisamente para que el cliente no insista) |
| Forma del fallo | Excepciones tipadas con base `AiGatewayException`. Se documenta como trade-off consciente frente a un tipo resultado: C15 tiene un único punto de llamada |
| Observabilidad | `ILogger<T>` con plantillas semánticas y `BeginScope`. El texto de la consulta solo en nivel `Debug` (diseño v3 §8.5). Sin tokens ni coste: C03 no llama a ningún modelo de lenguaje. El render depende del entorno: consola legible en desarrollo, JSON en producción |
| Dónde se especifica la observabilidad | **Repartida.** Lo del salto .NET↔Python (`trace_id` en claim y cabecera, los tres eventos, la consulta en `Debug`) va en la capability nueva del cliente, porque es el contrato de correlación con `jbg-ai`. El render global amplía el requisito `Structured Logging` que **ya existe** en la capability `backend` y cuyo escenario de identificador de correlación hoy no está implementado |
| Configuración | `IOptions<AiGatewayOptions>` con `ValidateOnStart()`: la validación perezosa no sirve, porque fallaría dentro de una petición en vez de en el arranque. En desarrollo los valores viven en `appsettings.json`; en producción llegan como variables de entorno desde SSM, con `__` como separador |
| Dirección del servicio | `http://localhost:8001` en desarrollo —el backend .NET corre en el host y solo ve el puerto publicado por Compose—. En producción, **valor previsto** `http://jbg-ai:8000`, que **exige que C17 cree una red Docker de usuario**: en la red *bridge* por defecto que usa el despliegue actual, ese nombre no resuelve |

**Referencias:**
[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C03),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.2 frontera, §6.4 seguridad y degradación, §7.6 sobre-recuperación, §8.5 privacidad),
[proyecto-final-diseno-rag-joiabagur-3devs.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur-3devs.md) (§6.6 observabilidad, §6.8 latencias objetivo),
[epicas.md](../../epicas.md) (EP11),
[HU-AIENG-002.md](HU-AIENG-002.md),
specs vivas `openspec/specs/ai-service-api-contracts/spec.md` y `openspec/specs/ai-service-auth/spec.md`,
contrato congelado `ai-service/openapi.json`,
change OpenSpec `openspec/changes/add-dotnet-ai-gateway-client/` y su ticket técnico.

---

## Criterios de Aceptación

### Escenario 1: Una respuesta correcta se mapea completa
**Dado que** el servicio de IA responde HTTP 200 al contrato de recuperación  
**Cuando** se invoca `SearchAsync` con una consulta y un ámbito válidos  
**Entonces** se devuelve un objeto con `results`, `candidates_returned`, `low_confidence`, `trace_id` y `effective_pos_id`  
**Y** cada resultado expone `product_id`, `sku`, `score`, `match_reasons` y `materials` como lista  

### Escenario 2: Los campos nulos del contrato se respetan
**Dado que** el servicio devuelve un resultado con `family_id` y `variant_label` a `null`  
**Cuando** se mapea la respuesta  
**Entonces** ambas propiedades quedan nulas en el objeto .NET  
**Y** el mapeo no lanza excepción ni sustituye el nulo por un valor por defecto  

### Escenario 3: El token lleva los cuatro claims obligatorios en `snake_case`
**Dado que** existe un ámbito construido con usuario, rol y punto de venta  
**Cuando** se firma el token interno  
**Entonces** el payload contiene exactamente `user_id`, `role`, `pos_id` y `trace_id`, con esos nombres literales  
**Y** ninguno de los cuatro está vacío  

### Escenario 4: El token no declara audiencia ni emisor
**Dado que** el validador de `jbg-ai` no espera ninguna audiencia  
**Cuando** se firma el token interno  
**Entonces** el payload **no** contiene `aud` ni `iss`  
**Y** tampoco contiene `nbf`  
**Y** contiene `exp` con el vencimiento configurado  

### Escenario 5: El ámbito solo se construye con un punto de venta real
**Dado que** se intenta construir un `AiCallScope`  
**Cuando** el identificador de punto de venta está vacío o el rol es una cadena en blanco  
**Entonces** la construcción falla con un error de argumento  
**Y** no existe ninguna vía alternativa para crear un ámbito sin punto de venta  

### Escenario 6: El tiempo de espera agotado se traduce a servicio no disponible
**Dado que** el servicio de IA no responde dentro del presupuesto de 0,8 segundos  
**Cuando** se invoca `SearchAsync`  
**Entonces** se lanza la excepción de servicio no disponible  
**Y** el fallo queda registrado con el resultado `timeout` y la latencia medida  

### Escenario 7: Con el circuito abierto se falla de inmediato y sin llamar
**Dado que** el circuit breaker del cliente de recuperación está abierto  
**Cuando** se invoca `SearchAsync`  
**Entonces** se lanza la excepción de servicio no disponible sin realizar ninguna petición HTTP  
**Y** el registro indica el resultado `circuit_open`  

### Escenario 8: Una ruta todavía no implementada no se reintenta
**Dado que** el servicio responde HTTP 501 porque la lógica real llega en un change posterior  
**Cuando** se invoca `SearchAsync`  
**Entonces** se lanza la excepción de funcionalidad no implementada  
**Y** se ha realizado **una sola** petición HTTP  

### Escenario 9: Un error de autenticación no se reintenta
**Dado que** el servicio responde HTTP 401 porque el secreto compartido no coincide  
**Cuando** se invoca `SearchAsync`  
**Entonces** se lanza la excepción de error de configuración  
**Y** se ha realizado **una sola** petición HTTP  
**Y** el fallo se registra con nivel de error, señalando que es un problema de configuración  

### Escenario 10: Un error transitorio del servidor se reintenta una vez
**Dado que** el servicio responde HTTP 503 en la primera petición y HTTP 200 en la segunda  
**Cuando** se invoca `SearchAsync`  
**Entonces** se devuelve la respuesta mapeada correctamente  
**Y** se han realizado exactamente dos peticiones HTTP  

### Escenario 11: La configuración incompleta impide arrancar
**Dado que** falta `AiGateway:JwtSecret` o `AiGateway:BaseUrl` no es una URI absoluta  
**Cuando** arranca la API  
**Entonces** el arranque falla de inmediato con un mensaje que identifica la clave concreta  
**Y** no queda una API funcionando que solo falle en la primera llamada al servicio de IA  

### Escenario 12: Cada llamada deja traza estructurada correlacionable
**Dado que** se invoca `SearchAsync` con un `trace_id` conocido  
**Cuando** la llamada termina, con éxito o con fallo  
**Entonces** existen registros con ese mismo `trace_id` y el nombre del endpoint  
**Y** el registro de finalización incluye latencia, número de intentos y el desenlace  
**Y** el texto de la consulta no aparece en niveles por encima de `Debug`  

### Escenario 13: El render de los logs depende del entorno
**Dado que** la aplicación arranca con perfil de desarrollo  
**Cuando** se emite cualquiera de los eventos de la llamada  
**Entonces** la salida es la consola legible de siempre  
**Y** con perfil de producción el mismo evento se emite como JSON de una línea, ingerible por una plataforma de observabilidad  
**Y** las propiedades nombradas del evento aparecen como campos, no embebidas en una frase  

### Escenario 14: Los DTOs no pueden derivar del contrato committeado
**Dado que** `ai-service/openapi.json` está versionado en el repositorio  
**Cuando** se ejecuta el test de contrato del lado .NET  
**Entonces** cada propiedad de los DTOs de recuperación existe en el esquema con el mismo nombre y la misma nulabilidad  
**Y** si alguien renegocia el contrato sin actualizar los DTOs, el test falla  

### Escenario 15: Fuera de alcance explícito
**Dado que** esta historia está implementada  
**Cuando** se revisa el entregable  
**Entonces** no existe ningún controlador de IA ni el endpoint `POST /api/ai/search`  
**Y** no hay hidratación de precio ni de stock, ni fallback al buscador léxico, ni feature flag por punto de venta  
**Y** el cliente expone un único método, no los ocho endpoints del contrato  
**Y** no hay migración de EF Core ni cambios en el frontend  

---

## Notas adicionales

- **Actor:** historia de plataforma para el equipo del Proyecto Final. No hay pantalla; el beneficiario directo es quien implemente C15.
- **Primer cliente HTTP saliente del backend.** Verificado: no hay ningún `AddHttpClient` en `backend/src/`. El `FakeHttpMessageHandler` que se añade a `TestHelpers` es infraestructura de test que heredarán C12, C15 y C34.
- **Trampa del `aud`:** el validador de `jbg-ai` usa `PyJWT` sin parámetro `audience`. En PyJWT 2.x, un token que **sí** declara `aud` cuando el validador no espera audiencia se rechaza con 401 — y la spec `ai-service-auth` obliga a que ese 401 **no revele la causa**. Copiar el patrón de `JwtTokenService`, que sí firma con emisor y audiencia, produciría un rechazo sistemático imposible de diagnosticar desde los logs de Python. Por eso el escenario 4 es un criterio de aceptación y no un comentario.
- **Trampa de los relojes:** `PyJWT` valida `iat` y `nbf` sin margen de tolerancia. Con dos contenedores desincronizados unos segundos, un token recién emitido puede parecer del futuro. Se emiten solo los campos temporales imprescindibles.
- **Doble dirección del servicio, y la trampa que esconde:** en desarrollo el backend .NET corre en el host y alcanza `jbg-ai` en `http://localhost:8001` (el Compose mapea `8001:8000`); en producción ambos contenedores convivirán en la misma máquina y la dirección será `http://jbg-ai:8000`. Son dos valores distintos y ninguno es el intuitivo. Pero hay un segundo nivel: verificado en `terraform/templates/user_data.sh`, el despliegue actual arranca la API con `docker run` **sin `--network`**, es decir sobre la red *bridge* por defecto, donde Docker **no resuelve nombres de contenedor**. El valor de producción no es un hecho de hoy: es un **prerrequisito nombrado sobre C17** (crear una red de usuario, unir ambos contenedores y no publicar el puerto de `jbg-ai`). El ticket lo recoge en detalle.
- **Límite del fail-fast:** la validación al arrancar detecta una clave ausente o malformada, no una presente pero equivocada. Si en producción faltara la dirección, la aplicación caería al valor de desarrollo, que es una URI válida, y fallaría luego con conexión rechazada. Por eso el evento de fallo incluye `base_url`: cuando algo va mal, el log dice a dónde estaba apuntando.
- **Sobre-recuperación:** `top_k` es el tamaño de página que .NET quiere **después** de hidratar; el servicio devuelve `min(top_k × 3, 60)` candidatos. El cliente no trunca: solo transporta el número y lo expone en `candidates_returned`. Truncar es responsabilidad de C15.
- **Pregunta abierta heredada:** el contrato exige `pos_id` en las ocho rutas, pero enriquecimiento e indexación son de catálogo global. Esta historia lo deja **imposible de resolver mal por accidente** (no hay fábrica sin punto de venta) y traslada la decisión al primer change que necesite un token administrativo.
- **OpenSpec:** se implementa vía el change `add-dotnet-ai-gateway-client` (proposal → specs → design → tasks → apply → verify → archive). Los artefactos del change se generan a partir de esta HU y del ticket.

---

## Tareas

1. Añadir a `JoiabagurPV.Application` las dependencias de cliente HTTP y resiliencia, y definir `AiGatewayOptions` con validación en el arranque; añadir la sección `AiGateway` a `appsettings.json` con la dirección de desarrollo y el secreto local que coincide con el del Compose.
2. Definir los DTOs de recuperación como espejo del contrato congelado, con serialización `snake_case` centralizada y nulabilidad real en `family_id` y `variant_label`.
3. Implementar `AiCallScope` con su única fábrica y sus validaciones de argumento.
4. Implementar el emisor del token interno: HS256, cuatro claims en `snake_case`, sin audiencia ni emisor, TTL configurable y reloj inyectado.
5. Añadir `ITraceContextAccessor` en `Application` y su implementación en la capa API, siguiendo el patrón de `CurrentUserService`.
6. Implementar `AiGatewayClient` con `SearchAsync`, la cabecera de correlación y el mapa de errores del contrato traducido a excepciones tipadas.
7. Registrar el *named client* de recuperación con el pipeline de resiliencia explícito (timeout, reintento único, breaker) y dejar preparado el hueco para el cliente de asistencia de C34.
8. Añadir el logging estructurado de los tres eventos por llamada —con `base_url` en el de fallo— y el render dependiente del entorno: consola legible en desarrollo, JSON bajo perfil de producción.
9. Escribir el `FakeHttpMessageHandler` en `TestHelpers` y los tests unitarios de mapeo, token, resiliencia y modos de fallo.
10. Escribir el test de contrato del lado .NET contra `ai-service/openapi.json`, con su utilidad de localización de la raíz del repositorio.
11. Verificar `dotnet build` y `dotnet test` en verde, sin regresión en la suite existente y sin necesidad de levantar `jbg-ai`.

---

## Estimaciones y atributos de priorización

> Valores propuestos por el Product Owner a partir de la guía de estimación de [Procedimiento-TicketsTrabajo.md](../../Procedimientos/Procedimiento-TicketsTrabajo.md) (§4.6). **Pendientes de validar** en la sesión de refinamiento del equipo.

- **Puntos de historia:** **5** — superficie estrecha (un solo método) pero infraestructura enteramente nueva en el backend: primer cliente HTTP saliente, primer pipeline de resiliencia y primer emisor de token de servicio. No llega a 8 porque no hay lógica de negocio, ni base de datos, ni modelo de datos que tocar.
- **Impacto en usuario / Valor de negocio:** **2** — nulo de forma directa (no hay pantalla). El valor aparece en C15, que es el que convierte esta integración en búsqueda visible.
- **Urgencia (mercado / feedback):** **5** — Ola 0, ruta crítica 🔴. Bloquea C15 y, a través de él, C16 y C17: el hito de tener el sistema desplegado y usable el 19 de agosto depende de esta pieza.
- **Complejidad / Esfuerzo:** **4** — la dificultad no está en el algoritmo sino en los modos de fallo y en las trampas silenciosas del token: un campo de más en el JWT o un predicado de reintento demasiado genérico producen fallos que los logs de Python, por diseño, no explican.
- **Riesgos y dependencias:**
  - Depende de HU-AIENG-002 / C02 (contrato congelado y autenticación) — **hecho y archivado**.
  - Desbloquea C15 (endpoint de búsqueda en .NET) y, en cascada, C16, C17 y C34.
  - **Riesgo:** el 401 opaco por audiencia, emisor o desfase de reloj consume horas de diagnóstico → mitigado con los escenarios 4 y 11 como criterios de aceptación y con el fail-fast de configuración.
  - **Riesgo:** un predicado de reintento genérico ("reintentar cualquier 5xx") rompe la decisión de C02 sobre el 501 → mitigado con el escenario 8.
  - **Riesgo:** el test del circuit breaker aprueba sin que el circuito llegue a abrirse, porque la librería exige una ventana de muestreo y un mínimo de llamadas → mitigado configurando umbrales bajos explícitos en el pipeline de test o forzando el estado.
  - **Riesgo:** deriva silenciosa del contrato, que hoy rompe el build de Python pero dejaría el de .NET en verde → mitigado con el test de contrato del escenario 13.
  - **Riesgo:** compartir circuit breaker entre recuperación y asistencia haría que un modelo de lenguaje lento apagase la búsqueda → mitigado con clientes con nombre separados desde el principio.
  - **Dependencia hacia adelante:** la dirección de producción presupone una red Docker de usuario que **hoy no existe** —el despliegue arranca los contenedores en la red *bridge* por defecto, donde no hay resolución por nombre—. Queda como prerrequisito nombrado sobre C17, junto con los dos parámetros SSM. C03 no toca infraestructura, pero si C17 lo pasa por alto, la integración funcionará en desarrollo y fallará en producción con conexión rechazada.
  - No depende del export del catálogo real, ni del esquema `ai`, ni de la elección de proveedor de modelos.
