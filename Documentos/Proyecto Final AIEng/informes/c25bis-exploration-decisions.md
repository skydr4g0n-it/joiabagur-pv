# C25bis — decisiones de exploración: retirar el andamio de la fusión plana

**Change:** [`clean-plain-fusion`](../../../openspec/changes/archive/2026-09-12-clean-plain-fusion/) · **Fecha:** 2026-09-12
**Árbol explorado:** `ai-eng` en `b162422` · **Rama de implementación:** `c25bis-clean-plain-fusion`

Este informe recoge lo que la exploración **comprobó sobre el árbol** y las siete decisiones de
arquitectura que salen de ello. No contiene mediciones nuevas: C25bis no tiene autoridad para
mover una cifra, y este documento tampoco.

Su razón de ser es que la ficha del plan y los artefactos generados el 11 de septiembre describen
un inventario **supuesto**, y la regla D3 del propio `design.md` exige uno **comprobado**. Al
comprobarlo, tres de sus afirmaciones resultaron falsas del árbol. Se corrigen aquí.

---

## 1. El inventario, comprobado por búsqueda y no por memoria

| Elemento | Lectores reales, verificados | Veredicto |
|---|---|---|
| `jpv_fusion_mode` / `JPV_FUSION_MODE` | **Selector**: [`orchestrator.py`](../../../ai-service/src/jbg_ai/retrieval/orchestrator.py) (218-220, 367, 475-490, 665), validador `known_fusion_mode` en [`settings.py`](../../../ai-service/src/jbg_ai/config/settings.py) (717-727) · **Registro**: `Provenance.fusion_mode`, columna `fusión` del informe, `metrics` jsonb de `ai.eval_run`, `FusionFingerprint.mode` | El **selector** muere; el **registro** vive (D-B) |
| `jpv_rrf_weight_vector` = 0,33 | Únicamente `flat_weights[2]` | Muere limpio |
| `jpv_rrf_weight_typed` = 0,5 | `flat_weights[0]` **y `internal_weights[0]`, que es ruta viva** (etapa 1 de `_fuse_two_stage`) | La propuesta afirmaba que sólo los leía el modo plano. **Falso.** Muere como ajuste, sobrevive como constante igual |
| `jpv_rrf_weight_expanded` = 0,5 | Ídem | Ídem |
| «La variante de ponderación adaptativa que perdió el barrido» | **No existe.** `COVERAGE_RULES == ("continuous", "none")`, y la forma binaria con alfa se implementó y se retiró **dentro de C25** | Pata de alcance **vacía**. Se declara cumplida-por-C25 (D-D) |
| `coverage_rule = "none"` | Brazo de control del +0,128 y marcha atrás declarada. **No es campo de `Settings`** y el router no lo pasa ([`retrieval.py`](../../../ai-service/src/jbg_ai/api/routers/retrieval.py) 118-124) | Se conserva. No pertenece a la clase de riesgo de este change |
| Configuración de despliegue que traiga una perilla retirada | **Ninguna**: no hay `ai-service/.env.example`, ni `JPV_` en `terraform/`, ni compose de ai-service | La amenaza que el change suponía no existe hoy (D-G) |

### Las cuatro contradicciones internas encontradas

1. **La delta de `hybrid-fusion` perdía dos escenarios vivos.** Su bloque `MODIFIED` de
   *«The lexical branch weighs less…»* eliminaba *Coverage introduces no configured parameter*
   —que declara `none` como control y marcha atrás— y *The scaling is measured against the rule
   switched off* —que **prohíbe** sustituir el control por una comparación forma-contra-forma—, y
   sustituía el `MUST be continuous` por un *«exactly one scaling form»* que ya no nombra la forma.
   Un change de limpieza que afloja una norma es lo contrario de lo que dice ser.
