# HU-AIENG-017: Entorno de demo desplegado y con datos, aislado de la cuenta de la tienda

## Formato estándar

Como **desarrollador del Proyecto Final**, quiero **un entorno de demo desplegado en una cuenta AWS distinta de la de la tienda, con el sistema completo en contenedores y con el corpus ya cargado**, **para** **poder entregar la URL pública con usuario demo y el vídeo que exige el §16 del diseño, sin tocar en absoluto el sistema del que depende una joyería en funcionamiento**.

---

## Descripción

Change OpenSpec `add-ai-service-deployment` / **C17**, épica **EP11 — Plataforma del Servicio de IA**. Marcado 🔴 en la ruta crítica y en la lista de *nunca se recorta*. Prerrequisito: **C15** (`POST /api/ai/search`), archivado el 2026-08-28. Con **C16**, archivado el 2026-08-29, cierra el hito de la Ola 2.

Desde C01 el sistema se ha construido entero en un portátil. El corpus, el enriquecimiento, el índice vectorial, el retriever, la hidratación autoritativa y el panel del operador funcionan —y sólo funcionan— contra el Docker local. El §16 del diseño pide como criterio de entrega **«URL pública con usuario demo y vídeo de 2-3 min»**, y hoy no existe ninguna URL que enseñar.

La ficha v3 de C17 daba por hecho que «producción» era un sitio al que este equipo puede desplegar. **No lo es.** La cuenta AWS donde vive la tienda **no es accesible**, su RDS contiene el catálogo real del negocio, y el script que despliega —`/usr/local/bin/jpv-deploy.sh`— está horneado dentro de un heredoc de [`user_data.sh`](../../../terraform/templates/user_data.sh) en una instancia viva, bajo `lifecycle { ignore_changes = [user_data] }`. Cambiar el fichero en el repositorio no propaga nada, y re-ejecutarlo sobrescribiría la configuración de nginx que certbot ya modificó, tirando HTTPS de la tienda.

De modo que C17 no despliega a producción: **levanta un entorno de demo autocontenido en otra cuenta**, sin una sola arista hacia la de la joyería.

**El hallazgo que gobierna la historia: desplegar no es el problema, el dato lo es.** C17 puede terminar en verde —`/health` OK, smoke verde, `openspec validate --all --strict` en `0 failed`— y entregar una URL pública donde «Buscar con ayuda» no encuentra nada, nunca. Los 1.200 productos, las 38 colecciones, los 12 puntos de venta, las 6.720 filas de inventario, los 1.200 `ProductAiProfile` en `Approved` y los 1.200 `ai.product_document` con sus vectores **no existen fuera de un portátil**: el plan lo dice en tres sitios —*«INSERT local […] (Docker, no RDS)»*, *«RDS/producción»* en el fuera de alcance de C06b, y el runbook de C12 *«una persona, en local (y más adelante en demo)»*—. Es la tercera vez que aparece esta firma en el proyecto —A1 en C04, B5 en C16, y ahora el índice— y las tres comparten síntoma: compila, pasa, valida, y llega vacío a la entrega. **C17 se lleva el camino del dato, y no lo deja en un runbook.**

**El segundo hallazgo: hay dos valores que, mal puestos, mienten sin dar un solo error.** `STUB_MODE` en `true` devuelve fixtures con toda la apariencia de funcionar. Y un `JPV_EMBEDDING_MODEL` distinto del que generó los vectores compara dos espacios vectoriales como si fueran uno: la búsqueda devuelve ruido, con HTTP 200 y sin traza. Ninguno de los dos es un secreto, así que **se versionan en git como literales, no en el almacén de parámetros** —el almacén es un sitio donde alguien puede cambiar un valor sin revisión de código, y estos dos exigen revisión de código y reindexado—. Y además se comprueban: `ai.product_document` guarda `embedding_model` **por fila** desde C13, de modo que el `/health` puede contrastar lo configurado contra lo indexado.

**Alcance de esta historia (sí):**

