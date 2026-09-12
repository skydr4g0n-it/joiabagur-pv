## REMOVED Requirements

### Requirement: The flat fusion remains selectable so the published baseline stays reproducible

**Reason**: El requisito existía para que la fila de referencia de la tabla de ablations pudiese
re-medirse mientras el change que corrigió la fusión demostraba su propia mejora. Publicada la
tabla y congelada la configuración, deja de sostener nada y pasa a ser lo contrario: un camino
seleccionable cuya aritmética el proyecto midió como defectuosa —con los pesos por lista, los 60
documentos léxicos ganan al mejor candidato vectorial en toda consulta, y el documento de grado
máximo cae a la posición 33 en tres consultas del golden set—. Un camino muerto que se puede
activar por error es cómo un defecto corregido regresa.

**Migration**: La fusión en dos etapas con pesos por rama es la única, y ya era el valor por
defecto. Las cifras de la fila de referencia se conservan como artefactos versionados —el informe
en `ai-service/evals/results/`, su JSONL por consulta y su propio fichero de configuración, movido
a un directorio de retiradas— y la fila pasa a ser **histórica y no re-ejecutable**, lo que el
requisito modificado de `retrieval-evaluation` declara.

La obligación de registrar el modo de fusión **no desaparece con este requisito**: se traslada al
requisito de comparabilidad de `retrieval-evaluation`, porque lo que se retira es la capacidad de
**elegir** la composición, no la de **saber** cuál estuvo en vigor.

Una configuración de despliegue que todavía nombre la perilla retirada **no tiene efecto**, porque
la perilla ya no existe; no se añade ningún mecanismo que haga fallar el arranque por ello. El
riesgo que eso dejaría abierto —publicar una fila creyendo haber seleccionado la composición
antigua— lo cierra el registro de la procedencia, que declara la composición realmente aplicada y
no la que alguien pretendió.

## MODIFIED Requirements

### Requirement: Weights and smoothing are configuration, and the weakest branch weighs less

The per-**branch** weights and the smoothing constant MUST be read from settings and MUST NOT be written into the code. Their effective values MUST also travel as parameters of the retrieval orchestration call, so that several configurations can be evaluated in one process without restarting it and without adding a field to the retrieval request schema.

**The fusion is composed in two stages, and that is the only composition that exists.** The lists belonging to the lexical branch MUST first be fused with each other into one ranked lexical list, and that list MUST then be fused with the vector list under the per-branch weights. A branch's total vote MUST be exactly its declared weight, whatever number of lists it is composed of and however many of them returned candidates. **A single flat fusion over every list MUST NOT be implemented at all**, not merely be non-default, because it makes the effective weight of a branch depend on how many of its own lists happened to match — a property of the query that no configuration declares — and because it was measured to prevent the vector branch from placing any candidate the lexical branch did not also produce.

**The weights internal to the lexical branch are not configuration.** They MUST be equal, MUST NOT be swept and MUST NOT be settable, because the measured evidence establishes that both of its lists are necessary and not that either is worth more. A value that the specification forbids moving is not a knob that happens to be fixed: it is an invitation to violate the requirement with nothing to detect it. Only their order reaches the second stage, so their common value cannot change any result.

Per-list weights MUST NOT exist in settings, in an evaluation configuration or as parameters of the orchestration call.

The earlier requirement that the vector weight be lower than either lexical weight was withdrawn when the two-stage composition was adopted, and the per-list weights it spoke of no longer exist; no test may pin it.

Only the **ratio** of the branch weights may change the order, so a calibration sweep over them MUST be one-dimensional and MUST be expressed as that ratio. The default ratio MUST be declared with a rationale that can be stated in one sentence.

#### Scenario: Weights are not hardcoded

- **WHEN** the fused retrieval runs
- **THEN** the branch weights and the smoothing constant come from settings or from the call parameters
- **AND** no branch weight value is written into the fusion module

#### Scenario: Two configurations run in one process

- **GIVEN** the settings supply a default set of weights
- **WHEN** the orchestration call is made once with those weights and once with different ones
- **THEN** both calls succeed without restarting the process
- **AND** neither call mutates the settings object

#### Scenario: No flat fusion path exists

- **WHEN** the fusion module and the settings are inspected
- **THEN** no configuration selects a single-stage fusion over every list
- **AND** no per-list weight is defined

#### Scenario: An evaluation configuration naming a retired knob fails loudly

- **GIVEN** an evaluation configuration that names a retired fusion knob
- **WHEN** it is loaded
- **THEN** the load fails and names the retired knob
- **AND** no row of the ablation table is produced under a knob that was silently ignored

#### Scenario: A branch's vote does not depend on how many of its lists matched

- **GIVEN** a query for which both lexical lists return the same document
- **AND** a query for which only one lexical list returns anything
- **WHEN** each is fused
- **THEN** the lexical branch holds its declared weight in both cases
- **AND** the position at which the vector branch's best candidate can enter the result is the same for both

#### Scenario: The vector branch can place a candidate without lexical consensus

- **GIVEN** a query whose best-matching document the lexical branch ranks nowhere near the top
- **AND** which the vector branch ranks first
- **WHEN** the fusion runs under the default branch weights
- **THEN** that document appears among the first few fused candidates
- **AND** it is not placed behind every candidate the lexical branch produced