2. **La spec viva ya se contradecía desde C25.** *«Weights and smoothing…»* declara
   **retirado** el requisito de que el peso vectorial sea menor que los léxicos, y
   *«Fusion tests run offline and pin the measured defaults»* sigue exigiendo el test que lo fija
   — y el test existe: [`test_settings.py`](../../../ai-service/tests/config/test_settings.py) 435-437.
3. **Las tareas 3.5 y 3.8 se anulaban entre sí.** Conservar `v2-hibrido.yaml` en su sitio rompe
   `load_all()`, que hace `glob("*.yaml")` sobre el directorio y carga **cada** fichero.
4. **La tabla publicada no sirve como referencia de comparación.** El informe de C25 declara que
   su corrida se tomó `+dirty`, con código que aterrizó en el commit siguiente. Comparar contra
   ella —lo que pedían las tareas 1.4 y 4.3— compararía dos árboles distintos.

---

## 2. Las siete decisiones

### D-A · La fila de referencia se cita desde fuera de la tabla, no se congela dentro

**Decisión.** Al retirar el modo plano, `v2-hibrido` deja de ser una fila. Sus cifras y su
procedencia quedan como artefactos versionados —[`c25-baselines-2026-09-11.md`](../../../ai-service/evals/results/c25-baselines-2026-09-11.md),
el JSONL por consulta `d91d4864-…` y, por D-E, el propio YAML— y toda cita la marca como
**histórica y no re-ejecutable**. El arnés **no** gana un cargador de filas archivadas.

**Evidencia.** La spec viva ya resolvió el caso simétrico: `Deepening the golden set re-runs every
row` ordena que *«figures from the previous version are cited as historical rather than as
comparable rows»* y que *«every row reports the same golden set version and the same provenance
tuple»*. Una fila leída de artefacto metería una segunda tupla de procedencia en una misma tabla,
contra ese requisito.

**Alternativas descartadas.** (a) Mantener el modo plano sólo para el arnés — es lo que este
change existe para evitar, y un modo que sólo usan los tests deja de estar ejercitado por la ruta
viva. (b) Fila congelada leída del JSONL — código nuevo en un change de limpieza, y procedencia
mixta en una misma tabla. (c) Reimplementar el pipeline dentro del arnés — prohibido por
`A retired configuration is not reimplemented in the harness` y por la doctrina de C24.

**Consecuencia.** No hace falta delta sobre `Deepening the golden set…`: una configuración
retirada deja de ser fila, y el requisito habla de las filas que existen.

### D-B · El selector muere, el registro vive

**Decisión.** `JPV_FUSION_MODE` desaparece como ajuste de entorno y como clave de configuración de
evaluación. `Provenance.fusion_mode` **se conserva**, poblado desde constante de módulo y no desde
el entorno.

**Evidencia.** El docstring de [`provenance.py`](../../../ai-service/src/jbg_ai/evals/provenance.py)
dice que el modo pasó a ser el sexto elemento *«porque C25 lo hizo uno»*, cuando la fusión plana se
volvió seleccionable. Retirar el selector devuelve esa lógica al `git_sha` — pero el registro sigue
haciendo dos trabajos que nada más hace: `differences()` marca **no comparable** una corrida
archivada en `flat` frente a una nueva en `branch`, y la columna `fusión` del informe distingue las
filas que fusionan de las que no (`NO_FUSION = "none"` en los cuatro degradados).

**Y cierra el único agujero que habría justificado una lista negra de perillas retiradas** (D-G):
si alguien exportase `JPV_FUSION_MODE=flat` creyendo reproducir la línea base, la fila resultante se
imprimiría marcada `branch` en su propia tabla.

**Principio que queda escrito.** *Una perilla es algo que se puede poner; un registro es algo que se
escribe.* Este change retira perillas.

**Consecuencia normativa.** El requisito vivo `A run is comparable to another only when its
provenance matches` enumera **cinco** elementos y no nombra el modo: su único mandato vivía dentro
del requisito que esta delta elimina. Conservar el registro exige **añadirlo a ese requisito**.

