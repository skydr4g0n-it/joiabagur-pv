# C25bis — implementación: el borrado, y la prueba de que no movió nada

**Change:** [`clean-plain-fusion`](../../../openspec/changes/clean-plain-fusion/) · **Fecha:** 2026-09-12
**Rama:** `c25bis-clean-plain-fusion` · **Decisiones previas:** [`c25bis-exploration-decisions.md`](c25bis-exploration-decisions.md)

Este change no tiene autoridad para mover una cifra. Su entrega, por tanto, no es una mejora sino
una **demostración de invariancia**: que retirar el andamio de C25 no cambió un solo resultado.
Esto es lo que se midió para demostrarlo, y lo que se encontró de paso.

---

## 1. La prueba central: 315 filas idénticas

El listón se subió de *«cifras idénticas»* a *«líneas idénticas»* antes de empezar, porque seis
agregados iguales pueden esconder reordenaciones que se compensan y la lista `ranked` por consulta
no. Dos corridas completas del arnés, una antes del borrado y otra después:

| | previa | posterior |
|---|---|---|
| identificador | `334bd6dc-b6c9-4c64-8738-993feb765014` | `e0a10740-4c61-466c-b86d-56a6df94b1a0` |
| versión del golden set | `1:198c4af44506` | `1:198c4af44506` |
| huella del conjunto indexado | `051a6b06021efc3f…` | `051a6b06021efc3f…` |
| revisión del código | `b16242203ba3+dirty` | `59f63ef04738+dirty` |

**La revisión es el único elemento de la procedencia que difiere, y esa diferencia *es* la
hipótesis bajo prueba.** La excepción se declaró por escrito antes de medir y está acotada: si
hubiera diferido la versión del golden set, la huella del índice o el modelo de embeddings, la
verificación sería **inválida** y no simplemente floja.

Emparejando por `(config_id, query_id)` sobre `ranked` **completo** y todas las métricas, para las
cinco configuraciones supervivientes:

```
previa   : 334bd6dc-…jsonl  -> 315 filas
posterior: e0a10740-…jsonl  -> 315 filas
OK: las 315 filas son IDENTICAS, `ranked` completo incluido.
```

Y las cifras publicadas coinciden a tres decimales en las cinco filas:

| configuración | fusión | nDCG@5 | nDCG@5 bin | nDCG@5 oper | Recall@5 | P@3 | MRR |
|---|---|---:|---:|---:|---:|---:|---:|
| `v0-nombre` | `none` | 0.092 | 0.086 | — | 0.079 | 0.039 | 0.116 |
| `v0-fts` | `none` | 0.507 | 0.579 | — | 0.558 | 0.550 | 0.661 |
| `v1-vectorial` | `none` | 0.612 | 0.648 | — | 0.637 | 0.628 | 0.720 |
| `v2b-fusion` | `branch` | 0.740 | 0.770 | — | 0.758 | 0.713 | 0.834 |
| `v3-senales` | `branch` | 0.729 | 0.755 | 0.732 | 0.744 | 0.698 | 0.824 |

**Un hallazgo que refuta una cautela propia.** La corrida previa reproduce la **tabla publicada de
C25 fila por fila**, a tres decimales, en las seis filas — incluida `v2-hibrido`. La exploración
había advertido que la tabla publicada no servía como referencia por haberse tomado `+dirty`, con
código que aterrizó en el commit siguiente; medido, esa diferencia no afectaba a ninguna de estas
cifras. La comparación se hizo igualmente contra la corrida previa, porque lo que la hace válida es
salir del mismo árbol y no que coincida.

## 2. La suite: de 994 a 997, con cero fallos a los dos lados

La línea base de la suite se tomó **antes de tocar nada** y resultó ser más estricta de lo que el
`CLAUDE.md` prevé para este repositorio: **`994 passed, 0 failed`**. La lista de nombres en rojo
estaba vacía, así que la comparación posterior no admite el margen habitual.

