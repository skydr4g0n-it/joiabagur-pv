# Isolated demo environment deployment for the AI service (C17)

## Why

Todo lo construido desde C01 —el corpus, el enriquecimiento, el índice vectorial, el retriever, la hidratación autoritativa y el panel del operador— funciona **sólo contra el Docker de un portátil**, y el §16 del diseño pide como criterio de entrega *«URL pública con usuario demo y vídeo de 2-3 min»*. No hay ninguna URL que enseñar.

La ficha original daba por hecho que se desplegaría a producción. **No hay acceso a esa cuenta AWS**, y su base de datos contiene el catálogo real de la joyería: inyectar allí 764 productos sintéticos y 12 puntos de venta simulados sería un daño al negocio, no una decisión técnica. Este change levanta en su lugar un **entorno de demo autocontenido en otra cuenta**, sin una sola arista hacia la de la tienda.

Y trae el dato consigo, que es el verdadero riesgo: un despliegue impecable con el índice vacío pasaría todos los tests y entregaría una URL donde «Buscar con ayuda» no encuentra nada. Es la firma de A1 (C04) y B5 (C16) por tercera vez.

## What Changes

- **Módulo Terraform en directorio y estado propios** (`terraform/demo/`) para una cuenta AWS distinta: instancia, grupo de seguridad con sólo 80/443 entrantes, IP elástica, dos repositorios de imágenes con su política de ciclo de vida, almacén de parámetros bajo un prefijo propio y rol de despliegue federado **acotado al entorno `demo`**, más estricto que el de producción. La imagen base del sistema operativo se resuelve por parámetro público en lugar de una variable que hay que actualizar a mano.
- **Aprovisionamiento del host reducido a cuatro pasos** sin nada específico de la aplicación, con el complemento de Compose instalado desde una release **con versión fijada**.
- **Fichero de composición autocontenido en la raíz** con **cuatro servicios**: proxy, API con la interfaz de usuario, servicio de IA y base de datos con extensión vectorial. Volúmenes, red y límite de memoria nombrados de forma inconfundible.
- **La frontera público/privado queda escrita en el fichero**: sólo el proxy declara puertos publicados. El servicio de IA, que custodia la clave del proveedor, no publica ninguno.
- **Terminación TLS automática** en el proxy, con nombre de dominio parametrizado para poder arrancar con un nombre derivado de la dirección IP y migrar al dominio propio cambiando un parámetro.
- **Flujo de despliegue nuevo** sobre una rama de entorno dedicada, con los secretos leídos del almacén **al entorno del proceso y nunca a disco**, y verificación posterior ejecutada dentro del host porque el servicio es privado y el ejecutor externo no lo alcanza.
- **Imagen de demo independiente** para la API y la interfaz, con base de rutas relativa que la vuelve agnóstica del nombre de dominio. La imagen de producción **no se toca**.
- **Endurecimiento de la imagen del servicio de IA**: construcción multietapa, usuario sin privilegios, instalador con versión fijada en lugar de una etiqueta móvil, y comprobación de salud propia.
- **Fichero de exclusiones de contexto de construcción** en la raíz, hoy inexistente.
- **Salud enriquecida** del servicio de IA: conectividad con la base de datos, estado del índice y si la credencial del proveedor está configurada — **sin llamar nunca al proveedor**, y con contraste del modelo de embeddings configurado frente al que consta en el índice.
- **Endpoint de salud en el backend**, sólo para administradores y **fuera del disyuntor**, más una **tarjeta de estado** en el panel de administración: la interfaz no puede consultar al servicio de IA directamente porque es privado.
- **Camino del dato**: volcado del esquema de negocio y del esquema vectorial desde el entorno local, sustitución del personal real por cuentas de demostración, y una sincronización de reconciliación que demuestra que el camino está cableado.
- **Deprecación** de dos ficheros de construcción y un fichero de composición en desuso, y corrección de la documentación del backend que presenta un camino de despliegue obsoleto como si fuera el vigente.

**Sin cambios que rompan nada.** No se modifica ningún contrato REST existente, ni el contrato congelado del servicio de IA, ni el fichero de composición de desarrollo local, ni la imagen de producción, ni el modelo de datos. **No hay migración**, ni de EF Core ni de Alembic.

## Capabilities

### New Capabilities

- `demo-deployment`: entorno de demostración desplegado y aislado — topología y frontera de red, clasificación de la configuración entre secretos y ajustes, canalización de despliegue y verificación posterior, camino del dato hasta el índice, y persistencia de datos y certificados frente a redespliegues.

### Modified Capabilities

- `ai-service-runtime`: el requisito de salud pública deja de ser un indicador de estado y versión y pasa a informar además de la conectividad con la base de datos, del estado del índice y de si la credencial del proveedor está configurada, **sin llamar al proveedor** y con resultado cacheado. Se añade el contraste del modelo de embeddings configurado contra el que consta en el índice.
- `dashboard-analytics`: el panel de administración incorpora una tarjeta de estado del servicio de IA, con su restricción de rol.

**Capacidades que deliberadamente NO se modifican:**

- `ai-service-api-contracts`: la salud enriquecida conserva su tipo de retorno abierto, así que el contrato congelado y su prueba de deriva **siguen intactos**. Bifurcar la salud en sondas de vida y de disponibilidad sí movería el contrato, y por eso queda fuera de este change.
- `ai-service-dev-compose`: fija literalmente la ruta y la red del fichero de composición de desarrollo. Este change **no lo mueve ni lo renombra**; el fichero de la demo es independiente.

## Impact

| Zona | Impacto |
|---|---|
| `terraform/demo/` | **Nuevo**, con estado propio. Sin relación con el estado de producción |
| `.github/workflows/` | **Un workflow nuevo.** Los existentes no se tocan |
| Raíz del repositorio | **Nuevos:** fichero de composición de la demo, directorio de despliegue (configuración del proxy, script y runbook) y fichero de exclusiones de contexto |
| `ai-service/` | Salud enriquecida y Dockerfile endurecido. **Contrato congelado sin cambios** |
| `backend/` | Controlador de salud nuevo, un método en el cliente del gateway con su propio cliente HTTP sin disyuntor, y su objeto de transferencia. Imagen de demo nueva. Deprecaciones y corrección de documentación |
| `frontend/` | Tarjeta de estado en el panel de administración, con componentes ya existentes |
| `openspec/` | Este change y la nota de tareas diferidas |
| `Documentos/` | Enlazar la historia en la épica de plataforma del servicio de IA |
| **Cuenta AWS de la tienda** | **Ninguno.** Ni infraestructura, ni permisos, ni flujos de despliegue, ni base de datos |
| Modelo de datos | **Ninguno.** Sin entidades, campos, índices ni migraciones |

**Dependencias externas del apply**, que no son de código y bloquean el despliegue real: alta de la cuenta AWS de demostración, y compra del dominio — esta última **no bloqueante**, porque el nombre de dominio es un parámetro y existe un puente sin coste.

**Riesgo principal:** que el entorno quede desplegado y el índice vacío. Mitigado llevando el camino del dato dentro del change y verificándolo en la comprobación posterior al despliegue, que exige un recuento de documentos mayor que cero.

**Riesgos secundarios:** dos valores de configuración que, mal puestos, no producen ningún error —el modo de respuestas simuladas y el modelo de embeddings— mitigados versionándolos como literales y contrastando el modelo contra el índice; y la pérdida del volumen de certificados en un redespliegue, que chocaría con el límite semanal de emisión de la autoridad certificadora.
