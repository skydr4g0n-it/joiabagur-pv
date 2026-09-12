# HU-AIENG-025bis: Retirar el andamio de la fusión plana — que no quede un camino muerto que se pueda encender por error

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** retirar la fusión plana y las perillas que quedaron sin lector al congelarse la decisión de C25, **sin mover ni una sola cifra** y conservando la memoria de por qué se llegó hasta aquí,
**para** que nadie pueda reactivar por accidente una aritmética que el proyecto midió como defectuosa, y para que el código diga una sola cosa donde la medición eligió una sola cosa.

---

## Descripción

C25 corrigió la fusión híbrida y, para poder **demostrar** que la corregía, tuvo que conservar la
fusión plana como modo seleccionable: sin ella, la fila `v2-hibrido` de la tabla de ablations
dejaba de ser reproducible y el change perdía la referencia contra la que se leen todas las demás
filas. Fue una decisión de medición, no de producto, y su propio `design.md` la declaró temporal.

Publicada la tabla y congelada la configuración, ese modo pasa a ser lo contrario de lo que era.

### El defecto que la fusión plana encarna, medido y publicado

```
  score(d) = Σᵢ wᵢ / (k + rangoᵢ(d))        k = 60, profundidad = 60
  rama léxica    w_typed 0,50 + w_expanded 0,50 = 1,00 votos, hasta 120 documentos
  rama vectorial                     w_vector = 0,33 votos,  hasta  60 documentos

  documento léxico en el rango 60  →  1,00/120 = 0,008333
  #1 de la rama vectorial          →  0,33/61  = 0,005410     ← pierde SIEMPRE
```

Los sesenta documentos léxicos ganan al mejor candidato vectorial **en toda consulta**, y el
documento de grado 2 que la rama vectorial pone en primer lugar cae a la **posición 33** en tres
consultas del golden set. No es un peso mal calibrado: es una partición dura disfrazada de fusión.
La fusión en dos etapas que C25 entregó vale **+0,083** sobre esa línea base en la lectura que
decide, y es hoy la única que la ruta viva ejecuta.

**Un camino muerto que se puede activar por error es cómo un defecto corregido regresa.** Ésa es
toda la historia.

### Lo que la exploración encontró al comprobar el inventario en vez de recordarlo

El plan describía tres cosas que retirar. Al mirarlas sobre el árbol, **tres de sus afirmaciones
resultaron falsas**, y esta historia entrega lo comprobado y no lo supuesto:

| Lo que decía la ficha | Lo que dice el árbol |
|---|---|
| «Los pesos por lista sólo los consume el modo plano» | **Falso.** `weight_typed` y `weight_expanded` alimentan también la etapa 1 de la fusión viva. Sólo `weight_vector` es exclusivo del modo plano |
| «Retirar la variante adaptativa que perdió el barrido» | **Pata vacía.** La forma binaria se implementó y se retiró *dentro* de C25. Hoy sólo quedan la continua adoptada y el `none` que es su brazo de control |
| «Que una configuración que nombre una perilla retirada falle al arrancar» | **No es alcanzable por el mecanismo previsto** y el remedio es peor que el mal: convertiría un residuo inofensivo en un fallo de arranque |

El inventario completo, con los lectores verificados de cada elemento, está en
[`c25bis-exploration-decisions.md`](../../Proyecto%20Final%20AIEng/informes/c25bis-exploration-decisions.md).

### El coste que esta historia acepta y declara

La fila `v2-hibrido` **deja de poder re-medirse**. Se conserva como artefacto citable —su informe,
su JSONL por consulta y su propio fichero de configuración— y pasa a ser **histórica y no
re-ejecutable**. La alternativa era mantener vivo un camino medido como roto, y ese precio es más
alto.

### Alcance de esta historia (sí)

1. **Retirar la fusión plana**: la rama del orquestador, el ajuste `JPV_FUSION_MODE` que la
   seleccionaba y la clave `fusion` de las configuraciones de evaluación.
