## Context

C25 dejó tres cosas vivas que sólo existen para que su propia medición fuese posible:

| Andamio | Por qué C25 lo necesitó | Por qué estorba después |
|---|---|---|
| Fusión plana de tres listas, seleccionable | La fila `v2-hibrido` es la referencia de la tabla, y se midió con ella | Camino muerto, activable por error, con una aritmética que el proyecto midió como defectuosa |
| Dos formas de ponderación adaptativa (continua y binaria con `α`) | Se barrieron una contra otra | Dos mecanismos vivos donde la medición eligió uno |
| Pesos por lista (`w_typed`, `w_expanded`) | Los consume sólo el modo plano | Sin lectores, y contradicen los pesos por rama |

El defecto que la fusión plana encarna está medido y publicado: con los pesos de C21, un documento
léxico en el rango 60 puntúa 0,008333 y el mejor documento que sólo vio la rama vectorial puntúa
0,005410, así que **los 60 documentos léxicos ganan al #1 vectorial en toda consulta**; y el grado
2 que la vectorial pone en el primer puesto cae a la posición 33 en tres consultas del golden set.
Dejar seleccionable un camino con esa propiedad es dejar abierta la puerta por la que el defecto
vuelve.

**Restricción que gobierna este change:** no puede abrirse antes de que C25 esté archivado y su
tabla publicada. Antes de eso retiraría el andamio mientras el andamio sostiene algo.

## Goals / Non-Goals

**Goals:**

- Que no quede seleccionable ningún camino de fusión que la medición haya descartado.
- Que no queden dos mecanismos vivos donde la medición eligió uno.
- Que no queden perillas sin lector.
- Que la pérdida de re-ejecución de la línea base quede **declarada**, no descubierta más tarde.

**Non-Goals:**

- Cambiar ningún valor calibrado por C25. Este change **no re-mide nada** y no mueve ningún peso:
  si al retirar código cambiase una cifra, sería un defecto del borrado y no un resultado.
- Retirar las perillas que C25 deja **calibrables a propósito** —los pesos de negocio, el umbral—:
  siguen teniendo lector y siguen siendo el mecanismo de decisión de C26 y C38.
- Retirar el golden set, las configuraciones `v2b-fusion` y `v3-senales`, o cualquier artefacto de
  evaluación distinto de la fila que deja de ser ejecutable.
- Tocar `backend/`, `frontend/`, `terraform/` o `.github/workflows/`.

## Decisions

### D1 · La línea base se conserva como artefacto, no como código ejecutable

Al retirar el modo plano, `v2-hibrido` deja de poder re-medirse. La alternativa que se adopta es
**conservar sus cifras y su procedencia** —el informe en `ai-service/evals/results/` y el JSONL por
consulta, los dos versionados en git— y **declarar** que la fila es histórica y no re-ejecutable.

*Razón:* la garantía que importa es poder **citar** de dónde viene una comparación, y eso lo da la
procedencia archivada. Poder re-ejecutarla sería mejor, pero su precio es mantener vivo un camino
medido como roto, y ese precio es más alto: un camino muerto que se puede activar por error es
exactamente cómo un defecto corregido regresa.

*Alternativas descartadas:* **(a)** mantener el modo plano indefinidamente sólo para el arnés —es
lo que este change existe para evitar, y además un modo que sólo usan los tests deja de estar
ejercitado por la ruta viva y se podre sin que nadie lo note. **(b)** Congelar el modo plano en una
copia dentro del paquete de evaluación —duplica la aritmética defectuosa en un segundo sitio, que
es el error que C24 ya nombró: *«un arnés que reimplementa el pipeline mide la copia»*. **(c)**
Sustituirlo por un fixture de resultados esperados —es lo que ya es el JSONL, sin añadir código.

*Consecuencia normativa:* el requisito de `retrieval-evaluation` que obliga a que la configuración
de la línea base siga siendo seleccionable se sustituye por uno de conservación y declaración.

### D2 · Se retira la variante adaptativa perdedora, y el borrado no cambia ninguna cifra

C25 mide la ponderación adaptativa continua contra la binaria con `α`. La que pierda se retira
entera, con su perilla y sus tests.

