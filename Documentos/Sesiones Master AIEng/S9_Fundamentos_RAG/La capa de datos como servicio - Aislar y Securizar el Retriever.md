# La capa de datos como servicio: aislar y securizar el retriever

Creada: 15 de junio de 2026 13:01
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S9. Fundamentos de RAG y técnicas de recuperación (https://app.notion.com/p/S9-Fundamentos-de-RAG-y-t-cnicas-de-recuperaci-n-380ea9ca03c480268ac0c4739784b444?pvs=21)

Al cierre del Artículo 4 tienes el flujo RAG completo dentro del servicio IA: reformulador, retriever, ensamblador, generador, todo orquestado por una función `estimate_from_transcript`. El endpoint público del servicio IA es uno solo — `POST /v1/estimate` — y detrás de él vive toda la lógica. El backend de negocio en Rails llama a ese endpoint, recibe la estimación estructurada, la persiste, la enseña al cliente. Funciona. Es lo que cualquier MVP de un sistema RAG ofrece.

El problema empieza cuando el sistema sale de la fase MVP. Imagina el escenario realista del segundo o tercer mes en producción. El equipo comercial quiere una funcionalidad nueva: dentro del CRM, al revisar un proyecto antiguo, poder buscar otros proyectos similares en la base histórica para apoyar una negociación. La búsqueda no genera estimación: solo devuelve los presupuestos parecidos y deja que el comercial los inspeccione. Es exactamente lo que el `retrieval` ya hace internamente, pero ahora hay que exponerlo.

La opción de mínimo esfuerzo es añadir un parámetro al endpoint existente: `POST /v1/estimate?retrieval_only=true`. La opción de medio esfuerzo es duplicar el endpoint: `POST /v1/estimate` para el flujo completo y `POST /v1/retrieve` para solo el retrieval. Ambas son tentadoras y ambas crean problemas operativos que no se ven hasta tres meses después.

Considera lo que estas dos opciones implican. Cuando la Sesión 10 introduzca reranking y búsqueda híbrida sobre el retriever, cualquier cambio toca el endpoint de estimación, incluso aunque la lógica de generación no varíe; el blast radius del cambio es innecesariamente amplio. Cuando llegue el momento de aplicar rate limiting, el endpoint de estimación necesita un régimen severo — cada llamada cuesta euros en tokens y segundos en latencia —, mientras que el de retrieval puede ser mucho más permisivo — cada llamada cuesta milisegundos y casi nada de dinero. Aplicar el mismo límite a ambos significa o bien estrangular al consumidor barato o bien dejar al caro sin protección. Cuando un compañero pida acceso al retrieval para un script ad-hoc de análisis, dar la misma API key que controla el endpoint de generación supone darle también permisos para gastar el presupuesto de LLM sin control.

Las tres tensiones — blast radius, rate limiting diferenciado, granularidad de credenciales — apuntan en la misma dirección. El retriever y el generador son **dos servicios lógicos distintos** que casualmente comparten codebase. Tratarlos como uno solo es una decisión que paga peaje a largo plazo. Este artículo aplica el patrón inverso: dos routers separados en FastAPI, dos contratos públicos distintos, dos régimenes de seguridad diferenciados, y un cliente Ruby que invoca al servicio IA desde el backend de negocio. La separación no es un refactor estético; es lo que permite que la Sesión 10 evolucione el retriever sin tocar el generador y que el operador del sistema pueda razonar sobre cada capa por separado.

## **Dos routers, dos contratos**

FastAPI organiza endpoints en `APIRouter`, un mecanismo de composición que permite separar la lógica del servicio en módulos independientes que luego se montan en la aplicación principal. La estructura final del servicio IA al cierre de S09 queda así:

```
src/estimator/
├── api/
│   ├── main.py
│   ├── security.py
│   └── routers/
│       ├── retrieval.py
│       └── estimate.py
├── retrieval/
│   ├── query_reformulator.py
│   └── retriever.py
└── generation/
    ├── context_assembler.py
    ├── prompt_builder.py
    └── estimator.py
```

El `retrieval.py` expone los endpoints que consumen el módulo de retrieval directamente, sin tocar la capa de generación. El `estimate.py` expone los endpoints que orquestan el flujo completo (reformulador → retriever → ensamblador → generador). El `main.py` monta ambos routers en la aplicación con prefijos de URL distintos:

```python
from fastapi import FastAPI
from estimator.api.routers import retrieval, estimate

app = FastAPI(title="Estimator AI Service", version="0.9.0")

app.include_router(retrieval.router, prefix="/v1/retrieval", tags=["retrieval"])
app.include_router(estimate.router, prefix="/v1/estimate", tags=["estimate"])
```

Los contratos públicos son completamente distintos. El router de retrieval expone dos endpoints, ambos con esquemas Pydantic estrictos:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from estimator.retrieval.retriever import search_chunks

router = APIRouter()

class SearchRequest(BaseModel):
    query_text: str = Field(min_length=10, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=30)
    distance_threshold: float = Field(default=0.6, ge=0.0, le=2.0)
    sectors: list[str] | None = None
    project_year_min: int | None = Field(default=None, ge=2010, le=2100)
    chunk_types: list[str] | None = None

class SearchResponseChunk(BaseModel):
    id: int
    content: str
    sector: str
    project_year: int
    chunk_type: str
    distance: float

class SearchResponse(BaseModel):
    chunks: list[SearchResponseChunk]
    low_confidence: bool
    total_candidates_considered: int

@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, _: str = Depends(require_retrieval_key)):
    result = search_chunks(
        query_text=req.query_text,
        top_k=req.top_k,
        distance_threshold=req.distance_threshold,
        sectors=req.sectors,
        project_year_min=req.project_year_min,
        chunk_types=req.chunk_types,
    )
    return SearchResponse(
        chunks=[SearchResponseChunk(**c.model_dump()) for c in result.chunks],
        low_confidence=len(result.chunks) == 0,
        total_candidates_considered=result.candidates_evaluated,
    )
