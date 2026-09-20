## Context

`ai-service/src/jbg_ai/assist/` llega a este change con la capa de venta asistida completa y sin agente: C30a puso la estructura y los avisos por reglas, C30b el argumentario con su puerta numérica y su verificación de citas, y C31 el enrutador de intención con dos rechazos distintos y la repregunta determinista. Lo que falta para cerrar la rama agéntica es la capa de decisión, y C32 se partió el 2026-09-20 en las dos mitades que la componen.

Ésta es la de abajo: **las herramientas y su registro**. Su único consumidor será el bucle de C32b, así que nada de lo que se construya aquí se cablea a una ruta HTTP y `ai-service/openapi.json` no se toca.

El punto de partida verificado contra el árbol es que **cinco de las seis tools están servidas por código ya probado** —`retrieve_products()`, `retrieve_substitutes()`, `family_roster()`, `search_knowledge()` con el filtro de slug de C30a, y `clarification_for()`— y que la sexta, `consultar_disponibilidad`, **no tiene servicio detrás**. El §6.1 del diseño RAG dejó el esquema de la llamada de vuelta Python → .NET como decisión abierta *de este change*, y hay que cerrarla.

Tres restricciones gobiernan el resto:

- **La frontera del §6.2**: *Python calcula parecidos y redacta; .NET calcula números y decide.* La autoridad sobre el stock es de .NET.
- **El §15.10**: la proyección de disponibilidad puede desfasarse minutos, por eso **degrada y nunca elimina**.
- **El §15.8**: ningún agente escribe, y es una de las tres declaraciones que el README entrega.

## Goals / Non-Goals

**Goals:**

- Que las seis herramientas existan como piezas tipadas, inyectables y probadas **sin proveedor, sin red y sin base de datos real**.
- Que el invariante de solo-lectura sea una propiedad **comprobable del grafo de objetos**, no una promesa de un documento.
- Que `consultar_disponibilidad` deje de ser un hueco sin que el stock exacto cruce hacia el modelo.
- Que el contrato congelado **no se mueva** y que `POST /v1/assist/sale` se comporte exactamente como lo dejó C31.
- Que C32b encuentre una superficie en verde y sólo tenga que aportar el bucle.

**Non-Goals:**

- El bucle, sus iteraciones, sus tres presupuestos y `partial: true` — **C32b**.
- `POST /v1/assist/agent` y la transcripción multi-turno — **C32b**.
- El endpoint .NET de disponibilidad puntual y el esquema de autenticación de vuelta — **declarados y no hechos**.
- Iterar las descripciones de las tools contra un modelo real: esta mitad no llama a ninguno, y un prompt se itera con medición.
- Los escenarios de agente, los adversarios y los de inyección sistemáticos — **C38**.
- `perfil_punto_venta` (C33, anulada) y `buscar_complementarios` (C27, cortada). No vuelven.

## Decisions

### D-1 · `consultar_disponibilidad` se sirve desde `ai.pos_projection`, no desde .NET

La decisión abierta del §6.1 se resuelve **difiriéndola con motivo**: no hay que inventar un esquema de autenticación de vuelta para un dato que Python ya tiene proyectado.

*Alternativas consideradas.* **(a) Construir el endpoint .NET aquí** — es la respuesta «correcta» a largo plazo y la que el §6.1 anticipaba, pero la única arista Python → .NET existente es `AiIndexFeedController`, autenticada con `X-Index-Feed-Key`, **sin `[Authorize]` a propósito** y sin transportar `pos_id`; su ruta `pos-availability` es un feed paginado de 200 filas con keyset, no una consulta puntual. Significaría ruta nueva, filtro de autenticación con ámbito de punto de venta y tests de integración: **zona .NET dentro de un change de zona Python**, y la sesión desbordada. **(b) Retirar la tool y quedarse en cinco**, que es lo que la regla de la ficha pide literalmente — pero entonces el pivote a sustitutos pierde su disparador, y es el escenario de venta más característico del dominio.

La tool se diseña para que (a) sea un **reemplazo directo**: misma forma de observación, puerto inyectado, y ninguna lógica de disponibilidad dentro de la tool.

### D-2 · La observación es una etiqueta cualitativa sin dígitos, nunca el bucket

`QTY_BUCKETS` es `{"0", "1-2", "3+"}`: **son cifras**. Pasar el bucket crudo al modelo es pasarle una cifra de stock, que es lo que el §6.2 y el §15.10 prohíben y lo que el propio puerto declara al decir que *«a bucket on the wire would be the beginning of one»*.