- **Módulo Terraform en directorio y estado propios** (`terraform/demo/`), en **otra cuenta AWS**: EC2 `jbg-demo-host`, grupo de seguridad con sólo 80/443 entrantes, IP elástica, dos repositorios ECR con su política de ciclo de vida, parámetros bajo `/jbg-demo/*` y **rol OIDC propio** acotado a `environment:demo`.
- **AMI resuelta con `data "aws_ssm_parameter"`** del alias público de Amazon Linux 2023, eliminando la variable `ami_id` y su paso manual.
- **`user_data` mínimo de cuatro pasos**, sin nada específico de la aplicación: instalar Docker y el plugin de Compose **con versión fijada**, arrancar Docker y el agente SSM, traer el compose y el script, ejecutarlo.
- **`compose.demo.yaml` autocontenido en la raíz** con los **cuatro** servicios: `jbg-demo-proxy` (Caddy), `jbg-demo-api` (.NET + SPA), `jbg-demo-ai` (`jbg_ai`) y `jbg-demo-postgres` (`pgvector/pgvector:pg15`), con volúmenes, red y `mem_limit` nombrados sin ambigüedad.
- **Frontera de red escrita en el fichero**: sólo el proxy declara `ports:`.
- **Workflow `deploy-demo.yml`** (OIDC + ECR + SSM) sobre la rama `demo`, más `workflow_dispatch`, con los secretos leídos de SSM **al entorno del proceso** y **nunca a disco**.
- **`Dockerfile.demo` nuevo e independiente** para API+SPA, con `VITE_API_BASE_URL=/api`, que deja la imagen **agnóstica del hostname**.
- **`ai-service/Dockerfile` endurecido**: usuario no-root, `uv` con versión fijada en lugar de `latest`, construcción multietapa y `HEALTHCHECK`.
- **`.dockerignore` en la raíz**: hoy el contexto de build son ~1 GB.
- **`/health` enriquecido en el sitio**: base de datos, índice y `provider: configured | missing`, cacheado ~10 s, **sin llamar al proveedor**, y con contraste de `embedding_model` contra el índice.
- **`AiHealthController` en `api/ai/health`**, sólo administradores y **fuera del circuit breaker**, más la **tarjeta de estado** en el dashboard de administrador.
- **Camino del dato**: volcado de `public` y de `ai` desde local, **cuentas de demo** sustituyendo al personal real, y **un** `POST /v1/index/sync` de reconciliación con `drift_count = 0`.
- **Deprecaciones**: cabecera en `Dockerfile`, `Dockerfile.prod` y `backend/docker-compose.prod.yml`, y corrección de `backend/README.md` — deuda que el ticket de C03 ya asignó a C17.

**Fuera de alcance (no):**

- **La cuenta AWS de la tienda, en su totalidad.** Ni Terraform, ni grupo de seguridad, ni IAM, ni workflow, ni `jpv-deploy.sh`, ni su RDS. **No hay acceso, y no se busca.**
- **`Dockerfile.bundled`**, que es la imagen de producción: no se toca ni se «mejora de paso».
- **`backend/docker-compose.yml` y la spec viva `ai-service-dev-compose`**, que fija su ruta y su red literalmente en dos requirements. Mover el fichero costaría un delta de spec, cinco documentos y el flujo diario de desarrollo.
- **Regenerar `ai-service/openapi.json`.** El `/health` enriquecido conserva `dict[str, Any]`, así que el contrato congelado no se mueve.
- **Bifurcar `/health` en liveness y readiness** → disparador escrito abajo y anotado en `DEFERRED_TASKS.md`.
- **Revertir los 2500 ms de `AiGateway:RetrievalTimeoutMs`** → es **C21 o C22**, que ya trabajan en `retrieval/`. C17 **mide y anota**.
- **Cualquier migración**, de EF Core o de Alembic más allá del `upgrade head` que ya existe. C17 no es 🗄️.
- Observabilidad de producción, alertas, panel de coste o A/B testing → S16 los describe; el proyecto los declara instrumentados, no medidos (§15.3).
- Adelantar trabajo de C21, C22 o C36.

**Decisiones de diseño ya acordadas** (exploración 2026-08-29, registradas en [§0 del plan](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md)):