### D-C · Mueren los tres pesos por lista; la etapa 1 queda con pesos iguales no configurables

**Decisión.** `jpv_rrf_weight_typed`, `jpv_rrf_weight_expanded` y `jpv_rrf_weight_vector` salen de
`Settings`, de `EvalConfig`, de `FusionFingerprint` y de los parámetros de `retrieve_products`. La
etapa 1 de la fusión pasa a componerse con **pesos iguales declarados en el módulo**.

**Evidencia de que el borrado es bit-idéntico por construcción, no por suerte.** En la etapa 1 ambas
listas llevan el mismo peso; RRF escala linealmente con el peso, y de la etapa 1 **sólo se reenvía
el orden** (`lexical_ids`), nunca la magnitud. Con pesos iguales, cualquier valor produce el mismo
orden y el mismo resultado final.

**Por qué no bastaba con retirar sólo `weight_vector`.** La spec viva ya ordena que los pesos
internos *«MUST be equal and MUST NOT be swept»*. Una perilla que existe y que la norma prohíbe
mover no es una perilla muerta: es una **trampa**, porque ponerla desigual viola una spec sin que
nada lo detecte.

**Consecuencia normativa.** `Fusion tests run offline and pin the measured defaults` exige hoy un
test que falle *«if the default vector weight is raised to or above the lexical weight»*. Ese peso
es el de lista y desaparece — y el requisito que lo fijaba ya estaba **declarado retirado** por
`Weights and smoothing…` desde C25. Hace falta `MODIFIED` que sustituya el pin por uno cierto.

### D-D · `none` se queda, la pata 2 se declara cumplida, y su requisito se corrige en una cláusula

**Decisión.** No se retira nada de la regla de cobertura. La pata *«retirar la variante adaptativa
que perdió el barrido»* se declara **cumplida por C25** y se comprueba en vez de ejecutarse. El
bloque `MODIFIED` sobre *«The lexical branch weighs less…»* se **reduce**: reproduce el requisito
**verbatim**, con sus seis escenarios y su `MUST be continuous`, y corrige **una** cláusula.

**Evidencia de que `none` está mandatado.** Dentro del mismo requisito:
*«switching the rule off is available as a control and a rollback, which is not a strength»* y
*«a comparison between two forms of the scaling is not accepted in place of that control»*.

**Evidencia de que la pata está cumplida y su guarda ya es ejecutable.**
[`test_orchestrator.py`](../../../ai-service/tests/retrieval/test_orchestrator.py) 1112-1128 declara
que la forma binaria *«was implemented and withdrawn… it lost on cost rather than on result»*,
afirma `COVERAGE_RULES == ("continuous", "none")` y comprueba que `rule="binary"` levanta.

**La cláusula que se corrige, y por qué.** La spec promete que apagar la regla es un *rollback*.
Comprobado: `coverage_rule` **no es campo de `Settings`** y el router no lo pasa, así que en
producción la regla está fijada a `continuous` por código. La marcha atrás es cierta del arnés y
falsa del servicio:

```diff
- AND switching the rule off is available as a control and a rollback, which is not a strength
+ AND switching the rule off is available to the evaluation as a control arm, not as a deployment
+     setting, and it is an on/off switch rather than a strength
```

**Alternativa descartada: retirar `none`.** Rompería dos escenarios vivos, dejaría el +0,128 sin
control con el que re-confirmarse cuando el golden set crezca, y `coverage_rule` ni siquiera es una
perilla de entorno.

**Hueco declarado y no cerrado.** Ninguna configuración superviviente fija `coverage_rule: none`: el
brazo de control sólo es alcanzable a mano. **No se añade fila** —este change no tiene autoridad
sobre la tabla— pero queda escrito, porque la próxima profundización del golden set lo necesitará.

### D-E · `v2-hibrido.yaml` se conserva en `evals/configs/retired/`