El mapa va a vocabulario cerrado sin dígitos, el mismo patrón que los `warnings[]` de C30a: `sin_existencias`, `ultimas_unidades`, `disponible`.

*Alternativa considerada.* Emitir el bucket y confiar en la puerta numérica de C30b. Funcionaría —la puerta rechazaría una cifra que no esté en el payload—, pero convierte una red en el único control, y deja al modelo razonando sobre una cifra que nadie ha contrastado. La puerta sigue estando; deja de tener que salvarnos.

### D-3 · «Sin ámbito» es un valor propio y no se confunde con «agotado»

Si el principal no trae `pos_id`, o si no hay fila de proyección para esa pieza, la observación lo dice. Es el precedente literal del puerto: `qty_bucket = None` significa *«ran unscoped, which is not the same as a bucket of zero»*.

*Por qué importa*: inventar ausencia dispararía el pivote a sustitutos sobre una pieza que la tienda sí puede vender, que es exactamente el fallo que el §15.10 existe para prevenir. Cuatro valores y no tres, por tanto.

### D-4 · La observación declara su frescura, y la tool degrada en vez de fallar

Se reutiliza la frescura ya cableada en `retrieval/projection.py` —la que la recuperación publica como `projection_age_seconds`— en vez de recalcularla. Una proyección vieja no invalida la respuesta: la acompaña con su edad, igual que hace el §7.6.

### D-5 · `pedir_aclaracion` elige eje; el castellano lo escribe el código

La tool recibe **un eje del enum cerrado** que `clarification_axes()` ya publica y devuelve la plantilla que `clarification_for()` resuelve.

*Alternativa considerada.* Dejar que el modelo redacte la pregunta, que es lo que una lectura ingenua de «tool de aclaración» sugiere. Se descarta por dos razones que no son de estilo: `clarification_question` está tipada como **prosa** en el contrato, así que la capa de presentación no puede resolverla como resuelve un código, y **ninguna puerta numérica inspecciona ese campo**; y hacerlo **retiraría un requisito vivo** de `assist-generation` que C31 acaba de escribir.

### D-6 · El invariante de solo-lectura es estructural y se comprueba por introspección

Tres comprobaciones sobre el registro ya construido: que el conjunto de nombres es exactamente el congelado; que ningún puerto capturado por una herramienta expone método alguno del vocabulario de escritura (`insert|update|delete|write|save|upsert|persist|sync|apply`); y que ningún cliente HTTP registrado emite otro verbo que `GET`.

*Alternativa considerada.* Un campo `writes: bool = False` en el descriptor. No demuestra nada: lo pone a `False` quien registra la herramienta, que es justo quien podría equivocarse. La comprobación tiene que mirar el grafo de objetos, y tiene que **fallar al registrar** una herramienta futura que no cumpla — que es lo que la hace útil dentro de seis meses.

### D-7 · Los fallos son observaciones con causa de vocabulario cerrado

Una excepción que escapa mataría el bucle de C32b en vez de gastarle una vuelta; un `"error"` genérico deja ciego al modelo. La observación fallida dice **qué** falló, con código y no con prosa, siguiendo el patrón que C30a estableció para los avisos.

### D-8 · Las herramientas se direccionan por `sku`, nunca por identificador interno

Precedente propio: C30b y C31 **excluyen los identificadores internos de producto** del *payload* por ser *«dígitos arbitrarios, nunca se dicen en mostrador»*. Un SKU es estable, real y semántico, que es lo que el apunte de S12 pide de un resultado de tool.

*Coste aceptado*: una lectura por SKU nueva en `ProductSearchPort`, junto a `source_document()` y `family_roster()`, que responden preguntas de la misma naturaleza sobre la misma tabla. *Alternativa considerada*: aceptar ambos y resolver en el registro — se descarta porque obliga a explicar en la descripción cuándo usar cada uno, que es la señal de que una herramienta hace demasiadas cosas.

### D-9 · Observaciones acotadas y sin `score` crudo

Lo que esta mitad decida entregar se reenvía **en cada vuelta** del bucle de C32b, y el contexto acumulado es el factor dominante del coste de un agente. Las observaciones llevan lo justo para decidir el siguiente paso. Si hace falta señal de orden, viaja como **posición** y no como número comparable entre herramientas distintas — un `score` de recuperación y uno de sustitutos no miden lo mismo, y ponerlos juntos invita a compararlos.