*Criterio de verificación del borrado:* la tabla de ablations se re-ejecuta **una vez** tras la
limpieza, sobre la misma versión del golden set, y **las filas supervivientes deben dar cifras
idénticas**. Una diferencia, por pequeña que sea, significa que el borrado se llevó algo que estaba
en la ruta viva — y es un fallo del change, no un resultado que discutir.

*Razón para no aceptar deltas:* este change no tiene autoridad para mover una métrica. La tiene
C25, bajo su regla escrita antes de medir. Si aquí se mueve algo, se revierte y se investiga.

### D3 · Sólo se retiran perillas sin lector, y la lista se comprueba, no se recuerda

Una perilla se retira cuando **ninguna** de estas tres cosas la lee: la ruta viva, una configuración
de evaluación superviviente, o un test que ejerza comportamiento vivo. La comprobación es por
búsqueda sobre el árbol y no por memoria de lo que C25 dejó.

*Razón:* el inventario de perillas de este subsistema ya sorprendió cuatro veces en el proyecto
—`tsv`, la expansión, `qty_bucket` y `coordination` estuvieron calculados y sin lector— y en las
cuatro el error fue suponer el inventario en lugar de mirarlo. Aquí el riesgo es el simétrico:
retirar algo que sí tenía un lector.

### D4 · El orden es borrar, verificar y sólo entonces actualizar la documentación

Primero el borrado con los tests en verde; después la re-ejecución de verificación de D2; y sólo
con las cifras idénticas delante se actualizan el README y los documentos de contexto. Escribir
antes la declaración de que la línea base es histórica sería declararlo sin saber si el borrado fue
limpio.

## Risks / Trade-offs

- **El borrado se lleva algo que estaba en la ruta viva** → Es el riesgo principal y el único que
  importa. Mitigación: la re-ejecución de D2 con exigencia de **cifras idénticas**, no de cifras
  parecidas; y `uv run pytest` completo antes y después, comparando **nombres** de tests que fallan
  y no su recuento, como manda el `CLAUDE.md`.
- **Se pierde la capacidad de re-ejecutar la línea base** → Aceptado a propósito y declarado en el
  README (D1). Lo que se conserva es la procedencia citable.
- **Abrirlo antes de que C25 esté archivado** → Retiraría el andamio mientras sostiene la tabla.
  Mitigación: es prerrequisito duro, anotado en la ficha y en el proposal; la tarea 1 lo verifica.
- **Retirar una perilla que sí tenía lector** → Mitigación: D3, comprobación por búsqueda sobre el
  árbol y no por memoria.
- **Tentación de "aprovechar" para ajustar algo** → Un change de limpieza que mueve una cifra deja
  de ser verificable. Mitigación: D2 convierte cualquier delta en fallo.

## Migration Plan

1. Verificar que C25 está **archivado** y su tabla publicada.
2. Retirar el modo plano, la variante adaptativa perdedora y las perillas sin lector.
3. `uv run pytest` en verde; caen los tests del comportamiento retirado y **ninguno más**.
4. Re-ejecutar la tabla una vez: las filas supervivientes, cifras **idénticas**.
5. Actualizar README y documentos de contexto con la declaración de D1.

**Rollback:** es un borrado sin migración ni cambio de contrato, así que revertir es revertir el
commit. Nada en los datos ni en el esquema cambia, y ninguna configuración de despliegue depende de
las perillas retiradas — si alguna las trae, el arranque debe fallar con un mensaje que las nombre
en lugar de ignorarlas en silencio.

## Open Questions

| # | Abierta | Cuándo se cierra |
|---|---|---|
| 1 | ¿Qué variante adaptativa se retira, la continua o la binaria? | Lo decide el barrido de la fase A de C25 |
| 2 | ¿Qué perillas quedan exactamente sin lector? | Se comprueba por búsqueda al abrir el change (D3), no se predice aquí |
| 3 | ¿Se retira también el `k` o la profundidad si el barrido los deja fijados? | No: siguen siendo el mecanismo de calibración de C26 y C38, así que conservan lector |
| 4 | ¿Se conserva `v2-hibrido.yaml` como fichero documental sin ser ejecutable? | Decisión al aplicar. Por defecto **se conserva con una cabecera que declara que es histórico**, porque el informe lo cita por identificador |