Después del borrado: **`997 passed, 0 failed`**. La cuenta cuadra exactamente.

**Cuatro retirados**, todos por nombrar comportamiento que ya no existe:

| test | por qué cae |
|---|---|
| `test_flat_fusion_mode_reproduces_the_published_baseline` | ejercitaba la composición retirada |
| `test_vector_branch_weight_defaults_below_lexical` | fijaba un peso **por lista**, y su requisito ya estaba declarado retirado desde C25 |
| `test_the_two_lexical_weights_sum_to_one_lexical_list` | ídem |
| `test_baseline_row_is_still_selectable_and_reproducible` | afirmaba justo lo que este change sustituye por conservación |

**Siete añadidos**, de los que sólo uno es comportamiento nuevo —ninguno lo es en producción—:

| test | qué fija |
|---|---|
| `test_the_flat_arithmetic_that_was_retired_buried_the_vector_leader` | el **fósil**: por qué se retiró, sobre `fuse()` a solas |
| `test_no_flat_fusion_path_exists` | que no vuelve por un ajuste ni por un parámetro |
| `test_the_internal_lexical_weights_are_equal_and_not_settable` | que no sobrevive ningún peso por lista |
| `test_the_default_branch_ratio_is_one_vote_each` | el pin que sustituye al del peso vectorial |
| `test_the_retired_baseline_config_no_longer_loads` | que el YAML archivado se conserva **y** se rechaza |
| `test_the_baseline_row_is_archived_rather_than_selectable` | conservación en lugar de reproducibilidad |
| `test_a_retired_fusion_knob_no_longer_exists_and_exporting_it_does_nothing` | que una exportación rancia es inerte |

**Dos se estrecharon en vez de caer**, y salen reforzados:
`test_vector_top_hit_reaches_the_top_five_without_lexical_consensus` y
`test_low_confidence_means_branch_disagreement_and_not_list_disagreement` perdieron su segundo
brazo —servir el mismo corpus bajo la composición retirada— y lo que era una comparación entre dos
composiciones pasa a estar garantizado por la **forma del código**.

## 3. El inventario retirado

| Elemento | Lector que tenía | Por qué se retira |
|---|---|---|
| `JPV_FUSION_MODE` | selector del orquestador y validador propio | Seleccionaba un camino medido como defectuoso |
| `JPV_RRF_WEIGHT_TYPED` | **etapa 1 de la fusión viva** | La spec exige que sea igual a su pareja y prohíbe barrerla: una perilla que la norma prohíbe mover no es una perilla muerta, es una **trampa** |
| `JPV_RRF_WEIGHT_EXPANDED` | ídem | ídem |
| `JPV_RRF_WEIGHT_VECTOR` | sólo la rama plana | El único genuinamente sin lector |
| `EvalConfig.fusion` y sus tres `weight_*` | configuraciones de evaluación | Sin composición que elegir ni pesos por lista que fijar |
| `FusionFingerprint.mode` y sus tres `weight_*` | huella de la captura del barrido | No pueden diferir entre captura y re-puntuación |

**Lo que NO se retiró, y se comprobó que conserva lector:** los pesos por rama, el umbral de
distancia, `k`, la profundidad, los pesos de negocio y `coverage_rule`. Y **`Provenance.fusion_mode`
se conserva**, poblado desde constante de módulo: el selector muere, el registro vive.

**Argumento de identidad, que es lo que permitió exigir líneas idénticas y no parecidas.** En la
etapa 1 ambas listas llevan el mismo peso, RRF escala linealmente con el peso, y de esa etapa sólo
se reenvía el **orden** a la etapa 2 — la magnitud se descarta. Con pesos iguales, cualquier valor
produce el mismo resultado. El borrado era bit-idéntico **por construcción** antes de medirse.

## 4. Lo que el borrado encontró y la ficha no preveía