```

Dos detalles deliberados en este endpoint. Primero, **el contrato es exhaustivo**: la respuesta incluye `low_confidence` y `total_candidates_considered` como campos de primer nivel, no anidados ni opcionales. El consumidor sabe siempre, sin parsear nada raro, si el retriever encontró material relevante. Segundo, `Depends(require_retrieval_key)` aplica autenticación específica de retrieval, distinta de la de estimate — el detalle de cómo se resuelve esa dependencia lo veremos en la sección de seguridad.

El router de estimate tiene un contrato más simple porque encapsula más:

```python
from estimator.generation.estimator import estimate_from_transcript

router = APIRouter()

class EstimateRequest(BaseModel):
    transcript: str = Field(min_length=100, max_length=50000)
    idempotency_key: str | None = Field(default=None, max_length=128)

@router.post("/from-transcript", response_model=Estimate)
def estimate(req: EstimateRequest, _: str = Depends(require_estimate_key)):
    return estimate_from_transcript(
        transcript=req.transcript,
        idempotency_key=req.idempotency_key,
    )
```

La asimetría entre los dos contratos es deliberada. El endpoint de retrieval expone palancas operativas — `top_k`, `distance_threshold`, filtros — porque sus consumidores pueden ser equipos internos que quieren ajustar el comportamiento para su caso. El endpoint de estimate solo expone el input mínimo (la transcripción) porque toda la complejidad interna debe estar gestionada por el servicio, no por el cliente. El backend de negocio en Rails no debería saber qué `top_k` se usa internamente; lo que necesita saber es "le paso una transcripción, me devuelve una estimación validada".

![art_5_figura-13-topologia-routers.jpg](https://media1-production-mightynetworks.imgix.net/asset/38582246-c4a7-4c42-b068-f1135edd73e9/art_5_figura-13-topologia-routers.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **API Keys y constant-time comparison**

La autenticación del servicio IA se hace con API Keys. La justificación es práctica: el consumidor del servicio es siempre otro servicio interno (el backend de negocio o, ocasionalmente, scripts internos del equipo), no un usuario final con identidad personal. Para ese patrón, API Keys es lo correcto: simple, sin estado, sin necesidad de un flujo de OAuth, sin un servidor de identidad adicional. Lo que cambia respecto a un solo API Key global son dos cosas: hay **dos claves separadas** (una para retrieval, otra para estimate) y la comparación se hace con `secrets.compare_digest` en lugar de `==`.

```python
import os
import secrets
from fastapi import Header, HTTPException, status