### D-10 · El registro no se cablea a ninguna ruta, y los esquemas no se congelan en un *snapshot*

Su único consumidor es el bucle. `openapi.json` se congela porque es frontera con .NET; esto no cruza ninguna frontera, así que la forma de los esquemas de *function calling* se fija con **un test de forma** y no con un fichero versionado que habría que regenerar en cada cambio interno.

### D-11 · Capability propia, `sales-assistant-tools`

`assist-generation` tiene ya 41 requisitos y describe el comportamiento de una **ruta HTTP**; esto es una biblioteca sin ruta. El precedente de reparto lo fijó C30a: cuando añadió `family_roster()` al puerto, el requisito se escribió en la capability **consumidora** y no en la del puerto. Aquí la consumidora es nueva.

### D-12 · `buscar_catalogo` expone `top_k`, acotado en el esquema

Con mínimo y máximo declarados. El apunte de S12 es explícito en que un límite explícito o un `enum` bien puesto hacen más por la fiabilidad que cualquier ajuste de temperatura, y un `top_k` sin cota es la forma más barata de que una vuelta del bucle arrastre cincuenta candidatos a todas las siguientes.

## Risks / Trade-offs

- **La granularidad de las seis puede resultar equivocada, y esta mitad no puede medirlo** → Es una limitación estructural del corte, no un descuido: iterar descripciones exige un modelo, y aquí no hay ninguno. Se mitiga dejando el registro construido con puertos inyectados, de modo que C32b pueda reagrupar o dividir una herramienta sin tocar los puertos ni la suite de éstos.
- **La etiqueta cualitativa puede quedarse corta**, si C32b descubre que el modelo necesitaba distinguir `1-2` de `3+` para decidir el pivote → El vocabulario es una constante y ensancharlo no mueve ningún contrato. Lo que no se hará es volver al bucket crudo.
- **Este change toca `retrieval/`, que C31 declaró explícitamente no haber tocado** → Se limita a **añadir** dos lecturas al `Protocol` y su SQL; ninguna función existente se modifica. El efecto colateral real es que los dobles de `ProductSearchPort` en la suite dejan de satisfacer el `Protocol` hasta que se amplíen, y eso es trabajo contemplado y no un descubrimiento.
- **Leer la disponibilidad pieza a pieza multiplica las consultas** si el bucle de C32b pregunta por muchas → Aceptado: el pool está limitado a 5 conexiones y la alternativa —`scope_buckets()`, que devuelve el surtido entero, del orden de mil filas— es un volcado que además desperdiciaría contexto. Si C32b mide que hace falta, el puerto admite una lectura por lote sin cambiar la forma de la observación.
- **Que la delta de spec no encaje donde se ha decidido** y haya que renegociar el reparto a mitad de sesión → Mitigado por D-11, que se apoya en un precedente propio y no en un criterio nuevo.
- **Que alguien lea «seis tools» como el entregable** → El recuento no es lo que el PF evalúa. Lo evaluable son el bucle, el presupuesto duro, el invariante de solo-lectura y el `partial: true`; de los cuatro, este change entrega **uno**, y así está escrito en la historia.

## Migration Plan

No hay migración. Sin cambios de esquema, sin Alembic, sin EF Core y sin variables de entorno nuevas.

**Despliegue**: ninguno. Nada de lo que entrega este change es alcanzable desde fuera del proceso, porque no se cablea a ninguna ruta.

**Rollback**: retirar el módulo. Al no haber consumidor —el bucle es C32b— y al no moverse el contrato, la marcha atrás no deja rastro en ninguna superficie publicada. La única huella fuera de `assist/` son las dos lecturas añadidas al puerto, que ningún camino existente invoca.

## Open Questions

Las seis preguntas abiertas del ticket se cierran con su opción por defecto, y quedan recogidas arriba: **Q-1** en D-11 (capability propia), **Q-2** en D-3 (cuatro etiquetas), **Q-3** en D-12 (`top_k` acotado), **Q-4** en D-10 (sin *snapshot*), **Q-5** en D-8 (la lectura por SKU va en `ProductSearchPort`) y **Q-6** en D-9 (sin `score` crudo).

Queda **una sola pregunta viva, y no es de este change**: si el enrutador de C31 debe clasificar **todos** los turnos del operario o sólo el primero cuando llegue la conversación multi-turno. Está anotada en la ficha de C32b con su propuesta —clasificar todos, cortocircuitar sólo el primero— y no bloquea nada de aquí, porque en este change no hay conversación.