**Tres configuraciones congeladas hubo que editarlas, y las tres claves eran inertes.** La guarda
de claves desconocidas de `evals/configs.py` —que existía desde C24— disparó contra las
supervivientes: `v1-vectorial.yaml` seguía nombrando los tres pesos por lista, y `v2b-fusion.yaml`
y `v3-senales.yaml` seguían fijando `fusion: branch`. Ninguna movía nada: `v1-vectorial` corre con
`mode: vector`, es decir con la rama léxica apagada, así que las listas que esos pesos gobernaban
no llegaban a existir; y `branch` era el valor vivo por defecto. Editar ficheros marcados como
congelados no era el plan, así que cada uno lleva escrito por qué la retirada no los mueve.

**El escenario del fallo ruidoso se cumplió sin escribir código.** La decisión D-G lo acotó a la
configuración de evaluación, donde el daño es de medición —una fila que mide otra cosa— y no de
creencia. Esa guarda ya existía, y `test_the_retired_baseline_config_no_longer_loads` la ejercita
ahora contra el propio artefacto archivado: el YAML retirado falla nombrando las claves que ya no
existen. **Cero código nuevo** para el requisito que la ficha creía que exigiría un validador de
entorno.

**La comprobación de despliegue encontró documentación en vez de configuración.** La tarea 4.7
buscaba una perilla retirada en `.env`, SSM o compose y no halló ninguna —ni en `backend/.env`, ni
en `.env.example`, ni en `terraform/`, ni en los compose del backend; `ai-service/` no tiene ni
`.env.example` ni compose propio—. Lo que sí la nombraba era **`openspec/config.yaml`**, el
contexto que todo agente carga primero, y además describía la fusión plana como seleccionable. No
invalida la comprobación, pero habría dejado obsoleto el documento de entrada: se corrigió.

## 5. Desviaciones declaradas

- **La tarea 3.10 pedía `test_no_per_list_weight_is_defined` como test propio y no existe con ese
  nombre.** Lo que el escenario de la spec exige está cubierto en dos: `test_no_flat_fusion_path_
  exists` para la ausencia de camino y `test_the_internal_lexical_weights_are_equal_and_not_
  settable` para la de pesos por lista. La garantía es la misma; el nombre prometido no está, y se
  dice aquí en vez de dar la tarea por cumplida al pie de la letra.
- **Las capturas del barrido anteriores a este change dejan de poder cargarse**, porque
  `FusionFingerprint` perdió cuatro campos. Es el resultado correcto —su ventana se produjo bajo una
  composición que el código ya no reproduce— y no se pierde nada versionado: las capturas no son
  artefactos del repositorio. Se vuelve a ejecutar la fase de captura cuando haga falta.
- **El campo `mode` desapareció de la traza `stage=fuse`.** Un campo de log que sólo puede imprimir
  un valor es ruido, y el requisito que obligaba a emitirlo ahí es justamente el que este change
  elimina. Lo que la corrida compuso sigue **registrado** donde se puede actuar sobre ello: en la
  procedencia de la evaluación.

## 6. Lo que sigue declarado y sin cerrar

- **El brazo de control de la regla de cobertura no tiene fila propia** en la tabla y sólo es
  alcanzable a mano: ninguna configuración superviviente fija `coverage_rule: none`. No se añadió
  ninguna —este change no tiene autoridad sobre la tabla— pero la próxima profundización del golden
  set lo necesitará para re-confirmar el +0,128.
- **`coverage_rule` no es una marcha atrás de despliegue.** No es campo de `Settings` y el router no
  lo pasa, así que en producción la regla está fijada por código. La spec decía lo contrario y se
  corrigió en una cláusula.
- **Las tres brechas que C25 dejó abiertas siguen abiertas**: `Recall@5` 0,758 contra 0,85,
  abstención 0,150 contra 0,80, y `v3` sin batir a `v2b` por el margen. Este change no las toca.