**Decisión.** El fichero se mueve a `ai-service/evals/configs/retired/v2-hibrido.yaml` con una
cabecera que declara que es histórico. `v2-hibrido` sale de `ABLATION_ORDER` y de `POOLED`.

**Evidencia de que la inercia es estructural.** `CONFIG_DIR.glob("*.yaml")` **no es recursivo**
([`configs.py`](../../../ai-service/src/jbg_ai/evals/configs.py) 155): el subdirectorio es
inalcanzable por cómo está escrito el cargador, no por un acuerdo sobre nombres de fichero. Y
`load_config("v2-hibrido")` falla nombrando la ruta y listando las disponibles.

**Evidencia de que borrarlo perdería algo.** El informe publicado lleva etiqueta, columna `fusión`,
procedencia y cifras — **no lleva los valores de las perillas** (`weight_typed`, `weight_expanded`,
`weight_vector`, `rrf_k`, `branch_depth`, `abstain`, `pos_prefilter`). El YAML es el único artefacto
donde vive la configuración misma, y el proyecto ya rechazó por escrito el argumento de *«está en
git»*: *«evidencia que vive sólo en una base de datos es evidencia que nadie diffea»*.

**Lo que no diferencia a las alternativas.** Mover, renombrar o borrar obliga igualmente a tocar
`ABLATION_ORDER`, `POOLED` y los cuatro tests que lo cargan de disco, porque
[`test_baselines_and_configs.py`](../../../ai-service/tests/evals/test_baselines_and_configs.py)
102-105 exige igualdad **exacta** entre `load_all()` y `ABLATION_ORDER`.

**Coherencia con D-B.** Sacarlo de `POOLED` no contradice que `judgements.jsonl` siga nombrándolo en
`pooled_in`: `POOLED` es quién *entra* al próximo pooling; `pooled_in` es el registro de quién
*entró*. Perilla contra registro, otra vez.

**Regalo colateral.** El artefacto archivado se convierte en la prueba ejecutable de que la retirada
está completa, usando la guarda que **ya existe** en `configs.py` 127-131:

```python
def test_the_retired_baseline_config_no_longer_loads() -> None:
    with pytest.raises(ConfigurationError, match="unknown keys"):
        load_config("v2-hibrido", directory=CONFIG_DIR / "retired")
```

### D-F · Se conserva la demostración del defecto, sin que sea activable

**Decisión.** El testigo del defecto deja de ser **un camino** y pasa a ser **un fósil en un test**:
una prueba de aritmética pura sobre `fuse()` y `RankedList`, sin `_fuse_branches`, sin `Settings` y
sin modo, con los pesos de C21 como **literales locales comentados como históricos**.

**Qué afirma.** Que con `w_lex = 1,00` sobre hasta 120 documentos y `w_vec = 0,33` sobre 60, el peor
documento léxico puntúa `1,00/120 = 0,008333` y el mejor vectorial `0,33/61 = 0,005410`; y que con
una lista léxica de 32 documentos el #1 vectorial cae a la **posición 33**.

**Por qué no es activable.** `fuse()` es puro y sin dominio, ninguna configuración lo selecciona, y
los pesos dejan de leerse de `FUSION_DEFAULTS` — que es justo lo que los convierte en fósil en vez
de en configuración.

**Qué muere con ello.** Los cuatro sitios que hoy usan `fusion="flat"` como testigo diferencial:
[`test_fusion.py`](../../../ai-service/tests/retrieval/test_fusion.py) 259 y 299, y
[`test_orchestrator.py`](../../../ai-service/tests/retrieval/test_orchestrator.py) 776, 876 y 893.

### D-G · La obligación de «fallar nombrando la perilla» se acota a la evaluación

**Decisión.** No se añade lista negra de nombres retirados validada contra el entorno. El escenario
se **corrige** para que la obligación caiga donde el daño es de medición y no de creencia.