2. **Retirar los tres pesos por lista** (`JPV_RRF_WEIGHT_TYPED`, `_EXPANDED`, `_VECTOR`) de los
   ajustes, de las configuraciones de evaluación, de la huella de fusión del barrido y de los
   parámetros de la orquestación. La etapa 1 pasa a componerse con **pesos iguales declarados en el
   módulo**, que es lo que la spec viva ya ordenaba.
3. **Conservar el registro de la composición** en la procedencia de cada corrida, poblado desde
   constante y no desde el entorno.
4. **Mover `v2-hibrido.yaml`** a `evals/configs/retired/`, con cabecera que lo declara histórico, y
   sacar `v2-hibrido` del orden de la tabla y del conjunto de pooling.
5. **Conservar la demostración del defecto** como test de aritmética pura, no activable por
   ninguna configuración.
6. **Acotar a la evaluación** la obligación de fallar nombrando una perilla retirada, y corregir en
   consecuencia la nota de migración del requisito retirado.
7. **Verificar que el borrado no movió nada**, comparando las corridas anterior y posterior **línea
   a línea del JSONL por consulta**.
8. **Seis deltas de specs vivas**, cuatro en `hybrid-fusion` y dos en `retrieval-evaluation`.
9. **Documentación**: README del servicio, README de tests, cabecera de histórico en el informe de
   C25, informe de implementación, plan y épicas.

### Fuera de alcance (no)

1. **Re-medir cualquier cosa.** Esta historia **no tiene autoridad para mover una cifra**. Si al
   borrar cambiase una, es un fallo del borrado que se revierte, no un resultado que discutir.
2. **Retirar `coverage_rule = "none"`.** Es el brazo de control con el que se midió el +0,128 y la
   marcha atrás declarada de la regla adaptativa; la spec viva lo exige por escrito.
3. **Retirar las perillas que C25 deja calibrables a propósito**: pesos de negocio, umbral de
   distancia, `k` y profundidad. Son el mecanismo de calibración de C26 y C38.
4. **Añadir una fila de control** para la regla de cobertura. El hueco se declara; no se cierra.
5. **Añadir una lista negra de nombres de variables retiradas** validada al arranque.
6. **Tocar el golden set**, `v2b-fusion`, `v3-senales` ni ningún otro artefacto de evaluación.
7. **Migraciones, cambios de contrato o reindexado.** `openapi.json` no se mueve.
8. **Diff fuera de `ai-service/`, `Documentos/` y `openspec/`.** Nada en `backend/`, `frontend/`,
   `terraform/` ni `.github/workflows/`.
9. **Cerrar las tres brechas que C25 dejó declaradas** (`Recall@5` 0,758 contra 0,85, abstención
   0,150 contra 0,80, y `v3` sin batir a `v2b` por el margen).

### Decisiones de diseño ya acordadas

| # | Decisión | Razón corta |
|---|---|---|
| **D-A** | La fila de referencia se **cita desde fuera** de la tabla; el arnés no gana un cargador de filas archivadas | La spec viva ya resuelve el caso simétrico así: las cifras anteriores *«se citan como históricas y no como filas comparables»*. Una fila leída de artefacto metería dos tuplas de procedencia en una tabla |
| **D-B** | **El selector muere, el registro vive**: `JPV_FUSION_MODE` desaparece, `Provenance.fusion_mode` se conserva | *Una perilla es algo que se puede poner; un registro es algo que se escribe.* El registro es lo que marca no comparables una corrida archivada y una nueva, y lo que delataría una fila publicada bajo una composición que nadie eligió |
| **D-C** | Mueren **los tres** pesos por lista; la etapa 1 queda con pesos iguales no configurables | Dos de ellos tienen lector vivo, pero la spec ya prohíbe moverlos. Una perilla que la norma prohíbe tocar no es una perilla muerta: es una trampa. Con pesos iguales el resultado es bit-idéntico por construcción |
| **D-D** | `none` **se queda**; la pata de la variante perdedora se declara **cumplida por C25** y se comprueba, no se ejecuta | La forma binaria ya no existe y hay un test que falla si vuelve. Y `none` está mandatado por dos escenarios vivos del propio requisito |
| **D-E** | `v2-hibrido.yaml` se conserva en **`evals/configs/retired/`** | El cargador hace `glob("*.yaml")` no recursivo, así que el subdirectorio es inalcanzable **por construcción**. Y el informe publicado no lleva los valores de las perillas: el YAML es el único sitio donde vive la configuración misma |
| **D-F** | La demostración del defecto se conserva como **fósil en un test** de aritmética pura | El proyecto conserva ejecutable el porqué de la decisión, sin conservar el camino que la causó |
| **D-G** | La obligación de fallar nombrando una perilla retirada se **acota a la evaluación** | Una perilla retirada e ignorada produce el comportamiento **bueno**; una clave mal escrita en un YAML de evaluación **publica una fila que mide otra cosa**. Distinta gravedad, distinto mecanismo — y el segundo ya está implementado |

