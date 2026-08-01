# Gestión efectiva de contexto en arquitectura CAG

Creada: 30 de abril de 2026 20:52
Módulo: M2. Arquitecturas CAG (https://app.notion.com/p/M2-Arquitecturas-CAG-b69ea9ca03c4837fae818110aa5ad27d?pvs=21)
Sesión: S2. Primeros pasos de arquitectura CAG (https://app.notion.com/p/S2-Primeros-pasos-de-arquitectura-CAG-352ea9ca03c4800aa421ca55b02ceccb?pvs=21)

## **El contexto como recurso finito**

En el artículo anterior sobre la estructura FastAPI del proyecto, vimos que la capa `context/` es donde viven los datos de referencia que inyectamos en cada llamada al LLM. Lo que no abordamos es la pregunta más importante: ¿cómo decidimos qué meter ahí y cómo formatearlo?

En una arquitectura CAG, la ventana de contexto del modelo es tu recurso más valioso y tu limitación más dura. Todo lo que el modelo necesita saber debe caber en esa ventana — junto con las instrucciones del system prompt, la consulta del usuario y el espacio que necesita el modelo para generar su respuesta. No hay una base de datos vectorial a la que recurrir si algo no cabe. Lo que no está en el contexto, no existe para el modelo.

Gestionar este recurso con criterio es lo que marca la diferencia entre un sistema CAG que produce respuestas útiles y uno que produce texto genérico que no le sirve a nadie.

## **Anatomía de la ventana de contexto**

Antes de hablar de estrategias, necesitamos entender cómo se reparte la ventana de contexto en una llamada típica de nuestro sistema de estimaciones.

```
┌─────────────────────────────────────────────────────────┐
│                    VENTANA DE CONTEXTO                   │
│                  (ej: 128K tokens total)                 │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  System prompt: instrucciones + rol               │  │
│  │  (~500-1.500 tokens)                              │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Contexto inyectado: estimaciones de referencia    │  │
│  │  (~2.000-40.000 tokens según cantidad de datos)   │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Mensaje del usuario: transcripción de reunión     │  │
│  │  (~500-5.000 tokens)                              │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Respuesta del modelo: estimación generada         │  │
│  │  (~1.000-3.000 tokens)                            │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Espacio no utilizado                              │  │
│  │  (el "desperdicio" que intentamos minimizar)       │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

La suma de todos los bloques no puede exceder el tamaño de la ventana de contexto del modelo. Si lo hace, la llamada falla directamente o el sistema trunca contenido silenciosamente — con resultados impredecibles.

Pero hay un matiz más sutil. Aunque todo quepa en la ventana, eso no garantiza que el modelo use bien la información. La investigación muestra que a medida que el contexto crece, la capacidad de atención del modelo se degrada. No es una degradación lineal: los modelos prestan más atención al contenido que está al principio y al final del contexto, y tienden a "perderse" con lo que está en el medio. Este fenómeno, conocido como "lost in the middle", tiene implicaciones directas en cómo debemos organizar la información.

## **Presupuesto de tokens: planifica antes de construir**

Antes de escribir una sola línea de código, necesitas hacer un ejercicio de presupuesto. ¿Cuántos tokens tienes disponibles y cómo los vas a repartir?

Para nuestro proyecto de estimaciones, trabajando con un modelo como `gpt-4o-mini` (128K tokens de contexto) o `claude-haiku-4-5` (200K tokens), el cálculo orientativo sería:

![image.png](https://media1-production-mightynetworks.imgix.net/asset/09b5eb47-675a-40ec-a837-1b92b75698f7/1146e01f9b39811e.png?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

La primera conclusión es evidente: en la fase CAG de nuestro proyecto, tenemos espacio de sobra. Con 5-10 estimaciones de referencia no vamos a acercarnos al límite. Esto es exactamente lo que hace viable la arquitectura CAG para este caso de uso.

La segunda conclusión es menos obvia pero más importante: que tengas espacio no significa que debas llenarlo. Cada token adicional de contexto tiene un coste económico (pagas por token de entrada) y un coste atencional (el modelo tiene que procesar más información para encontrar lo relevante). El objetivo no es meter el máximo posible, sino meter lo mínimo necesario con la máxima calidad.

## **Qué incluir en el contexto (y qué no)**

Decidir qué información forma parte del contexto inyectado es una decisión de diseño, no una decisión técnica. Requiere entender qué necesita el modelo para hacer bien su trabajo y qué es ruido que lo distrae.

### **Información que mejora la respuesta**

En nuestro sistema de estimaciones, el modelo necesita referencia para generar estimaciones realistas. Los datos de referencia útiles son aquellos que le permiten calibrar su respuesta contra la realidad de tu empresa:

**Ejemplos de estimaciones previas completas.** No basta con decir "un proyecto de e-commerce costó 200 horas". El modelo necesita ver el desglose: qué tareas se estimaron, cuántas horas se asignaron a cada una, qué tecnologías estaban involucradas, qué tamaño de equipo se propuso. Es el desglose lo que le permite generar un desglose propio coherente.

**Patrones de precios y dedicación.** Si en tu empresa un día de desarrollo backend cuesta 500€ y uno de diseño UX cuesta 400€, el modelo necesita esa referencia para no inventar cifras. Sin estos datos, generará precios basados en su conocimiento general del mercado — que puede o no coincidir con tu realidad.

**Estructura y formato del output esperado.** Si quieres que la estimación tenga un formato concreto (secciones, campos, unidades), incluir un ejemplo de cómo debe verse el resultado final es más efectivo que describir el formato en texto.

### **Información que degrada la respuesta**

**Datos excesivamente detallados que no aportan al patrón.** El historial completo de comunicaciones con el cliente del proyecto de referencia no ayuda a estimar un proyecto nuevo. Los detalles internos de gestión de cada proyecto anterior son ruido.

**Información contradictoria.** Si incluyes estimaciones de épocas muy diferentes (cuando la empresa era más pequeña, con precios distintos, con tecnologías obsoletas), el modelo puede generar estimaciones que mezclen patrones incompatibles. Es mejor incluir pocas referencias relevantes y actuales que muchas heterogéneas.

**Contexto redundante.** Si tres estimaciones de referencia cubren proyectos de e-commerce muy similares, la segunda y tercera aportan rendimientos decrecientes. Mejor incluir una de e-commerce, una de plataforma SaaS y una de aplicación interna — mayor diversidad de referencia con menor consumo de tokens.

## **Cómo formatear el contexto para el modelo**

El formato en que presentas los datos de referencia al modelo importa más de lo que parece. Un LLM procesa texto, y la forma en que ese texto está estructurado afecta directamente a cómo lo interpreta.

### **Texto plano estructurado vs. JSON vs. Markdown**

Hay tres formatos habituales para inyectar datos de referencia. Cada uno tiene un perfil diferente:

**Texto plano estructurado** funciona bien cuando los datos son descriptivos y el modelo necesita entender narrativa, no estructura. Es el formato más eficiente en tokens.

```
-- Estimación de referencia 1 ---
Proyecto: Plataforma de gestión de inventario
Tareas:
Diseño UI/UX: 40 horas a 400 EUR/hora → 16.000 EUR
Backend API REST: 60 horas a 500 EUR/hora → 30.000 EUR
Autenticación y roles: 20 horas a 500 EUR/hora → 10.000 EUR
Total: 120 horas, 56.000 EUR
Equipo: 2 developers full-stack, 1 diseñador UX (part-time)
Duración: 6-8 semanas
```

**JSON** es útil cuando necesitas que el modelo entienda relaciones jerárquicas o cuando el output que esperas también es JSON. Los modelos actuales procesan JSON con soltura, pero consume más tokens que texto plano por los caracteres de estructura (llaves, comillas, indentación).

```json
{
  "project": "Plataforma de gestión de inventario",
  "tasks": [
    {"name": "Diseño UI/UX", "hours": 40, "rate": 400, "total": 16000},
    {"name": "Backend API REST", "hours": 60, "rate": 500, "total": 30000}
  ],
  "total_hours": 120,
  "total_cost": 56000
}
```

**Markdown** es un punto intermedio: estructurado visualmente, con jerarquía clara mediante headers, y más eficiente en tokens que JSON. Es el formato que usaremos por defecto en nuestro proyecto.

La recomendación práctica: usa el formato que más se parezca al output que esperas. Si quieres que el modelo genere estimaciones en Markdown con secciones y tablas, dale los ejemplos de referencia en Markdown con secciones y tablas. El modelo tiende a replicar los patrones que ve en su contexto.

### **Separadores y delimitadores**

Cuando incluyes múltiples ejemplos de referencia, necesitas delimitar dónde empieza y termina cada uno. Sin delimitadores claros, el modelo puede mezclar información de diferentes estimaciones.

```
===== ESTIMACIÓN DE REFERENCIA 1 =====

[contenido de la primera estimación]

===== ESTIMACIÓN DE REFERENCIA 2 =====

[contenido de la segunda estimación]

===== FIN DE ESTIMACIONES DE REFERENCIA =====
```

Los separadores cumplen dos funciones: ayudan al modelo a entender la estructura del contexto, y te ayudan a ti a debuggear cuando la respuesta no es la esperada (¿el modelo mezcló las estimaciones 1 y 3? quizá los separadores no son suficientemente claros).

## **La posición importa: dónde colocar cada cosa**

El efecto "lost in the middle" tiene una implicación práctica directa para nuestra arquitectura: la información más importante debe estar al principio o al final del contexto, nunca enterrada en el medio.

En nuestro sistema de estimaciones, esto se traduce en un orden deliberado:

```
1. System prompt con instrucciones claras          ← PRINCIPIO (máxima atención)
2. Formato esperado del output
3. Estimaciones de referencia (las más relevantes primero)
4. [... más estimaciones ...]
5. Restricciones y reglas específicas               ← CERCA DEL FINAL
6. Transcripción de la reunión (mensaje del usuario) ← FINAL (máxima atención)
```

Las instrucciones van al principio porque definen el comportamiento del modelo para toda la interacción. La transcripción va al final porque es la consulta directa que necesita respuesta inmediata. Las estimaciones de referencia van en el medio, pero ordenadas por relevancia: la más útil primero. Y las restricciones o reglas específicas van justo antes de la transcripción, cerca del final, donde recibirán atención.

Este orden no es arbitrario. Es una decisión de ingeniería basada en cómo los modelos distribuyen su atención sobre el contexto.

## **El system prompt: instrucciones que dirigen todo**

El system prompt es la parte del contexto que define quién es el modelo y cómo debe comportarse. En una arquitectura CAG, es también donde le dices cómo interpretar el contexto de referencia que le estás proporcionando.

Un system prompt débil para nuestro proyecto sería:

`Eres un asistente que ayuda con estimaciones de software.`

Esto es demasiado vago. El modelo no sabe qué formato usar, qué nivel de detalle proporcionar, ni cómo usar las estimaciones de referencia. El resultado será genérico y probablemente inútil.

Un system prompt efectivo define cuatro dimensiones:

**Rol y expertise.** No solo "eres un asistente", sino qué tipo de experto eres y qué experiencia tienes. Cuanto más específico sea el rol, más calibrada será la respuesta.

**Tarea concreta.** Qué debe hacer exactamente con la información que recibe. En nuestro caso: analizar una transcripción de reunión y generar una estimación de proyecto de software.

**Uso del contexto de referencia.** Cómo debe interpretar y usar las estimaciones históricas que le proporcionamos. ¿Son ejemplos de formato? ¿Son datos de calibración de precios? ¿Son proyectos similares? El modelo necesita saber para qué están ahí.

**Formato del output.** Qué estructura debe tener la respuesta: secciones, campos obligatorios, unidades, nivel de detalle. Si no lo especificas, el modelo decidirá por ti — y no siempre decidirá bien.

Un system prompt más efectivo:

```
Eres un consultor senior de software con 15 años de experiencia en estimación
de proyectos. Tu trabajo es analizar transcripciones de reuniones con clientes
y generar estimaciones detalladas de desarrollo de software.

A continuación se incluyen estimaciones de proyectos anteriores de la empresa.
Úsalas como referencia para calibrar tus estimaciones: los precios por hora,
la granularidad del desglose de tareas y la estructura del presupuesto deben
ser consistentes con estos ejemplos.

Tu estimación debe incluir:
1. Resumen del proyecto (2-3 frases)
2. Desglose de tareas con horas estimadas y coste
3. Equipo recomendado
4. Duración total estimada
5. Riesgos o supuestos clave

Usa EUR como moneda. Redondea las horas a múltiplos de 5.
```

La diferencia entre ambos prompts parece obvia cuando los comparas, pero en la práctica muchos sistemas en producción funcionan con prompts del primer tipo. La calidad del system prompt es posiblemente el factor que más impacta en la calidad del output, y sin embargo es el componente al que menos tiempo se le suele dedicar.

## **Preprocesamiento: la capa invisible que marca la diferencia**

Entre tus datos en crudo y el contexto que llega al modelo hay una capa de transformación que no siempre se hace visible, pero que tiene un impacto enorme. Es lo que en nuestra estructura FastAPI vive en el servicio — la función que toma los datos de `context/examples.py` y los convierte en texto listo para inyectar en el prompt.

Las operaciones de preprocesamiento típicas para nuestro proyecto incluyen:

**Selección de campos relevantes.** Un presupuesto completo en JSON puede tener 50 campos. El modelo no necesita el ID interno del presupuesto, la fecha de creación, el email del comercial ni las condiciones de pago para generar una estimación de horas y coste. Incluir esos campos consume tokens sin aportar valor.

**Normalización de formatos.** Si un presupuesto histórico usa "días" como unidad y otro usa "horas", el contexto debe normalizarlos a una unidad común. Si uno usa puntos decimales y otro comas, igualmente. El modelo puede manejar inconsistencias, pero cada inconsistencia introduce una pequeña probabilidad de error en el output.

**Cálculo de campos derivados.** Si el presupuesto original tiene `quantity: 15` y `unit_price: 500` pero no tiene `total`, calcularlo y añadirlo al contexto evita que el modelo tenga que hacer aritmética — algo en lo que los LLMs no son especialmente fiables.

**Anonimización.** Si los presupuestos históricos contienen nombres de clientes, emails u otra información sensible, deben eliminarse o generalizarse antes de incluirlos en el contexto. El modelo no necesita saber que el proyecto era para "Empresa X" — necesita saber que era una plataforma de e-commerce con 50K usuarios mensuales.

Estas transformaciones parecen menores, pero su efecto acumulativo es sustancial. Un contexto limpio, consistente y sin ruido produce respuestas significativamente mejores que un volcado directo de datos en crudo.

## **Cuántos ejemplos de referencia incluir**

Una pregunta recurrente en arquitectura CAG es cuántos datos de referencia incluir. La respuesta no es "todos los que quepan", sino "los que aporten sin generar ruido".

Para nuestro sistema de estimaciones, la orientación práctica es:

**2-3 ejemplos** son suficientes para que el modelo entienda el formato, la escala de precios y el nivel de desglose esperado. Este es el mínimo viable para una arquitectura CAG que produzca resultados utilizables.

**5-7 ejemplos** son el punto dulce para la mayoría de los casos. Proporcionan suficiente diversidad de tipos de proyecto (web, móvil, API, integración) para que el modelo calibre bien sin inundar el contexto.

**Más de 10 ejemplos** empiezan a tener rendimientos decrecientes. El octavo ejemplo de presupuesto de e-commerce no aporta información que los tres primeros no hayan cubierto ya, pero sí consume tokens y diluye la atención del modelo.

La evolución natural del sistema, cuando 10 ejemplos no son suficientes y necesitas cientos de presupuestos de referencia, es exactamente el momento en que CAG deja de ser la arquitectura adecuada y la migración a RAG está justificada. En RAG, un servicio de búsqueda semántica selecciona los 5-7 más relevantes de entre cientos, combinando lo mejor de ambos mundos: la precisión de la selección con la eficiencia de un contexto acotado.

## **Iteración sobre el contexto: un proceso continuo**

Una ventaja poco mencionada de la arquitectura CAG es la velocidad de iteración. Como los datos de referencia están definidos en tu código (en `context/examples.py`), cambiar un ejemplo, reformatear los datos o ajustar el system prompt es inmediato. No necesitas re-indexar una base de datos, recalcular embeddings ni esperar a que un pipeline de ingesta se complete.

Esto convierte la optimización del contexto en un ciclo rápido:

```
1. Ejecutar una estimación con la transcripción de prueba
2. Evaluar la calidad del resultado
3. Identificar el problema:
   ¿Formato inadecuado? → Ajustar el system prompt
   ¿Precios descalibrados? → Mejorar los ejemplos de referencia
   ¿Desglose demasiado genérico? → Añadir más detalle a los ejemplos
   ¿Información irrelevante en el output? → Añadir restricciones
4. Modificar el contexto
5. Volver al paso 1
```

Cada iteración es cuestión de segundos: modificas un string, reinicias el servidor (o `--reload` lo hace por ti), y lanzas otra petición. Esta velocidad de iteración es algo que perderemos parcialmente cuando migremos a RAG, donde los cambios en los datos requieren re-vectorización. Es una razón más para explotar la fase CAG al máximo: invertir tiempo ahora en encontrar el formato de contexto óptimo y el system prompt más efectivo nos ahorrará esfuerzo significativo en fases posteriores.

## **Errores comunes en la gestión de contexto**

Estos son los patrones que producen malos resultados de forma recurrente. Reconocerlos te ahorrará horas de debugging.

**Contexto demasiado genérico.** Si los ejemplos de referencia son de proyectos muy diferentes entre sí y muy diferentes al que se está estimando, el modelo no tiene un patrón claro que seguir. La respuesta será una media difusa que no refleja ningún caso real.

**Instrucciones contradictorias.** Si el system prompt dice "sé conciso" pero los ejemplos de referencia son extensos y detallados, el modelo recibe señales opuestas. Los ejemplos suelen ganar (el modelo imita lo que ve), así que asegúrate de que instrucciones y ejemplos estén alineados.

**Ausencia de formato de output.** Sin una especificación clara del formato esperado, cada llamada puede producir una estructura diferente. Una llamada devuelve una tabla, la siguiente una lista, la siguiente un párrafo narrativo. Para un sistema de producción, la consistencia del formato es tan importante como la calidad del contenido.

**Volcado de datos sin curación.** Pegar un JSON de 200 líneas directamente como contexto es la forma más segura de obtener resultados pobres. El modelo no sabe qué campos son importantes y cuáles son ruido administrativo. La curación del contexto es una responsabilidad del desarrollador, no del modelo.

**Ignorar el coste acumulativo.** Cada llamada al LLM con contexto CAG envía todos los tokens de referencia. Si tu contexto tiene 10.000 tokens de referencia y haces 1.000 llamadas al día, estás pagando 10 millones de tokens de entrada al día solo en contexto. El coste del contexto se multiplica por el volumen de uso.

## **Resumen**

- **La ventana de contexto es un recurso finito** que compartes entre instrucciones, datos de referencia, la consulta del usuario y la respuesta del modelo. Planificar un presupuesto de tokens antes de escribir código evita problemas difíciles de diagnosticar.
- **Menos es más.** El objetivo no es llenar la ventana de contexto sino incluir la información mínima necesaria con la máxima calidad. Cada token adicional tiene un coste económico y un coste atencional.
- **El formato del contexto importa tanto como el contenido.** Texto estructurado con separadores claros, campos normalizados y datos derivados precalculados produce mejores resultados que un volcado de datos en crudo.
- **La posición importa.** Instrucciones al principio, restricciones cerca del final, la consulta del usuario al final. Los datos de referencia en el medio, ordenados de mayor a menor relevancia.
- **El system prompt es el componente de mayor impacto.** Definir rol, tarea, uso del contexto y formato de output con precisión es lo que convierte una respuesta genérica en una estimación profesional.
- **CAG permite iterar rápido.** Aprovecha esta velocidad para encontrar el formato de contexto óptimo y el prompt más efectivo antes de migrar a RAG, donde los cambios tienen más fricción.