**Evidencia decisiva — el precedente es de tres semanas antes y del mismo change.** El commit
`27dfe66` (*«Retira la rotacion del orden»*, 11-09) eliminó `JPV_BUSINESS_WEIGHT_ROTATION`, que
tenía campo, default, fallback de cadena en blanco **y su propio `field_validator`**, y no añadió
guarda alguna: `grep os.environ` sobre `settings.py` no devuelve nada. Exigírsela ahora a
`JPV_FUSION_MODE` sería una asimetría sin fundamento.

**La asimetría que decide.** Una perilla **retirada** e ignorada produce el comportamiento **bueno**:
lo silencioso no es un defecto de comportamiento sino de creencia. Una clave mal escrita en un YAML
de evaluación, en cambio, **publica una fila que mide otra cosa** — y esa guarda ya está
implementada y ya tiene test.

**El mecanismo, además, no es el que parece.** Con `extra="ignore"` y `pydantic-settings`, pasar a
`extra="forbid"` **no** caza variables de entorno —ni se recogen— y sólo caza claves del fichero
`.env`, donde reventaría con cualquier clave ajena. Cumplir el escenario tal como está escrito
exigiría un validador que barra `os.environ`, con tres costes: falsifica el *«retira comportamiento
y no introduce ninguno»* de la propuesta, convierte un residuo inofensivo en un **fallo de
arranque**, y se pudre en cuanto alguien retire otra perilla sin ampliarla.

**Redacción sustituta.**

```diff
-#### Scenario: A configuration naming a retired knob fails loudly
-- GIVEN a deployment configuration or an evaluation configuration that names a retired fusion knob
+#### Scenario: An evaluation configuration naming a retired knob fails loudly
+- GIVEN an evaluation configuration that names a retired fusion knob
 - WHEN it is loaded
 - THEN the load fails and names the retired knob
-- AND the value is not silently ignored
+- AND no row of the table is produced under a knob that was silently ignored
```

Más una frase de prosa en el mismo requisito: *un ajuste retirado no puede reintroducirse y su
ausencia debe ser verificable inspeccionando el módulo de settings; un entorno que aún lo nombre no
tiene efecto, y lo que la corrida compuso realmente se lee de su procedencia registrada.*

**Consistencia interna obligatoria.** La nota `**Migration**` del requisito `REMOVED` y el apartado
*Rollback* del `design.md` dicen hoy *«el arranque debe fallar nombrándola»*. **Cambian en el mismo
commit**, o la delta se contradice a sí misma.

---

## 3. Mapa de deltas

### `openspec/changes/clean-plain-fusion/specs/hybrid-fusion/spec.md`

| Bloque | Requisito | Estado |
|---|---|---|
| `## REMOVED` | `The flat fusion remains selectable so the published baseline stays reproducible` | **Ya redactado.** Corregir la nota `Migration` (D-G) |
| `## MODIFIED` | `Weights and smoothing are configuration, and the weakest branch weighs less` | **Ya redactado y bien formado** (conserva los 7 escenarios vivos y añade 2). Acotar el escenario del knob (D-G) |
| `## MODIFIED` | `The lexical branch weighs less when its best candidate matched less of the query` | **Reescribir**: verbatim del vivo, con sus 6 escenarios, corrigiendo una cláusula (D-D) |
| `## MODIFIED` | `Fusion tests run offline and pin the measured defaults` | **Nuevo.** Sustituir el pin del peso de lista (D-C) |

### `openspec/changes/clean-plain-fusion/specs/retrieval-evaluation/spec.md`

| Bloque | Requisito | Estado |
|---|---|---|
| `## MODIFIED` | `An ablation table isolates each change it reports` | **Ya redactado y bien formado** (sustituye a propósito *The baseline row is still reproducible*) |
| `## MODIFIED` | `A run is comparable to another only when its provenance matches` | **Nuevo.** Mandata el sexto elemento de la procedencia (D-B) |

