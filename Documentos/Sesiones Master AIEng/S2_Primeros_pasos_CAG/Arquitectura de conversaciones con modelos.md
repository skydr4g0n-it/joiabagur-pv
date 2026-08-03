# Arquitectura de conversaciones con modelos

Creada: 30 de abril de 2026 21:26
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S2. Primeros pasos de arquitectura CAG (https://app.notion.com/p/S2-Primeros-pasos-de-arquitectura-CAG-352ea9ca03c4800aa421ca55b02ceccb?pvs=21)

## **La interfaz real con un LLM: un array de mensajes**

Cuando usas ChatGPT o Claude desde el navegador, la experiencia se siente como una conversación fluida. Escribes algo, el modelo responde, tú replicas, el modelo vuelve a responder. Parece que el modelo "recuerda" lo que le dijiste hace tres turnos.

Pero esa es una ilusión de la interfaz. Por debajo, cada vez que envías un mensaje, la aplicación empaqueta **toda la conversación completa** — desde el primer mensaje hasta el último — en un único array de objetos JSON y lo envía al modelo. El modelo no tiene memoria entre llamadas. No "recuerda" nada. Lee toda la conversación de principio a fin, genera una respuesta, y se olvida de todo. En la siguiente llamada, vuelve a recibir todo el historial y lo procesa como si fuera la primera vez.

Esta es posiblemente la diferencia más importante entre la percepción de usuario y la realidad técnica de los LLMs, y como desarrolladores que construimos sobre estas APIs necesitamos trabajar con la realidad, no con la percepción.

La interfaz real con cualquier LLM comercial es un array de mensajes con esta forma:

```python
messages = [
    {"role": "system", "content": "Instrucciones para el modelo..."},
    {"role": "user", "content": "Primera pregunta del usuario"},
    {"role": "assistant", "content": "Primera respuesta del modelo"},
    {"role": "user", "content": "Segunda pregunta del usuario"},
    {"role": "assistant", "content": "Segunda respuesta del modelo"},
    {"role": "user", "content": "Tercera pregunta del usuario"},
    # → el modelo genera la respuesta a esta última pregunta
]
```

Todo lo que el modelo sabe sobre la interacción está contenido en este array. Si no está aquí, no existe. Entender esta estructura y saber gestionarla es lo que separa una integración funcional de una integración profesional.

## **Los tres roles: system, user, assistant**

Cada mensaje del array tiene un rol que indica al modelo quién lo dice y cómo debe interpretarlo. Aunque parecen simples etiquetas, cada rol tiene un propósito arquitectónico distinto.

### **System: las reglas del juego**

El mensaje con rol `system` define el comportamiento global del modelo para toda la conversación. Es la única parte del contexto que el modelo interpreta como instrucciones de configuración, no como contenido conversacional.

```python
{
    "role": "system",
    "content": """Eres un consultor senior de software especializado en
    estimación de proyectos. Analiza transcripciones de reuniones y genera
    estimaciones detalladas basándote en los ejemplos de referencia
    proporcionados..."""
}
```

En el artículo anterior vimos cómo diseñar un system prompt efectivo para nuestro sistema de estimaciones. Aquí el punto relevante es otro: el system prompt se envía en **cada llamada**. Si tu aplicación tiene una conversación de 20 turnos, el system prompt se envía 20 veces, consumiendo tokens cada vez. Esta es una razón más para que sea conciso y preciso — cada palabra innecesaria se paga multiplicada por el número de interacciones.

Hay un detalle que los proveedores manejan de forma diferente. En OpenAI, puedes incluir múltiples mensajes `system` intercalados en la conversación. En Anthropic, el system prompt se pasa como parámetro separado, fuera del array de mensajes. Tu código debe contemplar estas diferencias si soportas múltiples proveedores.

### **User: lo que pide el ser humano**

Los mensajes con rol `user` representan las entradas del usuario. En nuestro sistema de estimaciones, el primer mensaje de usuario contiene la transcripción de la reunión. En un sistema conversacional, cada turno del usuario añade un nuevo mensaje con este rol.

```python
{
    "role": "user",
    "content": "En la reunión con el cliente se discutió la necesidad de una
    plataforma de reservas online para su cadena de restaurantes..."
}
```

### **Assistant: lo que dijo el modelo**

Los mensajes con rol `assistant` contienen las respuestas previas del modelo. Aquí viene la parte contraintuitiva: cuando construyes una conversación multi-turno, **tú eres responsable de guardar las respuestas del modelo e incluirlas en las llamadas siguientes**. El modelo no lo hace por ti.

Si el modelo respondió con una estimación en el turno anterior y el usuario pide "ajusta las horas de diseño a 50", el modelo necesita ver su propia respuesta anterior en el array de mensajes para saber qué estimación está ajustando. Si no la incluyes, el modelo no tiene idea de qué estimación habla el usuario.

```python
{
    "role": "assistant",
    "content": "## Estimación: Plataforma de Reservas\\n\\n### Desglose:\\n
    1. Diseño UI/UX: 40 horas..."
}
```

## **Single-turn vs. multi-turn: dos modelos de interacción**

Nuestro sistema de estimaciones puede funcionar en dos modos, y la elección tiene implicaciones directas en cómo gestionamos los mensajes.

### **Modo single-turn: una pregunta, una respuesta**

En este modo, cada llamada al modelo es independiente. El usuario envía una transcripción, el modelo devuelve una estimación, y la interacción termina. No hay historial que gestionar.

```python
# Single-turn: no hay historial
messages = [
    {"role": "system", "content": system_prompt_con_contexto},
    {"role": "user", "content": transcripcion_de_reunion}
]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
)
```

Este es el modo que implementamos en el ejercicio pre-sesión y es perfectamente válido para muchos casos de uso. El usuario pega una transcripción, obtiene una estimación, y si quiere otra, pega otra transcripción desde cero.

La ventaja es la simplicidad: no hay estado que gestionar entre peticiones. La desventaja es que no puedes iterar sobre una estimación ("sube las horas de backend", "añade una fase de testing") sin repetir todo el contexto desde cero.

### **Modo multi-turn: conversación iterativa**

En este modo, el usuario y el modelo mantienen una conversación donde cada turno construye sobre los anteriores. El usuario pide una estimación, la revisa, pide ajustes, el modelo los aplica, el usuario pide más cambios.

```python
# Multi-turn: el historial crece con cada interacción
conversation = [
    {"role": "system", "content": system_prompt_con_contexto},
    {"role": "user", "content": "Estima este proyecto: [transcripción]"},
    {"role": "assistant", "content": "## Estimación: ...\\n1. Diseño: 40h..."},
    {"role": "user", "content": "Sube diseño a 60 horas y añade testing"},
    {"role": "assistant", "content": "## Estimación actualizada: ...\\n1. Diseño: 60h..."},
    {"role": "user", "content": "¿Cuál sería el equipo ideal para esto?"},
    # → el modelo responde con contexto completo de toda la conversación
]
```

La ventaja es una experiencia mucho más rica: el usuario refina la estimación en un diálogo natural. La desventaja es que la conversación consume tokens de forma acumulativa: cada turno nuevo incluye todos los turnos anteriores, y el coste crece con cada interacción.

## **Gestión del historial en memoria**

En modo multi-turn, necesitas un mecanismo para almacenar y gestionar el historial de la conversación. En la fase CAG de nuestro proyecto, la implementación más directa es mantener el historial en memoria — una lista de Python que crece con cada turno.

```python
class ConversationManager:
    def __init__(self, system_prompt: str):
        self.messages = [
            {"role": "system", "content": system_prompt}
        ]

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    def get_messages(self) -> list:
        return self.messages.copy()
```

La implementación es intencionadamente simple. No hay persistencia en disco, no hay base de datos. Si el servidor se reinicia, las conversaciones se pierden. Esto es aceptable en esta fase del proyecto — la persistencia y la memoria a largo plazo son temas de sesiones posteriores.

Lo que sí necesitas gestionar desde el principio es qué pasa cuando la conversación crece demasiado.

## **El problema del crecimiento: cuándo el historial no cabe**

Cada turno de conversación añade tokens al array de mensajes. En nuestro sistema de estimaciones, un turno típico puede consumir entre 1.000 y 4.000 tokens (la pregunta del usuario más la respuesta del modelo). Con un system prompt que ya incluye las estimaciones de referencia (5.000-30.000 tokens según vimos en el artículo anterior), la ventana de contexto se llena progresivamente.

Hagamos las cuentas para un caso concreto:

```
System prompt con contexto CAG:     15.000 tokens
Turno 1 (user + assistant):          3.000 tokens
Turno 2 (user + assistant):          2.500 tokens
Turno 3 (user + assistant):          2.000 tokens
Turno 4 (user + assistant):          3.500 tokens
Turno 5 (user + assistant):          2.000 tokens
Espacio para respuesta del turno 6:  3.000 tokens
─────────────────────────────────────────────────
Total:                               31.000 tokens
```

Con 31.000 tokens estamos lejos del límite de 128K, pero el crecimiento es real y en conversaciones largas o con contextos CAG más pesados se convierte en un problema. No solo un problema de espacio, sino de calidad: como vimos en el artículo anterior, más tokens significa más coste y menos atención efectiva del modelo sobre cada fragmento de información.

Existen tres estrategias principales para gestionar este crecimiento.

### **Estrategia 1: Ventana deslizante**

La más simple. Mantienes solo los últimos N turnos de la conversación, descartando los más antiguos. El system prompt siempre se conserva.

```python
def get_messages_windowed(self, max_turns: int = 10) -> list:
    system = [self.messages[0]]  # Siempre conservar el system prompt
    history = self.messages[1:]  # Todo lo demás

    # Mantener solo los últimos max_turns pares (user + assistant)
    if len(history) > max_turns * 2:
        history = history[-(max_turns * 2):]

    return system + history
```

Es predecible y fácil de implementar, pero tiene un problema: si el usuario dijo algo importante en el turno 1 y estamos en el turno 15, esa información desaparece del contexto. El modelo "olvidará" decisiones tempranas.

### **Estrategia 2: Resumen acumulativo (compactación)**

En lugar de descartar turnos antiguos, los resumes en un mensaje compacto que se mantiene al principio de la conversación. Cuando el historial alcanza cierto tamaño, generas un resumen usando el propio LLM y reemplazas los turnos antiguos por ese resumen.

```
[system prompt]
[resumen de turnos 1-8: "El usuario solicitó una estimación para una
 plataforma de reservas. Se acordó un equipo de 3 personas, duración
 de 8 semanas. Se ajustaron las horas de diseño de 40 a 60."]
[turno 9: user]
[turno 9: assistant]
[turno 10: user]
→ modelo responde
```

La ventaja es que conservas la información esencial de toda la conversación sin consumir el espacio de los turnos completos. La desventaja es que el resumen es una operación adicional que consume tokens y tiempo — y la calidad del resumen depende de la calidad de la instrucción de resumir.

### **Estrategia 3: Híbrida con priorización**

Combinas la ventana deslizante con marcado de turnos importantes. Ciertos turnos se marcan como "ancla" (por ejemplo, el turno donde se definió el alcance del proyecto o donde se tomó una decisión clave) y nunca se descartan, mientras que los turnos intermedios sí se descartan cuando el historial crece.

```
[system prompt]
[turno 1: definición del proyecto — ANCLA, nunca se descarta]
[turno 5: decisión sobre equipo — ANCLA, nunca se descarta]
[turnos 8-10: últimos turnos completos — ventana deslizante]
→ modelo responde
```

Esta estrategia es la más sofisticada y la que mejor resultados da en producción, pero requiere criterio para decidir qué turnos son "ancla". En nuestro sistema de estimaciones, un turno donde el usuario aprueba el desglose de tareas es claramente un ancla. Un turno donde pregunta "¿puedes reformular el resumen?" no lo es.

Para la fase actual del proyecto, la ventana deslizante es suficiente. Las estrategias más sofisticadas las abordaremos cuando el proyecto lo necesite.

## **El patrón request-response en la práctica**

Poner todo junto en código para nuestro sistema de estimaciones tiene esta forma:

```python
# services/llm_service.py

async def generate_estimation(
    transcription: str,
    conversation_history: list | None = None
) -> dict:

    system_prompt = build_system_prompt()  # Incluye contexto CAG

    if conversation_history:
        # Multi-turn: usar el historial existente
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": transcription})
    else:
        # Single-turn: solo system + user
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcription}
        ]

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages
    )

    assistant_message = response.choices[0].message.content

    return {
        "estimation": assistant_message,
        "model": settings.LLM_MODEL,
        "usage": {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens
        }
    }
```

Observa que la función acepta un historial opcional. Si viene vacío o nulo, funciona en modo single-turn. Si viene con turnos previos, funciona en modo multi-turn. El router decide qué modo usar según la petición del cliente; el servicio no necesita saber por qué.

Esta separación es coherente con la estructura FastAPI que definimos: el servicio no gestiona estado HTTP. El estado conversacional (el historial) vive fuera — en el router, en el cliente, o en un middleware de sesión. El servicio solo recibe mensajes y devuelve respuestas.

## **Diferencias entre proveedores que afectan a tu código**

La estructura `messages` con roles `system/user/assistant` es un estándar de facto en la industria, pero los proveedores tienen diferencias que tu código debe contemplar si soportas más de uno.

**System prompt.** OpenAI acepta el system prompt como un mensaje más dentro del array. Anthropic lo recibe como parámetro separado de la llamada (`system="..."`), fuera del array de mensajes. Si tu servicio abstrae múltiples proveedores, necesitas separar el system prompt del resto de mensajes antes de hacer la llamada.

**Alternancia estricta de roles.** Algunos modelos requieren que los mensajes alternen estrictamente entre `user` y `assistant`. Dos mensajes consecutivos de `user` producen un error. Si tu lógica de negocio necesita enviar información adicional al modelo entre turnos (por ejemplo, resultados de una herramienta), necesitas consolidarla en un solo mensaje de `user` o usar el rol `tool` que algunos proveedores soportan.

**Tokens de respuesta.** El parámetro `max_tokens` (o equivalente) limita cuántos tokens puede generar el modelo en su respuesta. Si tu estimación requiere un desglose extenso y el límite es demasiado bajo, la respuesta se cortará abruptamente. Para estimaciones de software, un valor de 2.000-4.000 tokens suele ser suficiente. Configúralo explícitamente en lugar de depender del valor por defecto del proveedor, que puede variar.

**Nombre del campo de respuesta.** OpenAI devuelve la respuesta en `response.choices[0].message.content`. Anthropic la devuelve en `response.content[0].text`. Si abstraes proveedores, tu servicio necesita normalizar estas diferencias.

Estas diferencias parecen menores cuando trabajas con un solo proveedor, pero se convierten en una fuente constante de bugs si soportas varios sin una capa de abstracción adecuada. En la Sesión 03 veremos patrones de diseño para wrappers de modelos que resuelven exactamente esto.

## **De la conversación al producto: consideraciones de diseño**

Más allá de la implementación técnica, hay decisiones de diseño de producto que afectan a cómo estructuras la conversación.

**¿Tu sistema es conversacional o transaccional?** Nuestro estimador en su forma más básica es transaccional: el usuario envía una transcripción, obtiene una estimación. Pero si añadimos la capacidad de refinar la estimación en un diálogo, se convierte en conversacional. Ambos modelos son válidos, pero la implementación es diferente. Un sistema transaccional no necesita gestionar historial. Uno conversacional sí.

**¿Quién controla el contexto de referencia?** En nuestra arquitectura CAG, el contexto de estimaciones históricas se inyecta automáticamente en cada llamada. El usuario no lo ve ni lo controla. Pero podrías diseñar una variante donde el usuario selecciona qué presupuestos históricos quiere usar como referencia. Eso cambia la estructura del prompt: los datos de referencia dejan de ser parte del system prompt y pasan a ser parte del mensaje del usuario.

**¿Cómo indicas al usuario los límites del modelo?** Si la conversación es muy larga y empiezas a truncar historial, el modelo puede "olvidar" decisiones anteriores. Gestionar esta expectativa — informar al usuario cuando se acerca al límite, ofrecer la opción de "reiniciar" la conversación con un resumen — es una decisión de producto, no solo de ingeniería.

## **Resumen**

- **Cada llamada a un LLM es stateless.** El modelo no recuerda nada entre llamadas. Todo el contexto de la conversación debe enviarse completo en cada petición como un array de mensajes.
- **Los tres roles tienen funciones distintas.** `system` configura el comportamiento global, `user` contiene las peticiones del humano, `assistant` preserva las respuestas anteriores del modelo. Los tres juntos forman la "memoria" de la conversación.
- **Single-turn es suficiente para empezar.** Nuestro estimador funciona perfectamente como sistema transaccional: una transcripción entra, una estimación sale. La conversación multi-turn añade valor (refinamiento iterativo) pero también complejidad (gestión de historial, truncamiento, coste acumulativo).
- **El historial crece y hay que gestionarlo.** Ventana deslizante para empezar, resumen acumulativo o estrategia híbrida cuando el proyecto lo requiera. La clave es no dejar que el historial crezca sin control.
- **Los proveedores no son idénticos.** System prompt como mensaje vs. como parámetro, alternancia estricta de roles, formatos de respuesta diferentes. Tu código debe contemplar estas diferencias si soportas más de un proveedor.
- **La arquitectura de conversación es una decisión de producto.** Transaccional o conversacional, contexto visible o invisible para el usuario, gestión de expectativas cuando el modelo "olvida". Estas decisiones se toman con el product owner, no solo en el IDE.