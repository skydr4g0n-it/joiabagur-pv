## 1. Líneas base y prerrequisitos

- [x] 1.1 Medir la línea base de la suite de backend con el árbol limpio (`git stash push -u`, ejecutar, `git stash pop`) y **anotar los nombres** de los tests en rojo, no el recuento
- [x] 1.2 Medir la línea base de la suite de frontend igual, leyendo la **línea de resumen** y no el código de salida — `vitest` sale con 0 si se canaliza su salida
- [x] 1.3 Medir la línea base de `uv run pytest` en `ai-service/` y confirmar que `test_openapi_snapshot_is_stable` está en verde antes de tocar nada
- [x] 1.4 Confirmar el alta de la cuenta AWS de demostración y disponer de credenciales de administración *(prerrequisito externo: bloquea el grupo 8 en adelante, no la escritura de código ni de tests)*
- [x] 1.5 Verificar el volcado local de partida: recuento de productos, colecciones, puntos de venta, inventario, perfiles aprobados y documentos indexados, y **el modelo de embeddings que consta en el índice**

## 2. Contexto de construcción e imágenes

- [x] 2.1 Crear `.dockerignore` en la raíz excluyendo `node_modules`, entornos virtuales, `.git`, `data/`, artefactos de compilación y ficheros de entorno
- [x] 2.2 Verificar la reducción del contexto de construcción midiendo antes y después
- [x] 2.3 Crear `backend/src/JoiabagurPV.API/Dockerfile.demo` a partir del de producción, con `VITE_API_BASE_URL` por defecto a `/api`, y cabecera que declare que `Dockerfile.bundled` es el de producción y **no se toca**
- [x] 2.4 Endurecer `ai-service/Dockerfile`: construcción multietapa, usuario sin privilegios, **versión fijada** del instalador `uv` en lugar de `:latest`, y `HEALTHCHECK` que use el intérprete ya presente sin instalar `curl`
- [x] 2.5 Comprobar que ambas imágenes construyen y que el servicio de IA arranca como usuario no-root
- [x] 2.6 Añadir cabecera de deprecado a `backend/src/JoiabagurPV.API/Dockerfile`, `Dockerfile.prod` y `backend/docker-compose.prod.yml`, siguiendo el formato de los workflows ya deprecados
- [x] 2.7 Corregir `backend/README.md`, que presenta el camino de despliegue obsoleto bajo «Production Deployment › Docker» *(deuda asignada a C17 en el ticket de C03)*

## 3. Composición del entorno

- [x] 3.1 Crear `compose.demo.yaml` en la raíz con nombre de proyecto `jbg-demo` y cabecera que declare que **producción no usa composición** y que el fichero de desarrollo local es otro
- [x] 3.2 Declarar `jbg-demo-postgres` con la imagen de pgvector, volumen `jbg-demo-pgdata` y comprobación de salud con `pg_isready`
- [x] 3.3 Declarar `jbg-demo-ai` sin `ports:`, con `mem_limit` explícito —**no `deploy.resources`**, que se ignora fuera de swarm—, `environment:` explícito **nunca `env_file:`**, y dependencia del estado sano de la base
- [x] 3.4 Declarar `jbg-demo-api` sin `ports:`, con dependencia del estado sano de la base
- [x] 3.5 Declarar `jbg-demo-proxy` (Caddy) como **único servicio con `ports:`** (80 y 443), con volúmenes `jbg-demo-caddy-data` y `jbg-demo-caddy-config`
- [x] 3.6 Declarar la red `jbg-demo-net` y los tres volúmenes con nombre explícito
- [x] 3.7 Fijar como **literales versionados** el modelo de embeddings (`openai/text-embedding-3-small`), el umbral de distancia (0,65) y `STUB_MODE=false`, con comentario que explique por qué no van al almacén de parámetros
- [x] 3.8 Declarar las variables de clase A como `${VAR}`, con comentario que nombre el parámetro de origen de cada una
- [x] 3.9 Crear `deploy/demo/Caddyfile` parametrizado por `${DEMO_HOSTNAME}`, con redirección automática y proxy inverso al servicio de API
- [x] 3.10 Validar la composición con `docker compose -f compose.demo.yaml config` y comprobar que **sólo el proxy declara puertos publicados**

## 4. Script de despliegue