RETRIEVAL_API_KEY = os.environ["RETRIEVAL_API_KEY"]
ESTIMATE_API_KEY = os.environ["ESTIMATE_API_KEY"]

def require_retrieval_key(x_api_key: str = Header(...)) -> str:
    if not secrets.compare_digest(x_api_key, RETRIEVAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key

def require_estimate_key(x_api_key: str = Header(...)) -> str:
    if not secrets.compare_digest(x_api_key, ESTIMATE_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key
```

El uso de `secrets.compare_digest` en lugar del operador `==` es un detalle de criptografía que merece una línea de explicación. La comparación nativa de Python con `==` sobre strings es **non-constant-time**: termina en cuanto encuentra el primer carácter distinto. Esto crea un canal lateral medible — un atacante que mide cuánto tarda el servidor en responder con `401` puede inferir, byte a byte, cuán cerca está su clave de la real. Es un ataque conocido (timing attack) y aunque la latencia diferencial es del orden de microsegundos, sobre una red local con muchas peticiones es explotable. `compare_digest` está diseñado específicamente para comparaciones de secretos: tarda el mismo tiempo independientemente de cuán "cerca" esté la clave aportada de la real. El coste de usar la versión segura es cero — son la misma línea de código —, así que no hay justificación para usar `==` con secretos.

El detalle operativo de **rotación de claves** vale la pena nombrarlo aunque la implementación quede fuera del scope de S09. Las API Keys deberían rotarse periódicamente y la rotación debe ser **graceful**: durante la ventana de rotación, dos claves válidas a la vez (la antigua y la nueva), para que el consumidor pueda actualizar su configuración sin downtime. El patrón típico es cargar `RETRIEVAL_API_KEY` y `RETRIEVAL_API_KEY_PREVIOUS` y aceptar ambas; cuando todos los consumidores han migrado, se retira la antigua. La rotación se cubre brevemente en S15 (puesta en producción) pero el código actual ya queda preparado para ello sin esfuerzo adicional.

## **Rate limiting diferenciado con slowapi**

`slowapi` es la librería de rate limiting que el programa adopta por su integración natural con FastAPI: usa `Starlette` directamente y se monta como middleware sin cambios estructurales. La instalación y configuración mínima:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

def get_api_key(request) -> str:
    return request.headers.get("x-api-key", get_remote_address(request))

limiter = Limiter(key_func=get_api_key)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
```

El `key_func` es lo que hace el rate limiting **por API key** en lugar de por IP. La función `get_api_key` toma el header `X-API-Key` cuando está presente y cae a la IP del cliente como último recurso para peticiones sin autenticar (típicamente las que van a fallar de todos modos). Esta elección es importante: si el backend de negocio en Rails comparte una sola IP — porque vive en un servidor con NAT, o porque está detrás de un proxy compartido — el rate limiting por IP sería trivial de saturar y bloquearía a usuarios legítimos. Por API key, cada consumidor tiene su propio cubo de tokens.

Los dos régimenes se aplican como decoradores específicos en cada endpoint:

```python
@router.post("/search", response_model=SearchResponse)
@limiter.limit("120/minute")
def search(request, req: SearchRequest, _: str = Depends(require_retrieval_key)):
    ...

@router.post("/from-transcript", response_model=Estimate)
@limiter.limit("10/minute")
def estimate(request, req: EstimateRequest, _: str = Depends(require_estimate_key)):
    ...
```

Los números — 120/minuto para retrieval, 10/minuto para estimate — son una primera aproximación basada en costes esperados. Una petición de retrieval cuesta del orden de un milisegundo de latencia y nada significativo en infraestructura; permitir 120 por minuto por consumidor es generoso pero razonable. Una petición de estimate cuesta entre cinco y quince segundos de latencia y entre veinte céntimos y un euro en tokens; diez por minuto por consumidor es ya 600 por hora, que para un equipo comercial típico es más que suficiente y para el resto crea una protección contra runaway costs. Estos números no son universales; el operador del sistema los calibra observando el patrón real de uso.

Cuando se excede el límite, la respuesta debe ser informativa para que el cliente sepa cómo recuperarse:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "rate_limit_exceeded",
            "limit": str(exc.detail),
            "retry_after_seconds": 60,
        },
        headers={"Retry-After": "60"},
    )