### Referencias

- Change: [`openspec/changes/clean-plain-fusion/`](../../../openspec/changes/clean-plain-fusion/)
- Decisiones y evidencias: [`c25bis-exploration-decisions.md`](../../Proyecto%20Final%20AIEng/informes/c25bis-exploration-decisions.md)
- Historia origen del andamio: [`HU-AIENG-025`](HU-AIENG-025.md)
- Specs vivas afectadas: [`hybrid-fusion`](../../../openspec/specs/hybrid-fusion/spec.md) · [`retrieval-evaluation`](../../../openspec/specs/retrieval-evaluation/spec.md)
- Tabla publicada: [`c25-baselines-2026-09-11.md`](../../../ai-service/evals/results/c25-baselines-2026-09-11.md)
- Plan de changes: [`proyecto-final-plan-changes-openspec.md`](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md), ficha C25bis

---

## Criterios de Aceptación

### Escenario 1: No queda ningún camino de fusión plana seleccionable

- **Dado que** la decisión de composición está congelada y publicada,
- **cuando** se inspeccionan el módulo de fusión, el orquestador y los ajustes,
- **entonces** no existe ninguna fusión de una sola etapa sobre todas las listas,
- **y** ninguna configuración —de entorno o de evaluación— puede seleccionar una.

### Escenario 2: No queda ningún peso por lista en la configuración

- **Dado que** los pesos internos de la rama léxica deben ser iguales y no barrerse,
- **cuando** se inspeccionan los ajustes, la configuración de evaluación y los parámetros de la
  orquestación,
- **entonces** no hay definido ningún peso por lista,
- **y** la etapa 1 compone sus dos listas con pesos iguales declarados en el módulo.

### Escenario 3: El borrado no mueve ni una posición

- **Dado que** existe una corrida de las cinco configuraciones supervivientes tomada **antes** del
  borrado, sobre el mismo índice y la misma versión del golden set,
- **cuando** se repite esa corrida después del borrado y se comparan los dos JSONL por consulta,
- **entonces** para cada par configuración-consulta la lista de resultados es idéntica y todas las
  métricas son idénticas,
- **y** cualquier diferencia, por pequeña que sea, se trata como fallo del borrado y se revierte.

### Escenario 4: Sólo la revisión del código puede diferir entre las dos corridas

- **Dado que** la corrida posterior se toma sobre un árbol que ha cambiado,
- **cuando** se comparan las dos procedencias,
- **entonces** el único elemento que difiere es la revisión del código,
- **y** si difiriese la versión del golden set, la huella del índice o el modelo de embeddings, la
  verificación se declara **inválida** en vez de darse por buena.

### Escenario 5: La composición realmente en vigor sigue quedando registrada

- **Dado que** ya no existe un ajuste que seleccione la composición,
- **cuando** se ejecuta una evaluación,
- **entonces** su procedencia sigue registrando cómo se compusieron las ramas,
- **y** ese valor procede de una constante del módulo y no del entorno,
- **y** dos corridas compuestas de distinta forma se siguen declarando **no comparables**.

