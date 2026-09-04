# Mínimo privilegio, validación de acciones y auditoría de agentes

Creada: 20 de julio de 2026 21:13
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S14. Sistemas multi-agente y patrones avanzados (https://app.notion.com/p/S14-Sistemas-multi-agente-y-patrones-avanzados-3a3ea9ca03c4800f98e8fdae96ec7f6f?pvs=21)

Hasta ahora vuestros agentes leen. El buscador consulta presupuestos, el generador calcula, el validador comprueba coherencia. Si uno de ellos alucina, produce una estimación mala, y una estimación mala la caza el validador o la caza el humano en el gate. El coste de un error es un número equivocado.

Eso cambia por completo el día que un agente **escriba**.

Alguien va a añadir la tool que faltaba. `save_estimate`, para persistir el resultado. O `update_budget_status`, para marcar un presupuesto como usado. O `send_estimate_email`, porque estaría bien automatizar el envío al cliente. Y en ese momento tenéis un componente gobernado por un modelo de lenguaje —una máquina que a veces alucina con total aplomo— con permiso para modificar los datos de vuestra empresa o para mandar correos en su nombre.

El coste de un error deja de ser un número equivocado. Pasa a ser una fila borrada, un correo enviado a quien no debía, un estado corrupto en producción.

Este artículo trata de contener eso. Y la tesis es incómoda de entrada: **la contención no puede vivir en el prompt.**

## **Por qué el prompt no es un mecanismo de seguridad**

La reacción instintiva es escribir en el system prompt algo como *"nunca borres datos"* o *"solo debes leer, nunca escribir"*. Es comprensible y es inútil.

Un system prompt es una **instrucción**, no una **restricción**. El modelo lo toma como una entrada más, la pondera junto al resto del contexto, y la mayoría de las veces la respeta. La mayoría de las veces. Un prompt inusual, una transcripción con contenido que empuja en otra dirección, una cadena de razonamiento que se convence a sí misma de que esta vez la regla no aplica: cualquiera de esas cosas puede llevar al modelo a hacer justo lo que le pedisteis que no hiciera.

Comparadlo con cómo protegéis cualquier otra cosa. No confiáis en que el frontend "no envíe" un campo prohibido: lo rechazáis en el backend. No confiáis en que un usuario "no acceda" a un recurso ajeno: lo comprobáis con una autorización. La regla que lleváis toda la vida aplicando —**no confíes en el cliente**— se aplica aquí sin una sola modificación. **El modelo es el cliente.** Es una entrada no confiable que propone acciones, y las entradas no confiables se validan en una capa que el cliente no controla.

Todo lo que sigue es esa idea, aplicada tres veces.

![art_6_fig-01-privilegio-validacion-auditoria.png](https://media1-production-mightynetworks.imgix.net/asset/87a6af49-7653-493d-a878-88ed1aa3763d/art_6_fig-01-privilegio-validacion-auditoria.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Capa 1: mínimo privilegio, en el reparto de tools**

La primera contención ya la construisteis, aunque no la llamasteis seguridad. Cuando le disteis al `budget_searcher` solo `search_budgets` y al `estimate_generator` solo `calculate_estimate`, aplicasteis mínimo privilegio: cada agente accede únicamente a lo que su función necesita.

El principio es viejo y es el mismo de siempre: si un agente no tiene una tool en la mano, no puede usarla mal por mucho que alucine. Un agente sin `save_estimate` no va a corromper la base de datos ni equivocándose ni siendo manipulado, porque la capacidad no existe en su mundo.

La consecuencia de diseño es que **el reparto de tools deja de ser una comodidad y pasa a ser una decisión de seguridad**. Y eso obliga a nombrar la naturaleza de cada tool, que es un ejercicio que conviene hacer explícito:

```python
from enum import Enum

class ToolRisk(str, Enum):
    PURE = "pure"          # no side effects: calculate_estimate
    READ = "read"          # reads state: search_budgets
    WRITE = "write"        # mutates state: save_estimate
    EXTERNAL = "external"   # acts on the world: send_estimate_email

AGENT_TOOL_GRANTS: dict[str, set[str]] = {
    "requirements_extractor": set(),
    "budget_searcher": {"search_budgets"},
    "estimate_generator": {"calculate_estimate"},
    "coherence_validator": {"validate_estimate"},
    "persistence_agent": {"save_estimate"},
}
```

Fijaos en una decisión que va más allá del reparto: hemos sacado la escritura a un `persistence_agent` propio. Es deliberado. Concentrar las tools de escritura en un único agente pequeño, en lugar de repartirlas entre los que ya hacen otras cosas, significa que **la superficie peligrosa de todo el sistema cabe en un fichero que podéis leer entero en un minuto**. La mayoría de vuestros agentes se quedan en `read` y `pure`, y no hace falta vigilarlos con la misma intensidad. Es la misma lógica por la que aisláis el código que maneja pagos: no porque el resto no importe, sino porque concentrar el riesgo lo hace revisable.

El grant es un dato, no una instrucción, y eso permite comprobarlo en el arranque:

```python
def verify_tool_grants(graph_agents: dict[str, Agent]) -> None:
    """Fail at startup if an agent was wired with a tool it was not granted."""
    for name, agent in graph_agents.items():
        granted = AGENT_TOOL_GRANTS.get(name, set())
        actual = {tool.name for tool in agent.tools}
        if not actual.issubset(granted):
            raise ConfigurationError(
                f"Agent '{name}' has ungranted tools: {actual - granted}"
            )
```

Un agente al que por error se le cableó una tool que no le corresponde no llega a producción: rompe el despliegue. Habéis convertido una política de seguridad en una invariante que el sistema verifica solo.

## **Capa 2: validar la acción, no solo tenerla permitida**

El mínimo privilegio decide **si** un agente puede usar una tool. No dice nada sobre **con qué argumentos**.

El `persistence_agent` tiene permiso para `save_estimate`. Bien. ¿Y si el modelo decide guardar una estimación de -400 horas? ¿O sobrescribir un `estimation_id` que no es el de esta ejecución? ¿O guardar un objeto al que le falta la mitad de los campos? Tiene permiso para escribir; nadie dijo que tuviera permiso para escribir *cualquier cosa*.

Hace falta un guardia entre la intención del agente y la ejecución real: un punto por el que pasa toda acción con efectos, y que la aprueba o la rechaza **antes** de que toque nada.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ActionRequest:
    agent: str
    tool: str
    args: dict

@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str

def guard_action(request: ActionRequest) -> GuardDecision:
    # 1. Privilege: is this tool granted to this agent at all?
    if request.tool not in AGENT_TOOL_GRANTS.get(request.agent, set()):
        return GuardDecision(False, f"{request.agent} is not granted {request.tool}")

    # 2. Argument validation: rules the tool itself enforces, regardless of caller.
    if request.tool == "save_estimate":
        estimate = request.args.get("estimate", {})
        if estimate.get("hours", 0) <= 0:
            return GuardDecision(False, "estimate hours must be positive")
        if estimate.get("estimation_id") != current_estimation_id.get():
            return GuardDecision(False, "estimation_id does not match this run")

    return GuardDecision(True, "ok")
```

Tres cosas que quiero destacar.

**El guardia es código plano y determinista.** Nada de LLM validando a otro LLM: eso solo añade una segunda máquina falible al problema. Las reglas de qué es una acción válida son reglas de negocio, y las reglas de negocio se escriben, se testean y se razonan. Un test unitario puede cubrir el guardia por completo; no puede cubrir un prompt.

**La comprobación de** `estimation_id` **es la que de verdad importa** y la que más se olvida. Un agente que puede escribir sobre *cualquier* `estimation_id` es un agente que, ante el input adecuado, modifica la estimación de otro cliente. Atar cada acción a la ejecución en curso —el `estimation_id` que ya usáis como `thread_id` del checkpointer— convierte un permiso genérico en un permiso acotado a este contexto. Es el equivalente a no dejar que un usuario edite recursos que no son suyos.

**Las acciones irreversibles piden algo más que validación.** Guardar una fila se puede deshacer. Enviar un correo al cliente, no. Para esa clase de acciones, la validación automática no basta: la decisión correcta es enrutarlas al gate humano que ya construisteis. Y aquí las dos mitades de la sesión encajan: **el human-in-the-loop no era solo para la baja confianza; es también el mecanismo de aprobación de las acciones que no admiten marcha atrás.** No hace falta inventar nada nuevo. La misma pausa, disparada por otra señal.

## **Capa 3: auditoría, porque lo que no se registra no ocurrió**

Las dos primeras capas previenen. La tercera no previene nada: **hace que todo sea reconstruible después**. Y es la que separa un sistema que podéis operar de uno que solo podéis rezar para que funcione.

Cuando un cliente os pregunte por qué su estimación cambió, o cuando queráis entender por qué el sistema hizo algo raro el martes a las tres, la respuesta no puede ser "no sé, el modelo decidió eso". Tiene que ser un registro que podáis leer.

La regla es tajante: **toda acción con efectos se registra, incluidas las que el guardia denegó.** Las denegadas son, de hecho, las más valiosas: son el sistema diciéndoos exactamente dónde un agente intentó salirse de su carril. Una tasa de denegaciones que sube es una alarma temprana, mucho antes de que nada se rompa.

```python
async def execute_guarded(request: ActionRequest, tool: Callable) -> ToolResult:
    decision = guard_action(request)

    log = logger.bind(
        agent=request.agent,
        tool=request.tool,
        args=redact_sensitive(request.args),
        estimation_id=current_estimation_id.get(),
        allowed=decision.allowed,
    )

    if not decision.allowed:
        log.warning("action_denied", reason=decision.reason)
        raise ActionDeniedError(decision.reason)

    result = await tool(**request.args)
    log.info("action_executed", result_summary=summarize(result))
    return result
```

El registro lleva el `estimation_id`, que es —otra vez— el mismo identificador que atraviesa las tres capas y vuestras trazas. Con eso, reconstruir todo lo que hizo el sistema para un caso concreto es una consulta, no una arqueología. `redact_sensitive` está ahí por una razón que no conviene aprender por las malas: un log de auditoría que copia datos personales del cliente en texto plano es él mismo un problema de privacidad. Auditáis la *acción* —quién, qué tool, con qué forma de argumentos, con qué resultado— no el contenido íntegro de los datos.

## **Qué es y qué no es "sandboxing" aquí**

La palabra sandboxing arrastra una imagen concreta: contenedores, máquinas virtuales, procesos aislados sin acceso a la red. Conviene ser honestos sobre lo que esta sesión cubre y lo que no, porque confundirlo genera una falsa sensación de seguridad, que es peor que no tener ninguna.

![art_6_fig-02-dos-fronteras-seguridad.png](https://media1-production-mightynetworks.imgix.net/asset/808b6655-2730-4e83-9298-f6f1eb73e80f/art_6_fig-02-dos-fronteras-seguridad.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Todo lo de este artículo vive **a nivel de aplicación**, en vuestro código Python. Responde a una pregunta: *qué puede hacer este agente dentro de la lógica de la aplicación*. Y es la capa correcta para el privilegio, la validación de argumentos y la auditoría, porque esas son decisiones de dominio: qué es una escritura válida, qué acciones son irreversibles, qué hay que registrar. Ninguna de esas preguntas la puede responder un contenedor.

Hay una segunda frontera, y responde a una pregunta distinta: *qué daño puede hacer el proceso si un agente se comporta de forma imprevista*. Aislamiento de proceso, políticas de red que impidan que un agente llame a donde no debe, límites de CPU y memoria y tiempo, gestión de secretos. Eso **no** vive en vuestro código de aplicación: vive en el runtime y en el despliegue. Es material de la puesta en producción, y llega en la siguiente sesión.

La relación entre ambas fronteras es la que importa: **no se sustituyen, se complementan, y ninguna sola es suficiente**. La validación de acciones no os protege de un agente que ejecuta código arbitrario a través de una tool mal diseñada; para eso hace falta aislamiento de proceso. Y el aislamiento de proceso no os protege de un agente que guarda una estimación negativa con argumentos perfectamente válidos desde el punto de vista del sistema operativo; para eso hace falta la validación de dominio. Un sistema serio necesita las dos. Esta sesión os deja la primera montada y bien; la segunda tiene su propio sitio.

## **Cierre del módulo: lo que habéis construido**

Con esto el módulo de orquestación de agentes está completo, y merece la pena mirar hacia atrás un momento, porque el recorrido tiene una forma.

Empezasteis con un grafo lineal que hacía su trabajo. Lo cuestionasteis: ¿por qué complicarlo? Y solo cuando aparecieron límites concretos —prompts sobrecargados, rutas que dependen del caso, decisiones que el código no puede prever— lo reorganizasteis en un supervisor que enruta y unos agentes que se especializan. Elegisteis cómo se comunican, sabiendo que la pizarra compartida que ya teníais era el punto de partida correcto. Le disteis al sistema la capacidad de **pararse y pedir ayuda** cuando sabe que no sabe, apoyándoos en el mismo checkpointer de siempre. Aprendisteis a hacer que los agentes **compitan** cuando el desacuerdo es información. Y le habéis puesto **límites a lo que cada agente puede tocar**, validación a lo que hace y un registro de todo ello.

Nada de eso fue un paradigma nuevo. Cada pieza resultó ser un principio de ingeniería que ya conocíais, aplicado a un componente que a veces alucina: separación de responsabilidades, contratos entre capas, no confiar en el cliente, persistencia para sobrevivir a los fallos, defensa en profundidad. La capa genuinamente nueva era pequeña. Ese era el trato desde el principio.

Vuestro sistema de estimación está funcionalmente completo. Recibe una transcripción y devuelve una estimación defendible, con un rango, con supuestos explícitos, con una persona en el bucle cuando hace falta, y sin que ningún agente pueda hacer más de lo que le corresponde.

Funcionalmente completo, sí. Pero corre en vuestra máquina. Nadie lo ha desplegado, nadie lo está monitorizando, nadie ha medido su latencia bajo carga real ni ha puesto un límite a lo que cuesta al mes. La otra mitad de "en producción" —la que empieza donde termina el código y empieza la operación— es lo que queda por delante.