**Sin delta** sobre `Deepening the golden set re-runs every row and re-confirms the decision`: una
configuración retirada deja de ser fila, y el requisito habla de las filas que existen (D-A).

---

## 4. Protocolo de verificación

La base está disponible con el índice en `051a6b06021efc3f…` y sus 1.168 documentos, y los vectores
de consulta están **congelados** en `evals/golden/query_vectors.jsonl`: la verificación no llama a
ningún proveedor y es determinista.

```
 1. ANTES    comprobar index_set_hash == 051a6b06021efc3f…     <-- puerta: si se movió, PARAR
             uv run evals run --all --repeat 3 --out evals/results/c25bis
             → run_id_pre + JSONL versionado
             uv run pytest  → guardar los NOMBRES de los tests en rojo, nunca el recuento
 2. BORRADO
 3. DESPUÉS  uv run evals run  (mismo golden set, misma huella)  → run_id_post
 4. DIFF     por (config_id, query_id), sobre las CINCO supervivientes:
             `ranked` COMPLETO + todas las métricas → CERO líneas distintas
```

**Ejecutado el 2026-09-12.** La puerta da `051a6b06021efc3fb18891ffc7acfa2c6e3499f161aa81e9e96dd061233e073b`
sobre **1168 documentos**, y el golden set es `1:198c4af44506` — las dos coinciden con la tabla
publicada. La corrida previa es **`334bd6dc-b6c9-4c64-8738-993feb765014`**, versionada en
[`ai-service/evals/results/c25bis/`](../../../ai-service/evals/results/c25bis/), con 378 filas.

`--all` incluye también `v2-hibrido`, que todavía se puede ejecutar: es incidental y **no se
publica como una segunda cifra de la referencia**. El diff de la tarea 4 se hace sobre las cinco
configuraciones que sobreviven al borrado.

**Y la cautela sobre el `+dirty` no se materializó:** la corrida previa **reproduce la tabla
publicada fila por fila**, a tres decimales, en las seis filas. Aun así la comparación se hace
contra la corrida previa y no contra la tabla, porque lo que la hace válida es que salga del mismo
árbol y no que coincida.

**Dos correcciones sobre lo que decía D2 del `design.md`:**

- **La referencia es la corrida previa de esta rama, no la tabla publicada.** El informe de C25
  declara que su corrida se tomó `+dirty`, *«con código que aterrizó en `8ace5ac`»*: compararse
  contra ella compararía dos árboles. Las tareas 1.4 y 4.3 originales quedan corregidas.
- **La excepción de procedencia, declarada por escrito.** `comparable_with` excluye sólo
  `config_id`, así que el arnés marcará las dos corridas como no comparables **por `git_sha`** — y
  tiene razón. La hipótesis bajo prueba *es* esa diferencia. `git_sha` es el **único** elemento que
  puede diferir: si difiere cualquier otro, la verificación es **inválida**, no floja.

**Y el listón sube de «cifras idénticas» a «líneas idénticas»**: seis agregados iguales pueden
esconder reordenaciones que se compensan; el `ranked` por consulta no. Como el JSONL de la corrida
previa queda versionado, la comprobación es reproducible por terceros.

**La corrida previa se toma sin `v2-hibrido`**, aunque todavía se pueda: su fila ya está publicada y
congelada, y volver a medirla sólo introduciría una segunda cifra para la misma referencia.

---

## 5. Esqueleto de tareas revisado

### 1 · Puerta de entrada y línea base

1.1 Verificar que C25 está archivado y su tabla publicada · 1.2 Comprobar que
`index_set_hash == 051a6b06021efc3f…`; si se movió, **parar** · 1.3 `uv run pytest`, guardando los
**nombres** de los tests en rojo · 1.4 Corrida previa de las **cinco** configuraciones
supervivientes; anotar `run_id_pre` · 1.5 Registrar que la referencia es esa corrida y **no** la
tabla publicada, con el motivo (`+dirty`)