### Escenario 6: Una configuración de evaluación que nombra una perilla retirada falla nombrándola

- **Dado que** una configuración de evaluación nombra una perilla de fusión ya retirada,
- **cuando** se carga,
- **entonces** la carga falla y nombra la perilla retirada,
- **y** no se produce ninguna fila de la tabla bajo un ajuste silenciosamente ignorado.

### Escenario 7: Un entorno que aún nombre la perilla retirada no cambia nada, y la corrida lo delata

- **Dado que** un despliegue exporta todavía la variable de entorno del modo de fusión,
- **cuando** el servicio arranca y se ejecuta una recuperación,
- **entonces** el servicio arranca con normalidad y compone en dos etapas,
- **y** cualquier evaluación tomada así registra en su procedencia la composición que realmente
  ocurrió, no la que alguien creyó configurar.

### Escenario 8: La configuración de la línea base se conserva y ya no se puede cargar

- **Dado que** la fila de referencia ya no es ejecutable,
- **cuando** se busca bajo qué valores exactos se midió,
- **entonces** su fichero de configuración sigue versionado, marcado como histórico y fuera del
  directorio de configuraciones vivas,
- **y** un intento de cargarlo falla nombrando las claves que ya no existen.

### Escenario 9: La fila de referencia se cita como histórica y no como comparable

- **Dado que** la configuración bajo la que se midió la línea base ha sido retirada,
- **cuando** esa línea base se cita,
- **entonces** sus cifras y su procedencia completa están presentes como artefactos versionados,
- **y** la cita la marca como histórica y **no re-ejecutable**,
- **y** el informe declara qué filas pueden re-ejecutarse y cuáles no.

### Escenario 10: La aritmética del defecto sigue demostrada, y no es activable

- **Dado que** la fusión plana ya no existe como camino,
- **cuando** se ejecuta la suite,
- **entonces** un test de aritmética pura demuestra que, con los pesos históricos, el peor documento
  léxico supera al mejor candidato vectorial y éste cae fuera de los primeros puestos,
- **y** ese test no puede ser seleccionado por ninguna configuración, porque no pasa por el
  orquestador ni lee ningún ajuste.

### Escenario 11: El brazo de control de la regla adaptativa sigue disponible

- **Dado que** la regla de ponderación por cobertura sigue siendo la adoptada,
- **cuando** se inspecciona qué formas de escalado existen,
- **entonces** existe exactamente una forma de escalado, la continua,
- **y** apagar la regla sigue estando disponible para la evaluación como brazo de control,
- **y** ninguna configuración puede seleccionar la forma que la calibración descartó.

### Escenario 12: Ningún contrato, esquema ni componente ajeno se mueve

- **Dado que** este cambio es un borrado,
- **cuando** se revisa el diff completo,
- **entonces** el snapshot del contrato del servicio queda sin cambios y no hay migración,
- **y** no hay diff en el backend, el frontend, la infraestructura ni los flujos de CI.

### Escenario 13: Fuera de alcance explícito

- **Dado que** esta historia es de limpieza,
- **cuando** se revisa lo entregado,
- **entonces** no se ha modificado ningún peso calibrado, ni el golden set, ni las configuraciones
  supervivientes,
- **y** no se ha añadido ninguna fila a la tabla de ablations,
- **y** las tres brechas que C25 dejó declaradas siguen declaradas y sin cerrar.

---

## Notas adicionales

- **Actor**: desarrollador del proyecto. No hay superficie de usuario: ni el operador ni el
  administrador ven nada distinto, y ése es exactamente el resultado esperado.
- **Prerrequisito duro, ya cumplido**: C25 archivado el 2026-09-12 y su tabla publicada. Antes de
  eso, la fila plana era la referencia y no el andamio.