- [x] 4.1 Crear `deploy/demo/deploy.sh` con `set -euo pipefail` y **sin `set -x`** en el tramo que lee secretos, con comentario que explique que la salida del comando remoto se archiva
- [x] 4.2 Leer los parámetros del almacén y **exportarlos al entorno del proceso**, sin escribir ningún fichero
- [x] 4.3 Leer **una sola vez** el secreto del token interno y la credencial del feed, e inyectar cada uno en los **dos** servicios que deben compartirlo
- [x] 4.4 Validar cada variable requerida con `: "${VAR:?}"` para que una vacía falle de forma ruidosa
- [x] 4.5 Ejecutar `docker compose ... up -d` y **jamás** `down -v`, con comentario que cite el límite semanal de certificados duplicados
- [x] 4.6 Ejecutar `alembic upgrade head` desde el contenedor del servicio de IA
- [x] 4.7 Añadir la llamada de calentamiento que absorbe el arranque en frío del cliente de embeddings
- [x] 4.8 Crear `deploy/demo/README.md` como runbook: alta de cuenta, aprovisionamiento del esquema, volcado y restauración, cuentas de demostración, y migración del nombre de anfitrión al dominio propio

## 5. Infraestructura

- [x] 5.1 Crear `terraform/demo/` con backend de **estado propio**, separado del de producción
- [x] 5.2 Declarar el proveedor OIDC como `resource` (cuenta virgen) con **comentario que documente que es singleton por cuenta y emisor**, y que en una cuenta que ya lo tenga hay que usar `data` o el apply falla con `EntityAlreadyExists`
- [x] 5.3 Declarar el rol de despliegue con confianza acotada a `repo:<org>/<repo>:environment:demo`, más estricta que el `:*` de producción
- [x] 5.4 Declarar la política del rol con permisos sobre **los repositorios ECR de la demo** y la instancia de la demo, y nada más
- [x] 5.5 Declarar los dos repositorios ECR (`jbg-demo-api`, `jbg-demo-ai`) **cada uno con su política de ciclo de vida**
- [x] 5.6 Declarar el grupo de seguridad `jbg-demo-sg` con entrada **sólo** en 80 y 443
- [x] 5.7 Declarar la instancia `jbg-demo-host`, su perfil de instancia con lectura de `/jbg-demo/*` y descarga de imágenes, y la IP elástica
- [x] 5.8 Resolver la AMI con `data "aws_ssm_parameter"` del alias público de AL2023, eliminando la variable manual, y anotar el supuesto sobre la VPC por defecto
- [x] 5.9 Crear `terraform/demo/templates/user_data.sh` con **cuatro pasos y nada específico de la aplicación**, instalando el plugin de Compose desde una release con **versión fijada**
- [x] 5.10 Ejecutar el plan y **verificar que no aparece ningún recurso ajeno al módulo**

## 6. Salud enriquecida del servicio de IA

- [x] 6.1 Implementar las sondas de base de datos, índice y credencial del proveedor, **sin llamar al proveedor** en ningún camino
- [x] 6.2 Implementar el contraste del modelo configurado contra el `DISTINCT embedding_model` del índice, con estado de discrepancia que nombre ambos modelos
- [x] 6.3 Cachear el resultado en una ventana corta, para no consumir el pool de cinco conexiones con sondas repetidas
- [x] 6.4 Enriquecer el `/health` existente **conservando el retorno `dict[str, Any]`**: sin modelo Pydantic y sin ruta nueva
- [x] 6.5 Tratar el índice vacío como recuento cero, **no** como discrepancia de modelo
- [x] 6.6 `test_health_reports_database_index_and_provider`
- [x] 6.7 `test_health_reports_model_mismatch_when_index_disagrees`
- [x] 6.8 `test_health_never_calls_the_embedding_provider`
- [x] 6.9 `test_health_result_is_cached_between_probes`
- [x] 6.10 `test_health_degrades_when_database_is_unreachable`
- [x] 6.11 Confirmar que **`test_openapi_snapshot_is_stable` sigue en verde** y que `openapi.json` no ha cambiado

## 7. Estado del servicio en el backend y en el panel