### 2 · Inventario, comprobado y no recordado

2.1 Confirmar los lectores de cada perilla candidata sobre el árbol · 2.2 Escribir el inventario en
el `design.md` **antes** de borrar · 2.3 Confirmar que **no** entran las que conservan lector: pesos
de negocio, umbral, `k`, profundidad y `coverage_rule` · 2.4 Declarar la **pata 2 cumplida por C25**,
comprobando `COVERAGE_RULES` y que `rule="binary"` levanta

### 3 · El borrado

3.1 `orchestrator.py` — retirar la rama plana, el parámetro `fusion`, los tres `weight_*` y la
ramificación del log · 3.2 `orchestrator.py` — etapa 1 con pesos iguales declarados en el módulo ·
3.3 `settings.py` — retirar `jpv_fusion_mode`, los tres pesos por lista, su validador, sus entradas
en el fallback de blancos y en el perfil canónico · 3.4 `evals/configs.py` — retirar `fusion` y los
tres `weight_*` de `EvalConfig`; sacar `v2-hibrido` de `ABLATION_ORDER` y `POOLED` · 3.5
`evals/sweep.py`, `execute.py`, `runner.py`, `cli.py` — retirar los campos y llamadas
correspondientes · 3.6 `evals/provenance.py` — **conservar** `fusion_mode`, poblado desde constante
de módulo; actualizar el docstring · 3.7 Mover `v2-hibrido.yaml` a `evals/configs/retired/` con
cabecera de histórico · 3.8 Retirar los tests del comportamiento retirado · 3.9 Añadir
`test_no_flat_fusion_path_exists`, `test_no_per_list_weight_is_defined`,
`test_the_retired_baseline_config_no_longer_loads` y el fósil de D-F

### 4 · Verificación

4.1 `uv run pytest`: comparar **nombres** con 1.3; deben caer exactamente los del comportamiento
retirado y **ninguno más** · 4.2 Corrida posterior de las cinco · 4.3 **Diff del JSONL** por
`(config_id, query_id)` sobre `ranked` y todas las métricas: **cero líneas distintas** · 4.4
Comprobar que sólo difiere `git_sha` en la procedencia · 4.5 `openapi.json` sin diff y sin migración
· 4.6 `backend/`, `frontend/`, `terraform/` y `.github/workflows/` sin diff · 4.7 Comprobar que
ninguna configuración de despliegue nombra una perilla retirada (se espera vacío)

### 5 · Specs y documentación, con las cifras idénticas delante

5.1 Las seis deltas del §3 · 5.2 `ai-service/README.md` — retirar la documentación del modo plano y
de los pesos por lista; declarar la fila histórica con enlaces a informe, JSONL y YAML retirado ·
5.3 `ai-service/tests/README.md` · 5.4 Cabecera en el informe de C25 marcando la fila como histórica
· 5.5 Informe de implementación con el inventario retirado y el diff · 5.6 Entrada fechada en el §0
y ficha en el plan · 5.7 `Documentos/epicas.md` · 5.8 `openspec validate --all --strict` en
`0 failed` · 5.9 `/opsx:verify`

---

## 6. Lo que este informe no decide

- **No mueve ninguna cifra** y no tiene autoridad para hacerlo. Si el borrado mueve una, es un fallo
  del borrado: se revierte y se investiga.
- **No toca el golden set, ni `v2b-fusion`, ni `v3-senales`, ni ningún peso calibrado.**
- **No añade la fila de control de la regla de cobertura**, aunque deja el hueco declarado.
- **No corrige las tres brechas que C25 dejó abiertas** (`Recall@5` 0,758 contra 0,85, abstención
  0,150 contra 0,80, y `v3` sin batir a `v2b` por el margen). Siguen declaradas, no cerradas.
