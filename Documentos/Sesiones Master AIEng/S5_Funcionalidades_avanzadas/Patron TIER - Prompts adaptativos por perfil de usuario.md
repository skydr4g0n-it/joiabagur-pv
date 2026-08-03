# Prompts adaptativos por perfil de usuario: el patrón "tier”

Creada: 17 de mayo de 2026 12:46
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S5. Funcionalidades avanzadas (https://app.notion.com/p/S5-Funcionalidades-avanzadas-363ea9ca03c4809fa6b4c8d2a9413af9?pvs=21)

Hay un patrón recurrente cuando un equipo de ingeniería senior se enfrenta por primera vez al problema de "el sistema debe responder de forma distinta según quién pregunte". La conversación arranca con frases como "necesitamos un fine-tuning específico para perfiles ejecutivos", "hay que entrenar un modelo distinto para cada rol" o "esto requiere RLHF con preferencias por tipo de usuario". Y luego, después de una semana investigando opciones de entrenamiento, alguien propone lo que iba a funcionar desde el principio: una columna `tier` en la tabla de usuarios, un `if/elif` que selecciona el template Jinja2 correcto, y dos schemas Pydantic distintos en la salida.

Esa propuesta tan poco glamorosa es la respuesta correcta. La sofisticación de los productos con IA bien hechos rara vez vive en la capa del modelo; vive en el resto de la aplicación. Este artículo desmonta el mito de que adaptar un sistema CAG a múltiples perfiles de usuario requiere maquinaria avanzada, y construye la versión simple que funciona en producción.

## **1. El antipatrón del prompt único**

Empezamos por el problema. La versión inicial del `estimator` —la que llegó al final de la sesión 04— tiene un único system prompt. Todos los usuarios reciben el mismo formato de respuesta, el mismo nivel de detalle, el mismo vocabulario. La transcripción y los parámetros tipados cambian; el system prompt no.

Imagina dos usuarios distintos haciendo la misma petición sobre el mismo proyecto:

**Usuario A — desarrollador senior del equipo de ingeniería.** Quiere desglose por componentes técnicos: backend, frontend, infraestructura, integraciones. Necesita ver las horas estimadas por cada componente, los riesgos técnicos identificados, las asunciones sobre stack y los puntos de incertidumbre que pueden disparar el alcance.

**Usuario B — director comercial preparando una propuesta para el cliente.** Quiere el coste agregado, el rango de duración, una lista de hitos visibles y un nivel de confianza global. No le sirve ver "12h en configuración de PostgreSQL"; le sirve ver "Fase 1: Setup técnico — 2 semanas, riesgo bajo".

El sistema actual les devuelve a los dos exactamente la misma respuesta. Si el formato está optimizado para el desarrollador, el director comercial recibe ruido técnico que tiene que filtrar mentalmente. Si está optimizado para el comercial, el desarrollador no ve los detalles que necesita para negociar el alcance con el cliente. Y si el formato es un compromiso entre ambos, ninguno de los dos queda bien servido.

La consecuencia operativa es predecible: los usuarios empiezan a acompañar la transcripción con instrucciones del tipo "explícame los componentes técnicos uno a uno" o "dame el resumen ejecutivo solo". Está volviendo a aparecer exactamente el patrón que combatimos en la sesión 04: la calidad del output dependiendo de la calidad del prompt del usuario. La interfaz se convierte de nuevo en un chat encubierto.

## **2. La decisión arquitectónica: tier como dimensión del producto**

La solución correcta tiene tres capas. Cada una vive en un sitio distinto y resuelve un problema distinto.

![004-tres-capas-tier.jpg](https://media1-production-mightynetworks.imgix.net/asset/716590ac-8b91-419e-aa20-73044eb224d9/004-tres-capas-tier.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

### **Capa 1 — Persistencia: el tier vive en la BBDD del backend de negocio**

En la tabla `users` del backend de negocio (Rails u otro stack), añades una columna `tier` con un conjunto enumerado de valores. Para el `estimator`, tres valores cubren la mayoría de los casos:

```ruby
# db/migrate/20250506_add_tier_to_users.rb
class AddTierToUsers < ActiveRecord::Migration[7.1]
  def change
    add_column :users, :tier, :string, null: false, default: "developer"
    add_index :users, :tier
  end
end
```

```ruby
# app/models/user.rb
class User < ApplicationRecord
  TIERS = %w[developer pm executive].freeze

  validates :tier, inclusion: { in: TIERS }
end
```

El tier no es un rol de autorización (qué puede hacer el usuario) — eso vive en otra columna o en un sistema dedicado. El tier es una **dimensión de producto**: define qué experiencia del producto recibe el usuario. La separación importa porque un mismo rol de autorización puede mapear a tiers distintos según contexto: un developer técnico puede pedir el modo `executive` cuando prepara una presentación para el comité.

### **Capa 2 — Propagación: el tier viaja al servicio IA**

Cuando el backend de negocio hace la llamada al servicio IA, propaga el tier del usuario actual. Hay dos maneras canónicas de hacerlo y la elección importa.

La primera es enviarlo como **claim en un JWT firmado por el backend de negocio** que el servicio IA valida. Es lo correcto en sistemas con varios backends de negocio o cuando el servicio IA debe defenderse de peticiones manipuladas:

```ruby
# Lado del backend de negocio (Rails)
class AiServiceClient

		def request_estimate(user:, transcript:, attachments: [])
		
				token = JWT.encode(
						{
								sub: [user.id](http://user.id/),
								tier: user.tier,
								exp: 5.minutes.from_[now.to](http://now.to/)_i
						},
						[Rails.application.credentials.ai](http://rails.application.credentials.ai/)_service_secret,
						"HS256"
				)

				HTTP
						.headers(authorization: "Bearer #{token}")
						.post(
								"#{ENV['AI_SERVICE_URL']}/sessions/#{session_id}/estimate",
								form: {
										transcript: transcript,
										attachments: attachments
								}
						)
		end
end
```

```python
# Lado del servicio IA (Python)

import jwt
from fastapi import Depends, HTTPException, Header

def get_caller_context(
		authorization: str = Header(...)
) -> CallerContext:

		token = authorization.removeprefix("Bearer ").strip()

		try:
				payload = jwt.decode(
						token,
						[settings.ai](http://settings.ai/)_service_secret,
						algorithms=["HS256"]
				)

		except jwt.PyJWTError:
				raise HTTPException(
				status_code=401,
				detail="Invalid token"
		)

		return CallerContext(
				user_id=payload["sub"],
				tier=payload["tier"]
		)
```

La segunda es enviarlo como **header simple** en un entorno de red controlado, donde el backend de negocio y el servicio IA están en la misma VPC y la confianza entre ambos está garantizada por red, no por criptografía:

```python
from fastapi import Header, HTTPException

ALLOWED_TIERS = {"developer", "pm", "executive"}

def get_caller_context(
    x_user_id: str = Header(...),
    x_user_tier: str = Header(...)
) -> CallerContext:

    if x_user_tier not in ALLOWED_TIERS:
        raise HTTPException(
            status_code=400,
            detail="Unknown tier"
        )

    return CallerContext(
        user_id=x_user_id,
        tier=x_user_tier
    )
```

Para el `estimator` cualquiera de las dos es defendible. JWT es la opción correcta a medio plazo porque añade defensa en profundidad y permite añadir más claims (timezone, idioma, organization_id) sin renegociar contratos. El header simple es razonable mientras el sistema vive en una sola red privada.

### **Capa 3 — Materialización: el tier selecciona template y schema**

Esta es la capa donde el tier deja de ser metadata y se convierte en comportamiento. El servicio IA usa el tier para elegir dos cosas: el template Jinja2 del system prompt y el schema Pydantic de la salida.

```python
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader, select_autoescape

BASE_DIR = Path(__file__).resolve().parent

jinja_env = Environment(
    loader=FileSystemLoader(BASE_DIR / "prompts"),
    autoescape=select_autoescape()
)

# Output schemas — one per tier

class DeveloperEstimate(BaseModel):
    components: list["ComponentEstimate"]
    technical_risks: list[str]
    stack_assumptions: list[str]
    uncertainty_drivers: list[str]
    total_hours_range: tuple[int, int]

class PmEstimate(BaseModel):
    phases: list["PhaseEstimate"]
    milestones: list["Milestone"]
    team_composition: "TeamComposition"
    duration_weeks_range: tuple[int, int]
    blockers: list[str]

class ExecutiveEstimate(BaseModel):
    headline_cost_range: "CostRange"
    headline_duration_range: "DurationRange"
    confidence_level: Literal["low", "medium", "high"]
    top_three_risks: list[str]
    go_no_go_recommendation: str

# Resolution map

TIER_CONFIG = {
    "developer": {
        "template": "estimate_developer.j2",
        "schema": DeveloperEstimate,
    },
    "pm": {
        "template": "estimate_pm.j2",
        "schema": PmEstimate,
    },
    "executive": {
        "template": "estimate_executive.j2",
        "schema": ExecutiveEstimate,
    },
}

def resolve_tier_config(tier: str) -> dict:

    config = TIER_CONFIG.get(tier)

    if config is None:
        raise ValueError(f"Unknown tier: {tier}")

    return config
```

Y la integración con el endpoint de estimación queda limpia:

```python
from fastapi import Depends, File, Form, HTTPException, UploadFile

@app.post("/sessions/{session_id}/estimate")
async def estimate(
    session_id: str,
    transcript: str = Form(...),
    attachments: list[UploadFile] = File(default=[]),
    caller: CallerContext = Depends(get_caller_context),
):

    config = resolve_tier_config(caller.tier)

    template = jinja_env.get_template(config["template"])
    output_schema = config["schema"]

    session = await load_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    system_prompt = template.render(
        project_metadata=session.project_metadata,
        session_history=session.history,
        caller_tier=caller.tier,
    )

    response = await llm_client.responses.create(
        model="gpt-4o-mini",
        input=build_messages(
            system_prompt=system_prompt,
            transcript=transcript,
            attachments=attachments,
            history=session.history,
        ),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": output_schema.__name__,
                "schema": output_schema.model_json_schema(),
            },
        },
    )

    return output_schema.model_validate_json(
        response.output_text
    )
```

Eso es todo el patrón. No hay nada más. La sofisticación está en haber hecho la decisión correcta, no en el código.

## **3. Diseñando los templates por tier**

Los tres templates Jinja2 comparten la estructura general (rol, contexto CAG, transcripción, formato de salida) y se diferencian en las instrucciones específicas y en el bloque de formato esperado. Un fragmento ilustrativo del template `developer`:

```
jinja2:

You are a senior software estimation expert producing estimates for the engineering team that will execute the project.
Your audience is technical: software engineers and tech leads who need component-level breakdowns to plan their work and identify risks.

{% include "_project_metadata.j2" %} {% include "_reference_estimates.j2" %}

When producing the estimate:

- Break down the work by technical component (backend, frontend, data layer, infrastructure, integrations).
- For each component, state hours estimate, technical risks, and the assumptions you are making about the stack.
- Surface uncertainty drivers explicitly: parts of the scope where small decisions can disrupt the estimate by more than 20%.
- Speak to engineers as peers. Use technical vocabulary without translating it.

Return ONLY valid JSON matching the schema provided. Do not include narrative text outside the JSON.
```

El equivalente para `executive`:

```
jinja2:

You are a senior software estimation expert producing estimates for executive stakeholders preparing strategic decisions or commercial proposals.
Your audience is non-technical leadership: heads of business, CTOs in oversight mode, sales directors. They need confident headline numbers and risk awareness, not technical detail.

{% include "_project_metadata.j2" %} {% include "_reference_estimates.j2" %}

When producing the estimate:

- Lead with a single cost range and a single duration range. No component-level breakdown.
- Provide an overall confidence level (low / medium / high) with one short justification.
- Surface only the top three risks that could materially affect the proposal.
- End with a go/no-go recommendation phrased as actionable executive guidance.
- Avoid technical jargon. If a stack decision matters, translate it into business terms (cost impact, timeline impact, hiring impact).

Return ONLY valid JSON matching the schema provided.
```

Tres detalles a notar.

- **Reutilización con** `include`**.** Los bloques compartidos (`project_metadata`, `reference_estimates`) viven en parciales que los tres templates importan. El día que cambia la definición del CAG estático, lo cambias en un sitio. Esto es disciplina estándar de templates pero es la primera cosa que se rompe cuando un equipo se apresura.
- **Las instrucciones se diferencian, el formato no se mezcla.** El template `developer` no se limita a "muestra más detalle"; le dice al modelo qué dimensiones componen ese detalle (componentes, riesgos, asunciones, drivers de incertidumbre). El template `executive` no dice "sé conciso"; especifica exactamente qué piezas componen una salida ejecutiva. El modelo trabaja mucho mejor cuando las instrucciones son específicas y diferenciadoras.
- **El schema actúa como segundo guardrail.** Aunque el template indique al modelo qué devolver, el `response_format` con `json_schema` lo fuerza a estructura. Si el LLM olvida una sección, la validación falla y el sistema lo detecta antes de que el usuario reciba algo defectuoso. Es la disciplina de la sesión 04 aplicada de forma diferenciada por tier.

## **4. Cómo gestionar la evolución de tiers**

Una pregunta legítima: ¿qué pasa cuando el producto descubre que necesita un cuarto tier? ¿Y un quinto? ¿Y cuando hay tiers compuestos del estilo "executive con detalle técnico" para CTOs que oscilan entre dos perfiles?

La respuesta no es añadir más entradas al diccionario `TIER_CONFIG` indefinidamente. Hay tres heurísticas de diseño que mantienen el patrón sano cuando el catálogo crece.

**Heurística 1 — Tres es el número adecuado para arrancar.** Tres tiers cubren la mayoría de los casos sin caer en la fragmentación que paraliza a equipos de producto. Si necesitas más, lo descubrirás por evidencia (usuarios pidiendo cosas que ningún tier sirve), no por anticipación.

**Heurística 2 — Tier compuesto es señal de tier mal definido.** Si te encuentras con la necesidad de un "executive con un poco de developer", probablemente el tier `executive` está mal especificado: le falta una sección de "appendix técnico" que un CTO querría ver al final. Antes de inventar un tier híbrido, revisa si el problema es de definición. Es casi siempre más barato refinar un tier que multiplicarlos.

**Heurística 3 — Nuevos tiers exigen evaluación, no intuición.** Cada tier nuevo es un nuevo template + un nuevo schema + nuevos casos de prueba. Sin un golden dataset que valide que el tier produce respuestas distintas y de calidad para sus usuarios reales, lo que estás añadiendo es complejidad sin valor verificable.

## **5. El antipatrón paralelo: el tier que solo cambia el tono**

Hay una forma de implementar el patrón "tier" que parece bien, funciona en la demo, y se rompe en producción. Consiste en mantener un único schema de salida y un único template, y limitarse a añadir una instrucción del tipo "responde de forma {tono} según el tier". Algo así:

```
jinja2

{% if tier == "executive" %} Respond in an executive tone, focused on strategic implications.
		{% elif tier == "pm" %} Respond in a project management tone, focused on phases and risks.
		{% else %} Respond in a technical tone with implementation detail.
{% endif %}
```

Funciona porque los modelos modernos son lo suficientemente capaces de adaptar el tono. Falla porque la **estructura de la respuesta** es la misma para todos los tiers, y la estructura es donde vive el valor de adaptación. El usuario ejecutivo sigue recibiendo una respuesta organizada por componentes técnicos, solo que con palabras menos técnicas. El usuario developer sigue recibiendo el "headline cost range" que no le interesa.

La regla operativa: **adaptar un sistema CAG a perfiles distintos significa adaptar la estructura de salida, no solo el tono**. Si el tier no cambia el schema Pydantic de la respuesta, lo más probable es que estés haciendo lock-in cosmético, no diseño de producto.

## **6. Cuándo un tier merece su propia pipeline: el ejemplo del modo investigación profunda**

Hasta aquí, los tres tiers comparten **la misma pipeline de ejecución**: una sola llamada al LLM con un template y un schema. Cambia el contenido del prompt y la forma del output, pero la mecánica es idéntica.

Hay un patrón superior que vale la pena conocer porque marca el techo del enfoque tier: un tier puede activar una **pipeline completamente distinta**. El ejemplo paradigmático lo ofrece OpenAI con su modo *Deep Research*: cuando el usuario activa esa modalidad, el sistema no solo usa un template diferente — invoca un modelo distinto (`o3-deep-research`), habilita web search por defecto, opera en modo `background` con tiempos de respuesta de minutos, y devuelve un informe largo con citas e índice estructurado.

Aplicado conceptualmente al `estimator`, el patrón se vería así:

```python
TIER_CONFIG = {
    "developer": {
        "pipeline": "single_call",
        "template": "estimate_developer.j2",
        "schema": DeveloperEstimate,
        "model": "gpt-4o-mini",
    },

    "pm": {
        "pipeline": "single_call",
        "template": "estimate_pm.j2",
        "schema": PmEstimate,
        "model": "gpt-4o-mini",
    },

    "executive": {
        "pipeline": "single_call",
        "template": "estimate_executive.j2",
        "schema": ExecutiveEstimate,
        "model": "gpt-4o-mini",
    },

    "research": {
        "pipeline": "deep_research",
        "template": "estimate_research.j2",
        "schema": ResearchEstimate,
        "model": "o3-deep-research",
        "tools": [
            "web_search",
            "code_interpreter",
        ],
        "background": True,
        "estimated_latency_seconds": 600,
        "estimated_cost_per_call_eur": 5.00,
    },
}
```

Y el orquestador del endpoint despacha por pipeline, no por template:

```python
PIPELINE_HANDLERS = {
    "single_call": run_single_call_pipeline,
    "deep_research": run_deep_research_pipeline,
}

@app.post("/sessions/{session_id}/estimate")
async def estimate(
    session_id: str,
    transcript: str = Form(...),
    attachments: list[UploadFile] | None = File(default=None),
    caller: CallerContext = Depends(get_caller_context),
):

    attachments = attachments or []

    session = await load_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    config = resolve_tier_config(caller.tier)

    pipeline_name = config["pipeline"]

    handler = PIPELINE_HANDLERS.get(pipeline_name)

    if handler is None:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown pipeline: {pipeline_name}"
        )

    return await handler(
        config=config,
        session=session,
        transcript=transcript,
        attachments=attachments,
        caller=caller,
    )
```

El tier `research` activa una pipeline que cuesta minutos (no segundos), euros (no céntimos), y devuelve un informe sustancialmente más rico que justifica el coste. La interfaz al usuario lo refleja: cuando elige `research`, el sistema le advierte explícitamente del tiempo de espera, le permite cerrar la pestaña y recibir el resultado por email, y le ofrece descargarlo en PDF al terminar.

La lección de diseño que viaja contigo: **el patrón tier escala desde "mismo motor, distinta presentación" hasta "motor completamente distinto". La elección entre estos dos extremos depende de cuánto valor adicional aporta la pipeline alternativa para los usuarios de ese tier**. No todos los productos justifican un modo investigación profunda. Pero saber que el patrón puede llevarte hasta ahí cambia cómo diseñas la abstracción desde el principio.

## **7. Anti-patrones frecuentes**

Tres errores que se ven repetidamente al implementar este patrón y que la arquitectura defendida aquí previene.

**Anti-patrón 1 — El tier vive en el frontend.** "Mi cliente envía un parámetro `tier` en el body de la petición y el servicio IA lo respeta". Es la forma más rápida de implementar el patrón y la más rápida de explotar: cualquier usuario puede enviar `tier=executive` y obtener acceso al modo más caro. El tier debe vivir en la BBDD del backend de negocio y ser propagado por un canal que el cliente final no pueda manipular (claim de JWT, header en red privada, sesión autenticada).

**Anti-patrón 2 — Un solo schema, branching de campos.** "Tengo un único `EstimateOutput` con todos los campos posibles, y el modelo rellena los que correspondan según el tier". El problema: el schema deja de ser un contrato. El modelo a veces rellena campos que no debería; el cliente tiene que saber qué campos esperar para cada tier; los validadores no pueden hacer su trabajo. Schemas separados por tier son más código pero el contrato queda nítido.

**Anti-patrón 3 — Los templates por tier divergen sin disciplina.** Empiezas con tres templates compartiendo el 80% del contenido. Tres meses después cada uno ha evolucionado por su cuenta, los bloques compartidos están duplicados con pequeñas variaciones, y un cambio en la definición del contexto CAG implica tocar tres archivos casi idénticos. La disciplina de parciales con `include` (vista en sesión 04) no es opcional cuando los templates se multiplican: es la diferencia entre mantener tres variantes y mantener tres versiones que divergen.

## **8. Resumen**

Cuatro afirmaciones operativas para llevarte:

1. **Adaptar un sistema CAG a múltiples perfiles de usuario es desarrollo web normal, no IA avanzada.** Una columna `tier`, un selector de template, un schema por tier. La sofisticación vive en haber tomado la decisión correcta, no en la maquinaria.
2. **El tier vive en la BBDD del backend de negocio y se propaga al servicio IA por un canal autenticado.** Nunca como parámetro libre desde el cliente.
3. **Adaptar a un perfil significa adaptar la estructura de salida, no solo el tono.** Schemas Pydantic distintos por tier es la prueba de que el patrón está bien implementado.
4. **El patrón escala desde "misma pipeline, distinto template" hasta "pipeline completamente distinta".** Conocer ese rango de aplicación cambia cómo diseñas la abstracción desde el primer día.

Implementar esto bien convierte un sistema que devuelve la misma respuesta a todo el mundo en una herramienta de producto que se adapta a cómo cada usuario va a consumir su salida. Y lo hace sin tocar el modelo, sin reentrenar nada y sin añadir complejidad innecesaria.