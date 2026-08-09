## Why

`jbg-ai` expone desde C02 ocho rutas `/v1` con contrato congelado, stubs deterministas y autenticación HS256, y **nadie las llama todavía**. Del lado .NET no existe ninguna pieza de integración: el backend no tiene ni un solo cliente HTTP saliente, ni resiliencia, ni correlación de trazas entre servicios.

C03 construye ese primer consumidor. Es la última pieza de la Ola 0 y está en ruta crítica: sin él, C15 (endpoint de búsqueda asistida) no puede empezar, y con C15 se caen C16, C17 y C34. El hito de la Ola 2 —un operador buscando en lenguaje natural desde producción— depende de esta pieza.

Hay un segundo motivo, menos obvio y más caro si se ignora. La capability `ai-service-auth` obliga a `jbg-ai` a rechazar todo token dudoso con un **401 que no revela la causa**: correcto como decisión de seguridad, brutal como experiencia de diagnóstico. Un secreto mal copiado, una audiencia de más en el token y un desfase de reloj producen exactamente el mismo síntoma mudo. Este change convierte esas trampas en requisitos verificables en vez de dejarlas como folclore oral entre los dos desarrolladores.

## What Changes

- **Cliente tipado hacia `jbg-ai`** en la capa de aplicación del backend, con **un único método** de búsqueda contra `POST /v1/retrieval/products`. La superficie del cliente crecerá en el change que consuma cada endpoint, no antes.
- **Modelos .NET espejo del contrato congelado**, con nombres en `snake_case` en el cable y nulabilidad real donde el contrato garantiza nulo en lugar de ausencia.
- **Ámbito de llamada explícito**: un tipo que transporta usuario, rol y punto de venta, construible **solo** con un punto de venta real. No autoriza nada; transporta un ámbito ya validado por quien llama.
- **Emisión del token interno de servicio**: HS256 con secreto propio, los cuatro claims obligatorios en `snake_case`, vencimiento corto, y **sin audiencia ni emisor**, porque el validador del servicio de IA rechaza un token que declare una audiencia que él no espera.
- **Degradación acotada**: presupuesto de tiempo por llamada, reintento único y cortacircuitos, en un cliente con nombre propio para que un fallo de la capa generativa no apague la búsqueda.
- **Modos de fallo distinguibles**: el receptor puede saber si el servicio no está disponible, si la ruta aún no está implementada o si la configuración es incorrecta. Ni la ruta no implementada ni el fallo de autenticación se reintentan.
- **Correlación entre servicios**: el identificador de traza viaja en el token y en una cabecera, de modo que una llamada puede seguirse a través de los logs de los dos servicios.
- **Traza estructurada por llamada** con inicio, fin y fallo, y **render dependiente del entorno**: consola legible en desarrollo, JSON ingerible en producción.
- **Validación de configuración en el arranque**: sin dirección del servicio o sin secreto, la API no arranca y el error nombra la clave que falta.
- **Guarda de deriva de contrato del lado .NET**, recíproca del snapshot que ya protege el lado Python.

Sin cambios que rompan nada: no se modifica ningún contrato REST existente, ni el snapshot de `jbg-ai`, ni el modelo de datos. La configuración gana una sección nueva y, por la validación en arranque, un despliegue sin esa sección no arranca — está recogido en la definición de hecho.

## Capabilities

### New Capabilities

- `ai-gateway-client`: integración del backend .NET con el servicio de IA. Cubre el método de búsqueda y el mapeo del contrato, el ámbito de llamada con punto de venta obligatorio, la emisión del token interno de servicio, la política de degradación y reintento, la traducción de los modos de fallo del contrato, la correlación de trazas del salto .NET↔Python y la guarda contra deriva del contrato.

### Modified Capabilities

- `backend`: el requisito existente `Structured Logging` se amplía en dos puntos. Primero, el render pasa a depender del entorno de despliegue —legible para una persona en desarrollo, JSON de una línea por evento en producción—, algo que la redacción actual insinúa al hablar de *«multiple output targets»* pero no exige. Segundo, el escenario de correlación se extiende a las **llamadas salientes** hacia otros servicios, no solo a las peticiones entrantes; hoy ese escenario está especificado y no implementado, y este change es el primero que lo cumple.

## Impact

**Código afectado**

- `backend/src/JoiabagurPV.Application/`: zona principal. Interfaces, modelos de transporte, ámbito de llamada, emisor de token, cliente, opciones de configuración, excepciones y registro en el contenedor de dependencias.
- `backend/src/JoiabagurPV.API/`: registro del cliente, sección de configuración nueva, fichero de configuración de producción para el render de logs, y la implementación del acceso al identificador de traza —que depende del contexto HTTP y por eso vive aquí, igual que el acceso al usuario actual.
- `backend/src/JoiabagurPV.Tests/`: dos utilidades nuevas reutilizables (un manejador HTTP falso y la localización de la raíz del repositorio) y tres suites unitarias.

**Dependencias**

- Se incorporan al backend las librerías de cliente HTTP y de resiliencia, ausentes hasta ahora, y una librería de formato JSON para los logs de producción.

**Sistemas y contratos**

- Consume el contrato congelado `ai-service/openapi.json` **sin modificarlo**. Cualquier necesidad de cambiarlo es una renegociación con change propio.
- No toca `ai-service/`, ni el frontend, ni la infraestructura, ni el modelo de datos. No hay migración.
- **Prerrequisito hacia adelante:** la dirección del servicio en producción presupone una red Docker de usuario que hoy no existe —el despliegue actual arranca los contenedores en la red por defecto, donde no hay resolución por nombre—. Queda como requisito nombrado sobre C17, junto con los dos parámetros del almacén de secretos. Si C17 lo pasa por alto, la integración funcionará en desarrollo y fallará en producción.

**Fuera de alcance**

Controlador y endpoint de búsqueda, hidratación de precio y stock, degradación al buscador léxico y activación por punto de venta (C15); los otros siete endpoints del contrato (C34, C13, C08); perfil de IA de producto (C08); feeds de indexación (C12); despliegue y secretos (C17).