| # | Tema | Decisión |
|---|---|---|
| 1 | Entorno | **EC2 de demo autocontenida** con Postgres+pgvector en contenedor, en **otra cuenta AWS**, con Terraform en directorio y **estado propios** |
| 2 | OIDC | Se **crea** el `aws_iam_openid_connect_provider` porque la cuenta es virgen. Es **singleton por cuenta y emisor**: en una cuenta que ya lo tenga hay que usar `data`, o el `apply` falla con `EntityAlreadyExists` |
| 3 | Ramas | Trabajo en `c17-add-ai-service-deployment`. Despliegue desde **`demo`**, con GitHub Environment homónimo y confianza OIDC acotada a `environment:demo` — **más estricta que la de producción** |
| 4 | Plugin de Compose | **Binario de la release con versión fijada**. Ni `dnf install` ni `latest` |
| 5 | `user_data` | **Cuatro pasos**, sin nada de la aplicación. AMI por `data "aws_ssm_parameter"` |
| 6 | Proxy y TLS | **Caddy en contenedor**, con `${DEMO_HOSTNAME}` parametrizado: se arranca con `sslip.io` y se migra al dominio propio cambiando un parámetro |
| 7 | Compose | **`compose.demo.yaml` autocontenido en la raíz**. `backend/docker-compose.yml` no se toca |
| 8 | Frontera | **Sólo el proxy publica puertos.** Un error de grupo de seguridad no puede exponer el servicio de IA porque no hay puerto que exponer |
| 9 | Secretos y ajustes | Cuatro clases: **A secreto** (SSM SecureString → entorno → `${VAR}`), **B entorno** (SSM String), **C comportamiento** (**git**), **D constante** (imagen) |
| 10 | Los dos que mienten | `JPV_EMBEDDING_MODEL` (`openai/text-embedding-3-small`), umbral 0,65 y `STUB_MODE=false` son **clase C**. Más el contraste contra el índice |
| 11 | Parejas de secretos | `JWT_SECRET` ↔ `AiGateway__JwtSecret` y la clave del feed salen de **un solo parámetro leído dos veces** |
| 12 | Health | **Enriquecido en el sitio, cacheado, sin llamar al proveedor.** `openapi.json` no se regenera |
| 13 | Health en .NET | `api/ai/health`, sólo admin, **fuera del circuit breaker** |
| 14 | Imágenes | `Dockerfile.demo` nuevo; `Dockerfile.bundled` intacto; `ai-service/Dockerfile` endurecido |
| 15 | Base relativa | `VITE_API_BASE_URL=/api` funciona porque la SPA es mismo origen. Imagen agnóstica del hostname |
| 16 | Deprecaciones | Cabecera en los dos Dockerfiles muertos y en `docker-compose.prod.yml`, más `backend/README.md` |
| 17 | `.dockerignore` | Nuevo en la raíz: hoy el contexto son ~1 GB |
| 18 | Memoria | `mem_limit: 512m` en el servicio de IA. **`deploy.resources` no vale** fuera de swarm |
| 19 | Camino del dato | Volcado de `public` y de `ai` + **un** `sync` de reconciliación. Los vectores viajan: no se re-facturan y son fila a fila los de las métricas |
| 20 | Usuarios | Cuentas de demo sustituyen al personal real. **Los 436 SKU reales con sus precios sí se publican** |

**Por qué la frontera se cumple sola.** S15 fija que *«el servicio IA no mira a la calle. Nunca»*, porque custodia la clave del proveedor y porque las reglas de negocio viven en el backend. Aquí se cumple por triplicado: el grupo de seguridad sólo abre 80 y 443, el proxy es el único servicio con `ports:`, y el contenedor de IA **no publica ningún puerto**. Un descuido en cualquiera de las tres capas no basta para exponerlo.

**Por qué el `/health` no llama al proveedor.** S15 avisa de que *«si dependiera de que el proveedor de LLM responda, un hipo del proveedor haría que vuestro healthcheck fallara […] un sistema que se autodestruye cada vez que el LLM tose»*, y S16 remata: *«el `/health` sigue siendo barato y tonto […] no confundáis el latido con la vigilancia»*. Los tres consumidores del latido —Docker, el smoke del despliegue y la tarjeta del administrador— quieren saber si el servicio está sirviendo, no si OpenAI está de buen humor. `provider` informa de si la clave está **configurada**, que es el fallo real que se quiere cazar: alguien olvidó un parámetro.

