# Cuánto cuesta un agente

Creada: 7 de julio de 2026 11:21
Módulo: M5. Orquestación de agentes (https://app.notion.com/p/M5-Orquestaci-n-de-agentes-345ea9ca03c48012a1b2c0abb8da7a31?pvs=21)
Sesión: S12. Orquestación de Agentes (https://app.notion.com/p/S12-Orquestaci-n-de-Agentes-394ea9ca03c4809baf0bdfe714f24cc8?pvs=21)

Un agente hace el mismo trabajo que un pipeline producir una estimación a partir de una transcripción y puede costar varias veces más. No es un defecto de implementación: es el precio estructural de la autonomía. El problema es que "el agente es más caro" no es un número con el que puedas presupuestar. Este artículo va de convertir esa frase vaga en algo medible: de dónde sale el sobrecoste, cómo instrumentarlo con precisión, y qué palancas tienes para controlarlo.

El escenario, para situarnos: un agente de estimación que, dada una transcripción, usa tres tools `search_budgets`, `calculate_estimate`, `validate_estimate` iterando en un bucle hasta producir el resultado. Su alternativa es un pipeline fijo que hace los mismos pasos en orden predeterminado. Compararemos el coste de ambos sobre el mismo trabajo.

## **De dónde sale el sobrecoste**

El sobrecoste de un agente no viene de un sitio, sino de cuatro que se suman.

**Más llamadas al modelo.** Un pipeline hace una o dos llamadas por estimación. Un agente hace una por cada vuelta del bucle: decidir, ejecutar tools, observar, volver a decidir. Ocho vueltas son ocho llamadas donde el pipeline hacía dos. Ya ahí tienes un factor de cuatro en número de llamadas.

**El contexto crece en cada vuelta, y es el factor dominante.** Este es el que la gente subestima. En cada iteración, el agente reenvía al modelo todo lo acumulado hasta el momento: la transcripción, las decisiones previas, y cada observación de cada tool. La octava llamada no cuesta como la primera; cuesta como la primera más siete rondas de observaciones arrastradas. Los tokens de entrada, que son los que más se facturan en volumen, crecen vuelta a vuelta. Un bucle que acumula tiene un coste que no es lineal en el número de pasos, sino que engorda con cada uno.

**Tokens de razonamiento.** Los modelos de razonamiento gastan tokens internos deliberando antes de responder, y esos tokens se facturan. En un agente, el modelo razona en cada vuelta —qué tool usar, cómo interpretar la observación—, así que ese coste se paga repetidamente, no una sola vez.

**Exploración y reintentos.** Un agente puede tomar caminos subóptimos: reformular una búsqueda que vino pobre, deshacer una línea que no llevaba a nada. Cada uno de esos pasos es correcto es el agente adaptándose pero cuesta tokens que un pipeline, al no explorar, no gasta.

Ninguno de estos cuatro es evitable del todo; son la contrapartida de la flexibilidad. Pero todos son medibles, y el segundo el crecimiento del contexto es donde está la mayor parte del dinero y, por tanto, la mayor palanca.

## **La cuenta del 5x**

Pongamos números aproximados sobre una transcripción compleja, para ver de dónde sale el multiplicador.

El pipeline hace dos llamadas reformular y generar con un contexto acotado y estable. Llamémoslo una unidad de coste base.

El agente, sobre la misma transcripción con cuatro componentes, da del orden de seis a ocho vueltas. Las primeras llamadas son baratas, pero las últimas arrastran todas las observaciones previas: cuatro búsquedas de presupuestos, sus resultados, quizá una reformulación, el cálculo, la validación. Si a eso le sumas los tokens de razonamiento de cada vuelta, el total de tokens facturados acaba siendo varias veces el del pipeline. Cinco veces es una cifra realista para un caso complejo; puede ser menos en casos simples y más en los que el agente se enreda.

Con números redondos e ilustrativos se ve el mecanismo. Supón que el pipeline consume unos 8.000 tokens en total entre sus dos llamadas. El agente da ocho vueltas, y sus tokens de entrada no son constantes: la primera llamada envía solo la transcripción, digamos 2.000 tokens; pero cada vuelta añade la observación anterior, así que la entrada sube a 4.000, luego a 6.000, y para la octava ronda ronda los 9.000, porque arrastra todo lo visto. Promediando, son del orden de 40.000 tokens de entrada, más unos 8.000 de salida y razonamiento sumados: cerca de 48.000 tokens frente a los 8.000 del pipeline. Ahí tienes tu factor de seis, y fíjate en que casi todo el sobrecoste está en esos tokens de entrada que crecen vuelta a vuelta, no en las respuestas del modelo. El número exacto variará, pero la forma entrada que engorda con cada paso es siempre la misma.

![S12-fig-06a-coste-por-vuelta.jpg](https://media1-production-mightynetworks.imgix.net/asset/59fc0d02-5126-4ec8-a716-cf15edda1aed/S12-fig-06a-coste-por-vuelta.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Para traducirlo a dinero, una regla mental útil que circula en el ecosistema sitúa el orden de diez céntimos de dólar por tarea en torno a los treinta o cincuenta mil tokens. Un agente que razona y busca varias veces se come ese presupuesto con facilidad. Y a escala, la diferencia deja de ser anecdótica: una operación que procesa un millón de tareas al mes gastando cinco veces los tokens necesarios quema del orden de un millón y medio de dólares al año de más. El multiplicador que en una tarea suelta parece despreciable, multiplicado por el volumen, es una partida presupuestaria.

La conclusión no es "los agentes son caros y ya". Es que el multiplicador depende por completo del caso, y que sin medirlo estás presupuestando a ciegas. Así que midámoslo.

## **Cómo medirlo**

La buena noticia es que el coste de un agente es de los problemas más medibles que tiene: cada llamada al modelo te devuelve exactamente cuántos tokens consumió. Solo hay que capturarlo y acumularlo.

Cada respuesta de la API trae un campo `usage` con los tokens de entrada, los de salida, y en modelos de razonamiento el desglose de cuántos de esos tokens de salida fueron de razonamiento. Un pequeño libro de cuentas que acumule esto a lo largo del bucle te da visibilidad total:

```python
from dataclasses import dataclass

@dataclass
class Pricing:
    input_per_1k: float
    output_per_1k: float

# Reasoning tokens are billed as output tokens.
@dataclass
class CostLedger:
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0  # Tracked for visibility; already included in output_tokens.

    def add(self, usage) -> None:
        self.steps += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.reasoning_tokens += (
            usage.output_tokens_details.reasoning_tokens
        )

    def cost(self, pricing: Pricing) -> float:
        return (
            self.input_tokens / 1000 * pricing.input_per_1k
            + self.output_tokens / 1000 * pricing.output_per_1k
        )
```

Conectarlo al bucle es una línea por vuelta: después de cada llamada al modelo, `ledger.add(response.usage)`. Al terminar, tienes el coste de esa ejecución, cuántos pasos dio, y cuánto de su gasto fue razonamiento puro.

Hay un detalle que conviene no equivocar: los tokens de razonamiento se facturan como tokens de salida y ya están contados dentro de `output_tokens`. No los sumes aparte duplicarías el coste. Los llevas por separado solo para *ver* qué fracción de tu gasto es deliberación; a veces descubres que la mitad de la factura es el modelo pensando, y esa es una señal accionable.

Tres cosas que medir más allá del total por ejecución.

La primera es **el coste por paso**, porque revela el crecimiento del contexto: verás cómo los tokens de entrada suben vuelta a vuelta, y eso te dice cuánto te está costando arrastrar el estado. Si la última llamada cuesta cinco veces la primera, ya sabes dónde está tu dinero.

La segunda es **la distribución, no la media**. Los agentes tienen cola larga: la mayoría de las ejecuciones son razonables, pero un agente confundido que itera hasta el límite de pasos es tu peor caso, y es el que te arruina el presupuesto medio. Mide el percentil 95, no solo el promedio, porque es ahí donde viven las sorpresas.

La tercera es **la comparación con el pipeline** sobre las mismas entradas. El número que importa no es el coste absoluto del agente, sino su sobrecoste frente a la alternativa más barata que resolvería el caso. Ese ratio es el que justifica o no la autonomía.

Y una atribución que paga con creces el esfuerzo de instrumentar: qué tool infla el contexto. Si registras el tamaño de la observación que devuelve cada tool, descubrirás rápido si el coste creciente viene de que `search_budgets` devuelve payloads enormes que luego se arrastran vuelta a vuelta. Atribuir el gasto a su origen esta tool, este tipo de observación, este tramo del bucle es lo que convierte "el agente es caro" en "el 60% del coste es el arrastre de resultados de búsqueda sin adelgazar", que ya es un problema con solución.

## **Cómo controlarlo**

Medido el coste, controlarlo es cuestión de palancas conocidas. Ordenadas por impacto para este caso:

**Enruta.** La palanca más grande no está dentro del agente, sino antes: no mandes al agente lo que un pipeline resolvería. Una clasificación barata al principio que envíe las transcripciones simples al pipeline fijo y solo las complejas al agente mantiene el coste medio bajo, porque pagas la autonomía únicamente cuando el problema la exige. La mayoría de tus entradas probablemente no la exigen.

**Adelgaza el contexto.** Como el crecimiento del contexto domina el coste por ejecución, recortarlo es la mayor palanca dentro del bucle. Resume las observaciones antiguas que ya no informan la decisión, descarta las irrelevantes, y guarda identificadores en lugar de payloads completos. Que `search_budgets` devuelva cinco referencias limpias en vez de doscientas filas en crudo no solo mejora las decisiones del modelo: reduce lo que reenvías en cada vuelta a partir de entonces.

**Acota la cola.** Un límite de pasos el clásico `MAX_STEPS` pone techo al peor caso. Complétalo con un presupuesto por ejecución: si una estimación supera un umbral de tokens o de coste, córtala y trátala como un caso para revisión en lugar de dejarla correr. La cola larga es donde se pierde el dinero, y esto la amputa.

**Ajusta el modelo y el razonamiento al trabajo.** No toda decisión necesita el máximo esfuerzo de razonamiento ni el modelo más caro. Reserva la potencia para la orquestación donde el agente decide y considera un modelo más barato o un esfuerzo de razonamiento menor para sub-tareas acotadas. El nivel de razonamiento es un dial de coste directo.

**Cachea lo determinista.** Si el agente repite búsquedas equivalentes entre ejecuciones, una caché de resultados evita pagar dos veces por lo mismo. No aplica a todo, pero donde aplica es dinero gratis.

![S12-fig-06b-palancas-de-coste.jpg](https://media1-production-mightynetworks.imgix.net/asset/5d825dd9-3fbb-49ad-a1d8-65e169b19fb0/S12-fig-06b-palancas-de-coste.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Ninguna de estas palancas es exótica. Son enrutado, gestión de estado, límites, selección de recursos y cacheo: el repertorio de siempre para operar cualquier proceso caro.

## **Cierre: el coste es una decisión de diseño, no un misterio**

El coste de un agente no es un problema oscuro de la IA. Es medible hasta el token, atribuible por paso, y controlable con ingeniería corriente: instrumentas, presupuestas, enrutas, cacheas. Lo único particular es que la unidad de facturación son tokens sobre un bucle no determinista; la disciplina para gestionarlo es la misma que aplicarías a cualquier operación cara.

Y de ahí sale el marco correcto para decidir. Un agente no es "mejor" que un pipeline: es un intercambio distinto entre coste y capacidad. La pregunta no es si el agente funciona casi siempre funciona, sino si el valor que aporta en tu caso justifica el multiplicador que acabas de medir. Si una estimación vale lo suficiente, cinco veces el coste de un pipeline es una ganga. Si no, el agente es la herramienta equivocada y el pipeline te estaba sirviendo mejor. Medir el coste no es un ejercicio de contabilidad: es lo que te permite tomar esa decisión con datos en lugar de con fe.

## **Fuentes**

- Anthropic, *Building Effective Agents* los agentes cambian latencia y coste por mejor rendimiento en la tarea, y la recomendación de no pagar esa cuenta cuando un flujo más simple basta: [https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)
- Barry Zhang (Anthropic), *How We Build Effective Agents* la heurística de coste por tarea y la aritmética a escala, sintetizada en: [https://shellypalmer.com/2026/04/how-anthropic-thinks-about-agents-workflows-and-tasks/](https://shellypalmer.com/2026/04/how-anthropic-thinks-about-agents-workflows-and-tasks/)
- OpenAI, *Usage and costs* el campo `usage` con tokens de entrada, salida y razonamiento por llamada: [https://platform.openai.com/docs/guides/production-best-practices](https://platform.openai.com/docs/guides/production-best-practices)