- **Es una hoja del grafo de dependencias**: no desbloquea ningún change. Cede el turno a C26 por la
  regla de prioridad al desbloqueo, y cierra la épica EP14.
- **Limitación conocida y aceptada**: la línea base deja de poder re-medirse. Lo que se garantiza a
  partir de aquí es poder **citar** de dónde viene la comparación, no volver a ejecutarla.
- **Limitación conocida y declarada**: el brazo de control de la regla de cobertura no tiene fila
  propia en la tabla y sólo es alcanzable a mano. La próxima profundización del golden set lo
  necesitará.
- **Riesgo principal, y el único que importa**: que el borrado se lleve algo que estaba en la ruta
  viva. La mitigación no es la revisión sino la medición — el diff línea a línea del Escenario 3.
- **Tentación que el diseño convierte en fallo**: «aprovechar» para ajustar algo. Un change de
  limpieza que mueve una cifra deja de ser verificable.
- **Change de OpenSpec por el que se implementa**:
  [`clean-plain-fusion`](../../../openspec/changes/clean-plain-fusion/), sobre la rama
  `c25bis-clean-plain-fusion`.

---

## Tareas

1. **Puerta de entrada**: confirmar que C25 está archivado, que la huella del índice no se ha
   movido, y registrar la corrida previa de las cinco configuraciones supervivientes como
   referencia de comparación — dejando escrito por qué la referencia **no** es la tabla publicada.
2. **Línea base de la suite**: ejecutar los tests y guardar los **nombres** de los que ya fallan,
   nunca su recuento.
3. **Inventario comprobado**: confirmar sobre el árbol los lectores de cada perilla candidata,
   escribirlo en el diseño del change antes de borrar, y declarar comprobada la pata ya cumplida.
4. **Retirar la fusión plana** del orquestador, con su parámetro, su ajuste y la ramificación de su
   traza.
5. **Fijar la etapa 1** con pesos iguales declarados en el módulo.
6. **Retirar los pesos por lista** de ajustes, configuración de evaluación, huella de fusión del
   barrido y parámetros de orquestación, incluido el perfil canónico del contrato.
7. **Conservar el registro de la composición** en la procedencia, poblado desde constante, y poner
   al día su documentación interna.
8. **Mover la configuración de la línea base** al directorio de retiradas, con cabecera de
   histórico, y sacarla del orden de la tabla y del conjunto de pooling.
9. **Ajustar los tests**: retirar los del comportamiento retirado y añadir los que fijan el
   borrado, el fósil de la aritmética y el que comprueba que la configuración retirada ya no carga.
10. **Verificar**: comparar nombres de tests en rojo, repetir la corrida y diferenciar los dos JSONL
    línea a línea exigiendo cero diferencias.
11. **Comprobar el perímetro**: contrato sin diff, sin migración, sin diff fuera del servicio de IA,
    y ninguna configuración de despliegue nombrando una perilla retirada.
12. **Escribir las seis deltas de specs** y validar el conjunto en estricto.
13. **Actualizar la documentación** con las cifras idénticas delante: README del servicio, README de
    tests, cabecera de histórico en el informe de C25, informe de implementación, plan y épicas.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **1/5** — ningún cambio observable en el mostrador. Su valor es de integridad del sistema, no de producto |
| Urgencia | **2/5** — es una hoja: no desbloquea nada. Pero el riesgo que retira crece con el tiempo, porque cuanto más se aleja C25 menos gente recuerda por qué ese camino sigue ahí |
| Complejidad / esfuerzo | **3/5** — el borrado es mecánico; lo que no lo es, es demostrar que no movió nada |
| Riesgos | Que el borrado se lleve algo de la ruta viva (mitigado por el diff línea a línea); que la huella del índice se haya movido y la verificación no pueda hacerse (puerta en la tarea 1); que alguien trate una diferencia de cifras como un resultado en vez de como un fallo |
| Dependencias | **C25 archivado** — prerrequisito duro, cumplido el 2026-09-12. No depende de nada más y nada depende de ella |