- [x] 7.1 Añadir el objeto de transferencia de la respuesta de salud en `Application/DTOs/Ai/`
- [x] 7.2 Añadir `HealthAsync` a `IAiGatewayClient` y su implementación, con **cliente HTTP con nombre propio y sin el disyuntor**, con tiempo de espera corto
- [x] 7.3 Crear `AiHealthController` en `api/ai/health`, `[Authorize(Roles = "Administrator")]`, siguiendo el patrón de un controlador por capacidad
- [x] 7.4 Garantizar que la respuesta **no expone** cadena de conexión, nombre de anfitrión de la base ni fragmento alguno de credencial
- [x] 7.5 `AiHealth_ReturnsUnauthorized_ForAnonymousRequest` *(pedir un cliente nuevo a la factoría: el compartido conserva las cookies de cada login)*
- [x] 7.6 `AiHealth_ReturnsForbidden_ForOperatorRole`
- [x] 7.7 `AiHealth_BypassesCircuitBreaker_WhenGatewayCircuitIsOpen`
- [x] 7.8 `AiHealth_DoesNotLeakConnectionStringOrApiKey`
- [x] 7.9 Añadir el servicio y los tipos del frontend para la tarjeta
- [x] 7.10 Añadir la tarjeta de estado a `AdminDashboard.tsx` con componentes Metronic existentes (`card`, `badge`, `alert`, `skeleton`, `separator`), sin componentes nuevos
- [x] 7.11 Presentar la discrepancia de modelo **como error y en texto**, no sólo por color, y el servicio inalcanzable sin tumbar el resto del panel
- [x] 7.12 `should show ai service status card when user is administrator`
- [x] 7.13 `should not show ai service status card when user is operator`
- [x] 7.14 `should render model mismatch as an error state`
- [x] 7.15 Declarar los manejadores de red explícitamente o mockear el servicio con `vi.mock` — el simulador corre en modo aviso y un test sin manejador **pasa sin probar nada**

## 8. Despliegue

- [x] 8.1 Crear `.github/workflows/deploy-demo.yml` con `on: push: branches: [demo]` más `workflow_dispatch`
- [x] 8.2 Configurar credenciales por OIDC contra el rol de la demo y publicar las dos imágenes con etiqueta de commit
- [x] 8.3 Construir la imagen de API con `--build-arg VITE_API_BASE_URL=/api`
- [x] 8.4 Desplegar con `aws ssm send-command` invocando el script, con sondeo del resultado
- [x] 8.5 Implementar la verificación posterior **desde dentro del anfitrión** por `docker exec`, exigiendo base accesible, **recuento de documentos mayor que cero**, ausencia de discrepancia de modelo y credencial configurada
- [x] 8.6 Validar el workflow con `workflow_dispatch` **antes** de empujar nada a la rama `demo`
- [x] 8.7 Crear la rama `demo` y el GitHub Environment homónimo

## 9. Camino del dato

- [x] 9.1 Ejecutar el aprovisionamiento del esquema (`bootstrap.sql`) contra la base de la demo, con privilegios de administrador
- [x] 9.2 Volcar `public` y `ai` desde el entorno local
- [x] 9.3 **Sustituir el personal real de la joyería** por una cuenta de administración y una de operación de demostración, y verificar que ninguna cuenta del personal puede autenticarse
- [x] 9.4 Restaurar ambos esquemas y verificar recuentos frente a los medidos en 1.5
- [x] 9.5 Ejecutar **una** sincronización de reconciliación y verificar `drift_count = 0` en el estado del índice
- [x] 9.6 Verificar de extremo a extremo: iniciar sesión con la cuenta de operación, buscar en lenguaje natural y confirmar que la insignia declara **origen asistido** y no camino degradado

## 10. Cierre

- [x] 10.1 **Medir el presupuesto de recuperación real en la demo** y anotarlo en `DEFERRED_TASKS.md` — sin revertirlo: el arreglo pertenece a los changes que trabajan en `retrieval/`
- [x] 10.2 Anotar en `DEFERRED_TASKS.md` los tres disparadores de la bifurcación del `/health` en vida y disponibilidad
- [x] 10.3 Medir el consumo de memoria con `docker stats` y confirmar o corregir el dimensionado de la instancia y el límite del contenedor de IA
- [x] 10.4 Comparar ambas suites contra las líneas base de 1.1 y 1.2 **por nombres de test**, y registrar el resultado en `qa.md`
- [x] 10.5 `dotnet build`, `npm run build` y `uv run pytest` sin errores
- [x] 10.6 Enlazar HU-AIENG-017 en `Documentos/epicas.md` (EP11)
- [x] 10.7 `openspec validate --all --strict` en `0 failed` — no basta la forma de un solo change