```

El header `Retry-After` es el estándar HTTP que clientes bien construidos consultan para decidir cuándo reintentar; el campo `retry_after_seconds` en el body es la versión amigable para frontends que prefieren JSON. Ambos comunican la misma cosa de dos formas.

## **Idempotencia: peticiones duplicadas, una sola estimación**

El endpoint de estimate tiene una característica que el de retrieval no tiene: cada llamada cuesta significativamente. Si el backend de negocio en Rails reintenta una petición porque su HTTP client cortó el socket por timeout, no quieres que el servicio IA genere una segunda estimación, duplique el coste y produzca un resultado distinto al primero por la variabilidad inherente del LLM. El patrón estándar para evitarlo es **idempotency keys**.

El contrato es: el cliente envía un campo `idempotency_key` (un UUID que él genera) en cada petición de estimate. El servicio IA almacena en una caché temporal — Redis, o memoria en una versión MVP — la asociación `idempotency_key → estimate`. Si una petición llega con un `idempotency_key` ya conocido, el servicio devuelve la estimación cacheada sin volver a llamar al LLM. Si no, procesa la petición normalmente y guarda el resultado.

```python
import json
from estimator.cache import idempotency_store  # Redis wrapper, TTL = 24h

def estimate_from_transcript(transcript: str, idempotency_key: str | None = None) -> Estimate:
    if idempotency_key:
        cached = idempotency_store.get(idempotency_key)
        if cached:
            return Estimate.model_validate_json(cached)

    structured_query = reformulate_query(transcript)
    retrieved = search_chunks(...)
    context_block = build_context_block(retrieved.chunks)
    estimate = generate_estimate(context_block, structured_query)

    if idempotency_key:
        idempotency_store.set(
            idempotency_key,
            estimate.model_dump_json(),
            ttl_seconds=86400,
        )
    return estimate
```

El TTL de 24 horas es una decisión deliberada. Demasiado corto y los reintentos legítimos del cliente caen fuera de la ventana; demasiado largo y la caché se vuelve un repositorio implícito de estimaciones históricas — algo que debería estar en la base de datos del backend de negocio, no en la caché del servicio IA. Veinticuatro horas cubre el escenario realista (un reintento ocurre típicamente dentro de los minutos siguientes al fallo original) y mantiene la caché manejable.

Hay una sutileza con la idempotencia que merece mención. El cliente puede mandar la misma `idempotency_key` con una `transcript` ligeramente distinta — por ejemplo, si edita el texto y reintenta. Sin protección, el servicio devolverá la estimación cacheada de la primera transcripción, confundiendo al usuario. La protección estándar es hashear la transcripción y guardar el hash junto a la estimación; si una petición posterior con la misma key trae un hash distinto, se devuelve un `409 Conflict` con un mensaje que explica el problema. La implementación queda como mejora opcional fuera del scope de S09 pero el patrón vale la pena conocerlo.

![articulo-05-figura-02-halfvec.jpg](https://media1-production-mightynetworks.imgix.net/asset/87e34f5c-e787-4bb3-8676-3b6846439d7b/articulo-05-figura-02-halfvec.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Logging estructurado por etapa**

El servicio IA tiene cinco etapas internas que pueden fallar de formas distintas (reformulación, retrieval, ensamblado, generación, validación) y el debug eficiente exige distinguirlas. El programa adopta `structlog` con salida JSON para que cada log line sea parseable por las herramientas de observabilidad — el detalle de qué herramienta concreta (Logfire, Langfuse, Helicone) se cubre en S15. La configuración de S09 es la base mínima:

```python
import structlog
import time
import uuid
from contextlib import contextmanager

logger = structlog.get_logger()

@contextmanager
def log_stage(stage: str, request_id: str, **context):
    start = time.perf_counter()
    log = logger.bind(stage=stage, request_id=request_id, **context)
    log.info("stage.started")
    try:
        yield log
        duration_ms = (time.perf_counter() - start) * 1000
        log.info("stage.completed", duration_ms=round(duration_ms, 2))
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        log.exception("stage.failed", duration_ms=round(duration_ms, 2), error=str(exc))
        raise