**Cortes que no se reabren:** la cuenta de la tienda no se toca; `Dockerfile.bundled` no se toca; `backend/docker-compose.yml` y `ai-service-dev-compose` no se tocan; el contrato C02 no se toca y `openapi.json` no se regenera; C17 no abre migración; y no se adelanta nada de C21 ni de C22.

**Referencias:**

- Change: `openspec/changes/add-ai-service-deployment/` · ticket [T-AIENG-017](../../../openspec/changes/add-ai-service-deployment/ticket.md)
- Plan: [proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) — ficha C17 y entrada §0 de 2026-08-29
- Diseño: [proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — §6.1 (topología), §6.4 (seguridad y degradación), §12 (despliegue), §15 (limitaciones), §16 (checklist de entrega)
- Specs vivas: `ai-service-runtime` · `ai-service-dev-compose` *(no se modifica)* · `ai-assisted-search` · `vector-retrieval` · `product-document-indexer` · `dashboard-analytics` · `access-control`
- Historias vecinas: [HU-AIENG-001](HU-AIENG-001.md) (esqueleto y Dockerfile) · [HU-AIENG-005](HU-AIENG-005.md) (`bootstrap.sql`, esquema `ai`) · [HU-AIENG-015](HU-AIENG-015.md) (endpoint) · [HU-AIENG-016](HU-AIENG-016.md) (panel)
- Épica: [EP11 — Plataforma del Servicio de IA](../../epicas.md)

---

## Criterios de Aceptación

### Escenario 1: El evaluador abre la URL pública y encuentra piezas describiéndolas

**Dado que** el entorno de demo está desplegado y con el corpus cargado
**Y** el evaluador dispone de las credenciales de la cuenta de demo de operador
**Cuando** abre la URL pública por HTTPS, inicia sesión y escribe *«algo azul de plata para regalar»* en el panel «Buscar con ayuda»
**Entonces** obtiene resultados con foto, SKU, nombre, precio en EUR y stock del punto de venta
**Y** la insignia de origen indica que la respuesta vino de la vía asistida, no del buscador degradado
**Y** el certificado del navegador es válido, sin pantalla de advertencia

### Escenario 2: El servicio de IA no es alcanzable desde fuera

**Dado que** el entorno está desplegado
**Cuando** se intenta alcanzar el servicio de IA desde Internet, por la IP pública y por cualquier puerto distinto de 80 y 443
**Entonces** no hay respuesta
**Y** el contenedor de IA no declara `ports:` en `compose.demo.yaml`
**Y** el único servicio con puertos publicados es el proxy
**Y** el `/health` del servicio de IA sólo responde desde dentro de la red de la demo o por `docker exec`

### Escenario 3: El administrador ve el estado del servicio de IA en su dashboard

**Dado que** un administrador ha iniciado sesión en el entorno de demo
**Cuando** abre su dashboard
**Entonces** ve una tarjeta de estado del servicio de IA con la conectividad a la base de datos, el número de documentos indexados y si la clave del proveedor está configurada
**Y** un operador que abra su dashboard **no** ve esa tarjeta
**Y** una petición directa a `api/ai/health` con un token de operador responde `403`

### Escenario 4: El latido no miente cuando el proveedor falla

**Dado que** el servicio de IA está desplegado y sano
**Cuando** el proveedor de embeddings deja de responder
**Entonces** `/health` sigue devolviendo `200` con `provider: configured`
**Y** en ningún momento realiza una llamada al proveedor
**Y** el despliegue no se marca como fallido por ese motivo
**Y** el contenedor no se reinicia por ese motivo

### Escenario 5: El modelo configurado y el índice no coinciden

**Dado que** el índice se pobló con `openai/text-embedding-3-small`
**Cuando** el servicio arranca configurado con un modelo de embeddings distinto
**Entonces** `/health` lo declara con un estado `model_mismatch`, nombrando el modelo indexado y el configurado
**Y** la tarjeta del administrador lo muestra como error
**Y** el smoke posterior al despliegue falla en lugar de dar el despliegue por bueno

### Escenario 6: Un redespliegue no destruye ni los datos ni los certificados

**Dado que** el entorno está desplegado, con el corpus cargado y el certificado emitido
**Cuando** se ejecuta el workflow de despliegue de nuevo con una imagen nueva
**Entonces** los contenedores se recrean
**Y** el volumen de datos de Postgres conserva las 1.200 filas de `ai.product_document` y el catálogo
**Y** el volumen de datos de Caddy conserva el certificado, sin volver a solicitarlo a la autoridad
**Y** el script de despliegue no ejecuta en ningún caso `down -v`

### Escenario 7: Ningún secreto llega al disco ni al historial

**Dado que** el despliegue lee parámetros `SecureString` del almacén
**Cuando** se ejecuta el script de despliegue
**Entonces** los valores viajan en el entorno del proceso y se interpolan como `${VAR}`
**Y** no se escribe ningún fichero `.env` en la instancia
**Y** la salida del comando remoto no contiene ningún valor de secreto
**Y** si una variable requerida llega vacía, el despliegue **falla de forma ruidosa** en lugar de arrancar un servicio que responderá `401` a todo

### Escenario 8: El servicio de IA se queda sin memoria y la demo sigue en pie

**Dado que** el contenedor de IA tiene un límite de memoria declarado
**Cuando** ese contenedor supera su límite y el sistema lo termina
**Entonces** se reinicia solo por su política de reinicio
**Y** el contenedor de la API y el del proxy siguen sirviendo
**Y** mientras tanto el panel degrada al buscador léxico con `aiAvailable: false`, en lugar de dejar la aplicación caída

### Escenario 9: La cuenta de la tienda no se toca

**Dado que** el módulo Terraform de la demo vive en un directorio con estado propio
**Cuando** se ejecuta el plan de Terraform de la demo
**Entonces** no aparece ningún recurso de la cuenta de la tienda, ni para crear, ni para modificar, ni para destruir
**Y** el workflow de la demo no referencia ni el rol, ni la instancia, ni los repositorios, ni los parámetros de producción
**Y** los únicos ficheros de producción que el change modifica son las cabeceras de deprecación y `backend/README.md`

### Escenario 10: Fuera de alcance explícito

**Dado que** C17 entrega el entorno de demo
**Cuando** se revisa el alcance del change
**Entonces** `ai-service/openapi.json` **no** se ha regenerado
**Y** `/health` **no** se ha bifurcado en liveness y readiness
**Y** `AiGateway:RetrievalTimeoutMs` sigue en los 2500 ms temporales de C16, medidos y anotados pero no revertidos
**Y** no existe ninguna migración nueva, ni de EF Core ni de Alembic
**Y** `Dockerfile.bundled`, `backend/docker-compose.yml` y la spec viva `ai-service-dev-compose` están sin modificar

---

## Notas adicionales

- **Actor.** El beneficiario inmediato es el equipo del Proyecto Final, que necesita algo que enseñar. El beneficiario real es el evaluador, que abre una URL y espera que funcione sin que nadie le explique nada — que es la definición de S15 de *«operable por alguien que no lo escribió»*.

- **Por qué una cuenta separada y no un segundo entorno en la de la tienda.** No hay acceso a esa cuenta, y aunque lo hubiera: su RDS es la base de datos real del negocio, con el catálogo, los puntos de venta y el personal de la joyería. Inyectar allí 764 productos sintéticos y 12 puntos de venta simulados no es una decisión técnica, es un daño. Y compartir la instancia de base de datos, aunque fuera en otra base, obligaría a editar el grupo de seguridad de producción y ataría los snapshots de las dos.

- **Por qué Postgres en contenedor y no una base gestionada.** Vuelve **irrelevante** la verificación que el plan marcaba como *tarea obligatoria fuera de código* y que nunca llegó a ejecutarse: *«verificar que RDS admite `CREATE EXTENSION vector`; si no, el plan B hay que saberlo hoy, no el 25 de agosto»*. Se adopta el plan B que el propio plan nombraba, con la **misma imagen** `pgvector/pgvector:pg15` que ya usa el compose local — así el `bootstrap.sql` de C05 y el camino de Alembic funcionan sin una sola variación. Y el dato de la demo es reproducible desde el volcado, así que las copias de seguridad gestionadas no compran nada aquí.

- **Por qué Caddy y no nginx.** Emite y renueva el certificado solo: elimina certbot, su cron, el heredoc de configuración y el paso manual posterior a la actualización del DNS. La asimetría con producción no cuesta nada, precisamente porque la demo es deliberadamente otro sistema, en otra cuenta.

- **⚠ El volumen de Caddy guarda los certificados.** Si se pierde en un redespliegue, Caddy los vuelve a pedir, y Let's Encrypt limita a **cinco certificados duplicados por semana**: dos descuidos y la demo se queda sin HTTPS hasta la semana siguiente, con la entrega el 3 de septiembre. El script usa `up -d` y **jamás `down -v`**.

- **⚠ `set -x` está prohibido** en el tramo del script que lee parámetros `SecureString`: la salida del comando remoto se conserva en el historial del almacén.

- **El dominio no bloquea nada.** El hostname es un parámetro: la demo arranca con un nombre `sslip.io` derivado de la IP elástica, que es un nombre DNS real y por tanto certificable, y se migra al dominio propio cambiando un parámetro y redesplegando. La compra del dominio es una tarea guiada aparte, con tres criterios que descartan las ofertas trampa: gestión de DNS con API, **precio de renovación igual al de alta**, y DNSSEC.

- **La imagen de la demo es agnóstica del hostname.** `VITE_API_BASE_URL=/api` funciona porque la SPA se sirve desde `wwwroot/` del **mismo contenedor** que la API, así que es mismo origen: verificado en [`api.service.ts`](../../../frontend/src/services/api.service.ts) y en [`image-url.ts`](../../../frontend/src/lib/image-url.ts), donde `getImageUrl` reduce la base a cadena vacía y devuelve rutas relativas. Producción no se beneficia porque su workflow hornea la URL absoluta, y ese workflow no se toca.

- **Los vectores viajan, no se recalculan.** El argumento no es sólo el coste: si la demo re-embebiera, sería un índice **distinto** del que describen los números del README y la tabla de ablations del §11.2, y esa diferencia es difícil de defender ante quien lea las dos cosas. El `sync` de reconciliación posterior existe para demostrar que el camino de sincronización está cableado y que `drift_count` es 0.

- **Los usuarios reales no viajan.** El volcado arrastra correos y hashes del personal de la joyería. Se sustituyen por cuentas de demo: una de administrador y una de operador, para que se vean los dos dashboards y el bloque de embudo que sólo ve el administrador. **Los 436 SKU reales con sus precios sí se publican**, decisión de negocio tomada en la sesión.

- **Cuándo se bifurca el `/health`.** Se parte en liveness y readiness cuando se cumpla **cualquiera** de estas tres, y no antes: cuando algo pueda **reiniciar el contenedor** según la respuesta —un orquestador en lugar de un único host Docker, que es lo que activa el bucle de autodestrucción de S15 y hoy no ocurre porque `--restart unless-stopped` no reinicia por `unhealthy`—; cuando la parte cara **deje de ser cacheable barata**; o cuando el servicio se despliegue a la cuenta real de la tienda. Al bifurcar, la ruta nueva **regenera `openapi.json`** y rompe `test_openapi_snapshot_is_stable`, que es lo correcto: la frontera se habrá movido.

- **El arranque en frío se calienta antes de grabar.** La primera consulta paga importación de LiteLLM más embedding frío, así que el despliegue incluye una llamada de calentamiento. Si el vídeo se graba justo después de desplegar, sin ella la primera búsqueda se verá lenta.

- **`design.md` obligatorio** en el change: veinte decisiones con alternativas defendibles y seis zonas no caben en `tasks.md`.

- **Trampa de la suite.** El baseline rojo de las dos suites está documentado en [testing-backend.md](../../testing-backend.md) y [testing-frontend.md](../../testing-frontend.md): se comparan **nombres de test**, nunca el número.

---

## Tareas

1. Completar los artefactos OpenSpec del change: `proposal`, **`design.md`**, specs delta y `tasks`.
2. **`terraform/demo/`** con estado propio: proveedor OIDC, rol acotado a `environment:demo`, EC2, grupo de seguridad, IP elástica, dos repositorios ECR con ciclo de vida, parámetros `/jbg-demo/*`, y AMI por `data "aws_ssm_parameter"`.
3. **`user_data` mínimo de cuatro pasos**, con el plugin de Compose descargado con versión fijada.
4. **`.dockerignore` en la raíz** y **`Dockerfile.demo`** para API+SPA con base relativa.
5. **Endurecer `ai-service/Dockerfile`**: no-root, `uv` con versión fijada, multietapa, `HEALTHCHECK`.
6. **`compose.demo.yaml`** con los cuatro servicios, la frontera de puertos, healthchecks, `depends_on`, `mem_limit`, volúmenes y red nombrados.
7. **`deploy/demo/`**: `Caddyfile` parametrizado y script de despliegue que lee SSM al entorno, valida con `:?` y nunca escribe a disco.
8. **`.github/workflows/deploy-demo.yml`** sobre la rama `demo` más `workflow_dispatch`, con smoke por `aws ssm send-command` + `docker exec`.
9. **`/health` enriquecido** en `ai-service`, cacheado, con contraste de `embedding_model` contra el índice y sin llamar al proveedor.
10. **`AiHealthController`** en `api/ai/health`, sólo administradores, fuera del circuit breaker, más el método en el cliente del gateway.
11. **Tarjeta de estado** en el dashboard de administrador, con componentes Metronic ya existentes.
12. **Camino del dato**: volcado, sustitución de usuarios por cuentas de demo, restauración y `sync` de reconciliación.
13. **Deprecaciones** de `Dockerfile`, `Dockerfile.prod` y `backend/docker-compose.prod.yml`, y corrección de `backend/README.md`.
14. **Medir y anotar** el presupuesto de recuperación real en la demo, sin revertirlo.
15. Enlazar la HU en [`Documentos/epicas.md`](../../epicas.md) (EP11) durante el apply.
16. `openspec validate --all --strict` en verde antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 5 — es el único change que convierte todo lo construido desde C01 en algo que alguien ajeno al equipo puede abrir y usar. Sin él no hay criterio de entrega del §16 que se pueda marcar.
- **Urgencia (mercado / feedback):** **5** — 🔴; nunca se recorta; el §6 del plan lo nombra explícitamente en el disparador del orden de corte (*«si el 26 de agosto no están la tabla de ablations y el sistema desplegado»*), y esa fecha ya pasó.
- **Complejidad / esfuerzo:** 4 — ancho más que profundo: seis zonas, ningún algoritmo nuevo, ninguna migración, pero mucha superficie de configuración donde un valor mal puesto no da error.
- **Riesgos y dependencias:**
  - **El dato es el riesgo, no el despliegue.** Un entorno perfecto con el índice vacío pasa todos los tests y no sirve para nada. Mitigado llevando el camino del dato dentro del change y verificándolo con el `sync` de reconciliación.
  - **Los dos valores que mienten** (`STUB_MODE` y el modelo de embeddings). Mitigados versionándolos en git y contrastando el modelo contra el índice en el `/health`.
  - **El volumen de certificados de Caddy** y el límite semanal de la autoridad. Mitigado prohibiendo `down -v` y verificándolo en el escenario 6.
  - **Memoria de la instancia** con cuatro contenedores. Mitigado con `mem_limit` en el servicio de IA y swap; se mide tras el primer despliegue.
  - **Dominio aún no adquirido.** No bloquea: `sslip.io` como puente y un parámetro para migrar.
  - **El presupuesto de 2500 ms puede quedarse corto en la demo**, contra un proveedor a más latencia que un portátil. C17 mide y anota; el arreglo es de C21/C22.
  - **Fecha.** La ficha prometía el 19 de agosto y estamos a 29, con las olas 3 y 4 sin empezar. C17 está en *nunca se recorta*, así que el riesgo no es que se caiga, sino que compita por las mismas horas que C21, C22 y C24.