#### Scenario: Documents both branches agree on come first

- **GIVEN** a candidate produced by both branches and candidates produced by only one
- **WHEN** the fusion runs under equal branch weights
- **THEN** the candidate both branches produced precedes the others

#### Scenario: The internal lexical weights are equal and not swept

- **WHEN** the calibration report is inspected
- **THEN** the weights internal to the lexical branch appear as equal declared values
- **AND** they are not listed among the weights the sweep explored

#### Scenario: The branch-weight sweep is one-dimensional

- **WHEN** the branch weights are calibrated
- **THEN** the grid is expressed as the ratio between them
- **AND** two weight pairs with the same ratio produce the same order

### Requirement: The lexical branch weighs less when its best candidate matched less of the query

The weight of the lexical branch MUST be scaled by how much of the query its best candidate actually matched, measured as the coordination tally the lexical branch already computes. The scaling MUST be continuous and MUST introduce no configured parameter of its own: a branch whose best candidate matched everything the query can express keeps its full declared weight, and one whose best candidate matched a fraction of it keeps that fraction.

**The denominator MUST count only the counting groups whose text-search query is non-empty.** A group whose terms reduce to nothing under the language configuration — a stop word the operator typed — can never match any document, so counting it in the denominator would lower the weight of a query that is in fact fully anchored, and would do so on exactly the queries where the lexical branch is strongest. The denominator MUST be computed in the same statement that computes the coordination tally, so that no additional round trip is spent on it.

The scaling MUST NOT be derived from whether the branch's typed list is empty, because a list built from the operator's literal text can be empty on a query the equivalence groups answer perfectly.

#### Scenario: Full coverage leaves the lexical weight untouched

- **GIVEN** a query whose best lexical candidate matches every counting group with a non-empty text-search query
- **WHEN** the fusion runs
- **THEN** the lexical branch keeps its full declared weight
- **AND** the fused order is the one the unscaled weights produce

#### Scenario: A stop-word group does not lower coverage

- **GIVEN** a query containing a stop word that becomes a counting group with an empty text-search query
- **AND** whose best lexical candidate matches every other counting group
- **WHEN** coverage is computed
- **THEN** the empty group is excluded from the denominator
- **AND** the coverage is full

#### Scenario: Partial coverage lowers the lexical weight

- **GIVEN** a query whose best lexical candidate matches only part of the counting groups that can match
- **WHEN** the fusion runs
- **THEN** the lexical branch's effective weight is scaled down in that proportion
- **AND** the vector branch's candidates rise accordingly

#### Scenario: Coverage introduces no configured parameter

- **WHEN** the settings are inspected
- **THEN** no parameter governs the strength of the coverage scaling
- **AND** the scaling is the proportion itself
- **AND** switching the rule off is available to the evaluation as a control arm, and is an on/off switch rather than a strength
- **AND** it is not a deployment setting, so the live service composes under the adopted rule and a rollback of it is a code change

#### Scenario: The scaling is measured against the rule switched off

- **WHEN** the adaptive scaling is adopted
- **THEN** the report compares it against the same fusion with the rule off
- **AND** states the per-category effect of the difference
- **AND** a comparison between two forms of the scaling is not accepted in place of that control

#### Scenario: An empty typed list does not by itself lower the weight

- **GIVEN** a query whose literal phrasing matches no document but whose equivalence groups match well
- **WHEN** coverage is computed
- **THEN** it is computed from the coordination tally of the group-based list
- **AND** the emptiness of the typed list does not lower it

### Requirement: Fusion tests run offline and pin the measured defaults

Tests for the fusion, the lexical branch and the structural filters MUST run without opening a socket to an embedding provider, an LLM provider or the database, using injected fakes. The suite MUST pin the defaults that were measured and are easy to undo by accident: that the weights internal to the lexical branch are equal and not settable, that the default ratio between the branch weights is the declared one, and that a conjunction is not used between groups. No test may require the index to contain any particular number of rows.

**The suite MUST also pin what was retired**, because a path removed for having been measured as defective can be reintroduced by anybody who does not know it was measured. It MUST fail if a single-stage fusion over every list reappears, and it MUST keep, as pure arithmetic over the fusion primitive, the demonstration of why that composition was retired — with the retired weights as literals local to the test, so that they are a record and not a configuration, and reachable by no configuration at all.

#### Scenario: The suite stays offline

- **WHEN** the fusion and lexical tests run
- **THEN** they use injected fakes
- **AND** no socket is opened to a provider or to the database

#### Scenario: The measured defaults are pinned

- **WHEN** the suite runs
- **THEN** a test fails if the weights internal to the lexical branch stop being equal or become settable
- **AND** a test fails if the default branch-weight ratio changes without the declared rationale changing with it
- **AND** a test fails if the groups are combined conjunctively

#### Scenario: The retired composition stays demonstrated and unreachable

- **WHEN** the suite runs
- **THEN** a test demonstrates, over the fusion primitive alone, that under the retired weights the whole lexical list outscores the vector branch's best candidate
- **AND** that test reaches no setting and no orchestration path
- **AND** a test fails if a single-stage fusion over every list is reintroduced
