# Arquitectura escalable en proyectos IA generativa

Creada: 30 de abril de 2026 19:03
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S2. Primeros pasos de arquitectura CAG (https://app.notion.com/p/S2-Primeros-pasos-de-arquitectura-CAG-352ea9ca03c4800aa421ca55b02ceccb?pvs=21)

## **¿Por qué FastAPI para proyectos con IA?**

Si vienes de frameworks como Rails, Django o Express, la primera pregunta razonable es: ¿por qué FastAPI? La respuesta corta es que las aplicaciones que integran LLMs tienen un perfil de ejecución fundamentalmente diferente al de las aplicaciones web tradicionales.

Una petición CRUD típica tarda milisegundos. Una llamada a un LLM puede tardar entre 2 y 30 segundos. En un framework síncrono tradicional con modelo de threads (como Rails con Puma o Django con Gunicorn WSGI), cada petición al LLM bloquea un thread completo durante todo ese tiempo. Bajo carga, tus workers se agotan rápidamente esperando respuestas de la API de OpenAI o Anthropic mientras no hacen nada útil.

FastAPI está construido sobre ASGI (Asynchronous Server Gateway Interface) y soporta `async/await` de forma nativa. Cuando una petición está esperando la respuesta del LLM, el event loop libera ese hilo para atender otras peticiones. El resultado es que un proceso FastAPI puede manejar decenas de peticiones concurrentes con el mismo consumo de memoria que un framework síncrono dedicaría a una sola.

Esto no significa que FastAPI sea la única opción, pero sí que su modelo de concurrencia está alineado con la realidad de las cargas de trabajo con IA: muchas operaciones I/O-bound de larga duración.

## **El problema del archivo único**

FastAPI permite levantar un servidor funcional en cinco líneas de código. Esto es una ventaja enorme para prototipar, pero se convierte en un problema cuando el proyecto crece.

```python
# main.py — all in one file
from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()
client = OpenAI()

@app.post("/estimate")
async def estimate(transcription: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres un estimador de software..."},
            {"role": "user", "content": transcription}
        ]
    )
    return {"estimation": response.choices[0].message.content}
```

Este código funciona. Pero tiene todo mezclado: la configuración del cliente LLM, la lógica de negocio (cómo construir el prompt, qué contexto inyectar), la definición del endpoint HTTP, y la estructura de la respuesta. Cuando necesites añadir un segundo proveedor, gestionar errores de la API, inyectar contexto de estimaciones históricas o cambiar el formato de respuesta, estarás editando un archivo que crece sin estructura.

Si ya has construido aplicaciones web a escala, este patrón te resultará familiar. Es exactamente el mismo problema que tienen los “fat controllers” en Rails o los views monolíticos en Django. La solución también es familiar: separación de responsabilidades.

## **Estructura por responsabilidades**

La estructura que usaremos en el proyecto separa el código en capas con responsabilidades claras. No es una estructura inventada para este programa — es una adaptación de patrones probados en producción, ajustada a las necesidades específicas de aplicaciones con LLM.

```
estimador-cag/
├── app/
│   ├── __init__.py
│   ├── main.py               ← Punto de entrada de la aplicación
│   ├── config.py             ← Configuración centralizada
│   │
│   ├── routers/              ← Endpoints HTTP (la capa de transporte)
│   │   ├── __init__.py
│   │   └── estimations.py
│   │
│   ├── services/             ← Lógica de negocio (la capa inteligente)
│   │   ├── __init__.py
│   │   └── llm_service.py
│   │
│   ├── schemas/              ← Contratos de datos (request/response)
│   │   ├── __init__.py
│   │   └── estimation.py
│   │
│   └── context/              ← Datos de referencia para CAG
│       ├── __init__.py
│       └── examples.py
│
├── tests/
│   └── ...
├── .env
├── .env.example
├── .gitignore
└── pyproject.toml
```

Cada directorio tiene una responsabilidad única y bien definida. Veamos qué hace cada capa y por qué existe.

## **La capa de configuración: `config.py`**

Todo proyecto necesita gestionar variables que cambian entre entornos: claves API, URLs de servicios, modos de ejecución. En Python con FastAPI, el patrón estándar es usar Pydantic `BaseSettings`, que combina dos cosas que normalmente se hacen por separado: cargar variables de entorno y validar que tienen el tipo y formato correctos.

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

El decorador `@lru_cache` asegura que la configuración se carga una sola vez y se reutiliza en todas las peticiones. Es el equivalente funcional de un singleton, pero sin la maquinaria habitual de patrones de diseño.

Si vienes de Rails, esto es lo que hace `config/credentials.yml` + `Rails.application.config` pero con validación de tipos en tiempo de carga. Si la variable `OPENAI_API_KEY` no está definida, la aplicación falla al arrancar, no cuando un usuario hace la primera petición. Fallar rápido es una ventaja, no un problema.

## **La capa de transporte: `routers/`**

Los routers en FastAPI son el equivalente a los controllers en MVC. Su responsabilidad es exclusivamente gestionar la comunicación HTTP: recibir peticiones, validar el formato de entrada, delegar el trabajo a la capa de servicios, y formatear la respuesta.

```python
# routers/estimations.py
from fastapi import APIRouter, Depends
from app.schemas.estimation import EstimationRequest, EstimationResponse
from app.services.llm_service import generate_estimation

router = APIRouter(prefix="/api/v1", tags=["estimations"])

@router.post("/estimate", response_model=EstimationResponse)
async def estimate(request: EstimationRequest):
    result = await generate_estimation(request.transcription)
    return result
```

Observa lo que este endpoint no hace: no construye prompts, no llama directamente a la API de OpenAI, no gestiona errores del LLM, no formatea la estimación. Solo recibe, delega y devuelve. Si necesitas cambiar cómo se genera la estimación (otro modelo, otro proveedor, otra estrategia de prompt), no tocas este archivo.

El principio es el mismo que en cualquier framework web maduro: los endpoints deben ser finos. La lógica vive en los servicios.

## **La capa de negocio: `services/`**

Aquí vive la inteligencia de la aplicación. En un proyecto con LLM, esta capa es donde ocurre lo interesante: la construcción del prompt, la inyección de contexto, la llamada al modelo y el procesamiento de la respuesta.

```python
# services/llm_service.py
from openai import OpenAI
from app.config import get_settings
from app.context.examples import ESTIMATION_EXAMPLES

settings = get_settings()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def build_system_prompt() -> str:
    examples_text = format_examples(ESTIMATION_EXAMPLES)
    return f"""Eres un experto en estimación de proyectos de software.

Utiliza los siguientes presupuestos históricos como referencia:

{examples_text}

Genera una estimación detallada para el proyecto descrito."""

async def generate_estimation(transcription: str) -> dict:
    system_prompt = build_system_prompt()

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcription}
        ]
    )

    return {
        "estimation": response.choices[0].message.content,
        "model": settings.LLM_MODEL,
        "provider": settings.LLM_PROVIDER,
    }
```

Esta separación tiene una consecuencia práctica importante: puedes testear la lógica de construcción de prompts sin necesidad de hacer llamadas HTTP, y puedes testear los endpoints sin necesidad de llamar al LLM real (usando mocks).

A medida que el proyecto crezca, esta capa se subdividirá. Podrías tener un `prompt_builder.py` para la lógica de construcción de prompts, un `llm_client.py` para la comunicación con la API, y un `postprocessor.py` para validar y formatear las respuestas. Pero en esta primera iteración, un solo archivo de servicio es suficiente.

## **Los contratos de datos: `schemas/`**

Pydantic no es solo una librería de validación — es el sistema de tipos de tu API. Cada schema define un contrato explícito entre tu servicio y sus consumidores.

```python
# schemas/estimation.py
from pydantic import BaseModel, Field

class EstimationRequest(BaseModel):
    transcription: str = Field(
        ...,
        min_length=50,
        description="Transcripción de la reunión con el cliente"
    )

class EstimationResponse(BaseModel):
    estimation: str
    model: str
    provider: str
```

Estos schemas hacen varias cosas por ti automáticamente: validan que la transcripción tiene al menos 50 caracteres (evitando llamadas inútiles al LLM), generan documentación interactiva en Swagger, y serializan la respuesta al formato JSON correcto.

Si vienes de Rails, esto es lo que hacen los serializers (como `active_model_serializers` o `jsonapi-serializer`) pero integrado en el framework. Si vienes de TypeScript, es similar a los DTOs de NestJS con class-validator.

La ventaja de tener schemas explícitos es que el contrato de tu API está documentado en código, no en un README que nadie actualiza.

## **Los datos de referencia: `context/`**

Esta capa es específica de la arquitectura CAG. Contiene los datos que se inyectan como contexto en cada llamada al LLM — en nuestro caso, los ejemplos de estimaciones históricas que el modelo usará como referencia.

```python
# context/examples.py
ESTIMATION_EXAMPLES = [
    {
        "meeting_summary": "El cliente necesita una plataforma web de gestión de inventario...",
        "estimation": "## Estimación: Plataforma de Gestión de Inventario\\n\\n..."
    },
    # ... más ejemplos
]
```

En esta primera iteración, los datos son estáticos — literalmente definidos en el código. Esto es deliberado. Nos permite iterar sobre la calidad de los ejemplos sin preocuparnos por infraestructura de datos. Cuando evolucionemos a RAG en módulos posteriores, esta capa será reemplazada por un servicio de búsqueda semántica que recupera los ejemplos más relevantes de una base de datos vectorial.

Tener esta capa separada desde el principio, aunque sea con datos estáticos, nos da un punto de sustitución limpio. El servicio LLM no sabe ni le importa si los ejemplos vienen de un diccionario en memoria o de una query a pgvector. Solo recibe datos formateados.

## **El punto de entrada: `main.py`**

El archivo `main.py` es el pegamento que conecta todas las piezas. Su responsabilidad es crear la instancia de FastAPI, registrar los routers y configurar el middleware necesario.

```python
# main.py
from fastapi import FastAPI
from app.routers import estimations

app = FastAPI(
    title="Estimador CAG",
    description="Sistema de estimación de software con arquitectura CAG",
    version="0.1.0"
)

app.include_router(estimations.router)

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

Mantener `main.py` breve es una señal de que la estructura está bien organizada. Si este archivo empieza a crecer, es probable que estés poniendo lógica donde no debería estar.

## **El flujo completo de una petición**

Cuando un usuario envía una transcripción al endpoint `/api/v1/estimate`, la petición atraviesa las capas en este orden:

```
Cliente (curl, Swagger, app frontend)
    │
    ▼
main.py ──► routers/estimations.py     ← Valida el request con Pydantic
                    │
                    ▼
             services/llm_service.py    ← Construye el prompt con contexto de context/
                    │
                    ▼
             API del LLM (OpenAI/Anthropic)
                    │
                    ▼
             services/llm_service.py    ← Procesa la respuesta
                    │
                    ▼
             routers/estimations.py     ← Serializa el response con Pydantic
                    │
                    ▼
              Cliente (JSON response)
```

Cada capa hace una cosa y la hace bien. Si algo falla en la llamada al LLM, el error se gestiona en el servicio, no en el router. Si cambia el formato de respuesta, se modifica el schema, no el servicio. Si cambia la estrategia de prompt, se modifica el servicio, no el router.

## **Convenciones que importan**

Más allá de la estructura de directorios, hay decisiones de proyecto que impactan en la mantenibilidad a largo plazo.

### **Gestión de dependencias con `uv`**

El programa utiliza `uv` como gestor de paquetes. Si vienes de Ruby, `uv` es el equivalente a Bundler. Si vienes de Node, es el equivalente a pnpm o yarn. El archivo `pyproject.toml` declara las dependencias del proyecto con sus versiones, y `uv` se encarga de resolver e instalar las compatibles.

```bash
# Instalar dependencias
uv sync

# Añadir una nueva dependencia
uv add httpx

# Ejecutar la aplicación
uv run uvicorn app.main:app --reload
```

### **Variables de entorno y seguridad**

Las claves API nunca van en el código. Punto. Se definen en un archivo `.env` que está en `.gitignore`, y se acceden a través de la capa de configuración. El archivo `.env.example` documenta qué variables necesita el proyecto sin exponer valores reales.

### **Versionado de API**

El prefijo `/api/v1` en los routers no es decorativo. Cuando tu API tenga consumidores (como la app Rails que consumirá nuestro servicio RAG más adelante), necesitas poder evolucionar los endpoints sin romper a los clientes existentes. Añadir `/api/v2` con un nuevo contrato mientras `/api/v1` sigue funcionando es la forma estándar de hacer esto.

## **Cómo evoluciona esta estructura**

La estructura que hemos definido es la correcta para la fase CAG del proyecto. A medida que avancemos en el programa, crecerá de forma natural:

```
Sesión 02 (ahora)              Módulos 3-4 (RAG)           Módulo 5 (Agentes)
─────────────────              ──────────────────           ──────────────────
app/                           app/                         app/
├── config.py                  ├── config.py                ├── config.py
├── routers/                   ├── routers/                 ├── routers/
│   └── estimations.py         │   ├── estimations.py       │   ├── estimations.py
├── services/                  │   └── **ingestion.py**         │   ├── ingestion.py
│   └── llm_service.py         ├── services/                │   └── **agents.py**
├── schemas/                   │   ├── llm_service.py       ├── services/
│   └── estimation.py          │   ├── **embedding.py**         │   ├── llm_service.py
└── context/                   │   ├── **retrieval.py**         │   ├── embedding.py
    └── examples.py            │   └── **ingestion.py**         │   ├── retrieval.py
                               ├── schemas/                 │   ├── agent_orchestrator.py
                               │   ├── estimation.py        │   └── tools/
                               │   └── document.py          │       ├── estimator.py
                               ├── **models/**                  │       └── validator.py
                               │   ├── **base.py**              ├── schemas/
                               │   ├── **document.py**          │   └── ...
                               │   └── **chunk.py**             └── models/
                               └── **db/**                          └── ...
                               │   └── **session.py**
                               └── context/
	                                 └── examples.py
```

Cada módulo añade archivos nuevos sin modificar la estructura fundamental. Los routers siguen siendo delgados (”skinny”), los servicios siguen conteniendo la lógica, los schemas siguen definiendo los contratos. Lo que cambia es la cantidad de servicios y la complejidad interna de cada uno, no la arquitectura del proyecto.

## **Resumen**

- **FastAPI es la elección natural para aplicaciones con LLM** porque su modelo async gestiona eficientemente las llamadas de larga duración a APIs de IA, a diferencia de frameworks síncronos que bloquean un thread por cada petición.
- **No es la única alternativa** → completar
- **La estructura por responsabilidades** (routers → services → schemas → context) separa transporte, lógica, contratos y datos. Es el mismo principio que aplicas en cualquier framework web maduro, adaptado a las necesidades específicas de un proyecto con IA.
- **Los routers son delgados** — reciben, delegan y devuelven. La lógica de prompts, llamadas al LLM y procesamiento de respuestas vive en los servicios.
- **La capa de contexto es el punto de sustitución** entre CAG y RAG. Hoy son datos estáticos; mañana será un servicio de búsqueda semántica. La separación permite hacer ese cambio sin reescribir el resto.
- **La configuración con Pydantic** `BaseSettings` valida las variables de entorno al arrancar la aplicación, no cuando un usuario hace una petición. Fallar rápido es una ventaja.
- **Esta estructura crece sin romperse.** Cada módulo del programa añade archivos, no reestructura lo existente.