def estimate_from_transcript(transcript: str, idempotency_key: str | None = None) -> Estimate:
    request_id = str(uuid.uuid4())
    with log_stage("reformulation", request_id):
        structured_query = reformulate_query(transcript)
    with log_stage("retrieval", request_id, sectors=structured_query.sector):
        retrieved = search_chunks(...)
    with log_stage("context_assembly", request_id, chunks=len(retrieved.chunks)):
        context_block = build_context_block(retrieved.chunks)
    with log_stage("generation", request_id, confidence_target="adaptive"):
        estimate = generate_estimate(context_block, structured_query)
    with log_stage("validation", request_id):
        validate_estimate(estimate, retrieved.chunks)
    return estimate
```

El `request_id` es lo que ata todas las líneas de log de una petición en una traza coherente; sin él, cuando inspecciones los logs vas a ver entradas de cinco etapas distintas entremezcladas con entradas de otras peticiones concurrentes y va a ser imposible reconstruir qué pasó en cuál. El `request_id` se incluye también como header `X-Request-ID` en la respuesta del servicio IA, para que el backend de negocio pueda correlacionar sus propios logs con los del servicio cuando algo se rompa.

Dos atributos adicionales por etapa que el programa siempre incluye: `duration_ms` para detectar regresiones de latencia, y un campo específico que ayuda al debug — `sectors` en retrieval (¿cuáles filtros se aplicaron?), `chunks` en assembly (¿cuántos chunks acabaron en el contexto?), `confidence` en validation (¿qué nivel devolvió el modelo?). Estos campos son los que, cuando dentro de tres meses uncliente reporte una estimación rara, te van a permitir reconstruir la cadena de decisiones que el servicio tomó sin tener que reproducir la petición.

![articulo-05-figura-03-senales-migracion.jpg](https://media1-production-mightynetworks.imgix.net/asset/e48b9261-aa74-4e50-95b2-de2dd2682aa3/articulo-05-figura-03-senales-migracion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **El cliente Ruby desde el backend de negocio**

El servicio IA está montado. La forma en que el backend de negocio en Rails lo invoca es lo que cierra el patrón. El programa muestra el cliente en Ruby por alineación con la implementación de referencia, pero el patrón es independiente del stack — cualquier HTTP client en cualquier lenguaje sirve.

```ruby
require "faraday"
require "faraday/retry"
require "securerandom"

class EstimatorClient
  ESTIMATE_TIMEOUT = 30  # seconds
  RETRY_OPTIONS = {
    max: 2,
    interval: 1.5,
    backoff_factor: 2,
    retry_statuses: [502, 503, 504],
    methods: [:post],
  }.freeze

  def initialize(base_url:, api_key:)
    @conn = Faraday.new(url: base_url) do |f|
      f.request :json
      f.request :retry, RETRY_OPTIONS
      f.response :json, content_type: /\\bjson$/
      f.options.timeout = ESTIMATE_TIMEOUT
      f.options.open_timeout = 5
      f.headers["X-API-Key"] = api_key
    end
  end

  def estimate_from_transcript(transcript:, idempotency_key: SecureRandom.uuid)
    response = @conn.post("/v1/estimate/from-transcript") do |req|
      req.body = {
        transcript: transcript,
        idempotency_key: idempotency_key,
      }
    end
    raise EstimationError, response.body["detail"] if response.status >= 400
    response.body
  end
end
```

Tres decisiones en este cliente merecen comentario. Primero, los **timeouts diferenciados**: `open_timeout` de 5 segundos para detectar rápidamente que el servicio IA está caído, y `timeout` total de 30 segundos para cubrir el caso peor de una llamada al LLM con `reasoning.effort` alto. Sin estos timeouts explícitos, el cliente cae a los defaults de Faraday (60 segundos para todo) y un usuario que abre una ventana de estimación se queda mirando un spinner sin saber si el sistema está roto o pensando. Segundo, el **retry policy** está restringido a `5xx` y específicamente a códigos que indican fallo transitorio (`502 Bad Gateway`, `503 Service Unavailable`, `504 Gateway Timeout`); reintentar un `400` o un `401` no tiene sentido — el servidor está diciendo que la petición está mal — y reintentar un `500` puro es ambiguo. Tercero, el `idempotency_key` se genera **por defecto** en el cliente con `SecureRandom.uuid`: cada llamada lleva una clave aunque el código que llama no se preocupe del tema. Si el retry policy de Faraday activa un reintento, la misma key viaja al servicio IA y el patrón de idempotencia se activa automáticamente sin que el programador tenga que pensarlo.

## **Trade-offs honestos**

La elección de **API Key vs JWT vs mTLS** es el debate clásico de seguridad de servicios internos y vale la pena nombrarla con precisión. API Key tiene dos limitaciones reales: no lleva información de identidad más allá de "alguien que tiene esta clave", y si la clave se filtra (en un log, en un repositorio mal configurado, en una variable de entorno expuesta) cualquiera puede usarla hasta que se rote. JWT mitiga la primera (los tokens llevan claims) pero no la segunda; mTLS mitiga ambas a costa de complejidad operativa significativa (gestión de certificados, infraestructura de CA, rotación más compleja). Para un servicio interno cuyo único consumidor es el backend de negocio en Rails y el cliente se despliega en infraestructura controlada, API Key es la opción de mejor coste/beneficio. Si el servicio IA se expusiera a múltiples consumidores externos con identidades distintas, JWT pasaría a ser la opción correcta. Si vivieras en una infraestructura con service mesh (Istio, Linkerd), mTLS sería casi gratuito y sería la opción por defecto. La decisión depende del contexto operativo, no de una preferencia universal.

El **OWASP API Security Top 10** es la referencia que el programa cita como lectura complementaria para los alumnos que quieran profundizar. El listado cubre las categorías estándar de fallos en APIs (broken authentication, broken object level authorization, security misconfiguration, etc.) y vale la pena conocerlo aunque el servicio IA del proyecto solo aplique directamente dos o tres de los items. Lo importante es interiorizar el reflejo de revisar la lista cada vez que se añade un endpoint nuevo.

El **rate limiting in-memory vs distribuido** es una decisión que el MVP elude por simplicidad pero el operador debe conocer. `slowapi` por defecto usa memoria del proceso para llevar la cuenta de peticiones; si el servicio IA se despliega con múltiples workers (gunicorn con `-w 4`) o múltiples instancias detrás de un load balancer, cada uno lleva su propia cuenta y el límite efectivo se multiplica por el número de workers. Para el MVP esto es aceptable — un solo worker en un solo contenedor — pero S15 introducirá Redis como backend de rate limiting cuando el sistema se escale horizontalmente. El cambio es de configuración, no de código: `slowapi` soporta Redis nativamente.

## **Conexión con la sesión en vivo**

El sexto bloque de la sesión es el cierre del flujo end-to-end y el escenario didáctico es deliberadamente provocativo. Vamos a poner el rate limit del endpoint de estimate en un número absurdamente bajo (dos por minuto), generar tres peticiones seguidas desde el cliente Ruby, y observar el comportamiento de Faraday cuando la tercera vuelve con `429`. Veremos el header `Retry-After`, veremos cómo el cliente lo respeta, y veremos el efecto del `idempotency_key` cuando uno de los retries pasa por el servicio: la respuesta cacheada vuelve en milisegundos en lugar de los quince segundos del LLM.

El segundo escenario es de seguridad. Vamos a filtrar deliberadamente la API key de retrieval en un commit (un caso de uso real que vemos todos los meses en algún cliente) y a discutir el procedimiento de respuesta: rotación inmediata, deploy de la nueva clave, retirada de la antigua, y por qué tener las dos claves separadas — retrieval y estimate — hace que el incidente sea muchísimo más manejable que si fueran una sola. Si la clave filtrada hubiera sido la única clave del servicio, el atacante tendría acceso al endpoint que cuesta dinero por petición; tenerlas separadas le limita el daño al acceso de datos sin coste, lo que es serio pero no catastrófico.

Y el cierre conceptual de toda la Sesión 09: lo que has construido ya no es un script con un LLM detrás, es un servicio operable. Tiene contratos claros, autenticación diferenciada, rate limits razonables, idempotencia, logging estructurado y un cliente robusto que lo invoca. La Sesión 10 va a evolucionar la capa de retrieval con reranking y búsqueda híbrida, y esa evolución va a tocar exactamente un módulo — el retriever — sin que el endpoint de estimate, el rate limit, las credenciales o el cliente Ruby tengan que cambiar. El aislamiento que has construido aquí es lo que hace ese tipo de evolución posible. Es lo que distingue un sistema RAG de juguete de uno que el equipo puede operar sin miedo durante años.