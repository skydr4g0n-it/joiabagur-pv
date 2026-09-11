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
defecto. Las cifras de la fila de referencia se conservan como artefacto versionado —el informe en
`ai-service/evals/results/` y su JSONL por consulta— y la fila pasa a ser **histórica y no
re-ejecutable**, lo que el requisito modificado de `retrieval-evaluation` declara. Ninguna
configuración de despliegue debe traer la perilla de modo de fusión; si la trae, el arranque debe
fallar nombrándola en lugar de ignorarla.

## MODIFIED Requirements

### Requirement: The lexical branch weighs less when its best candidate matched less of the query

The weight of the lexical branch MUST be scaled by how much of the query its best candidate actually matched, measured as the coordination tally the lexical branch already computes. **Exactly one scaling form MUST exist in the code** — the one the calibration selected — and the alternative form that lost that comparison MUST NOT remain selectable, because two live mechanisms where the measurement chose one is an invitation to configure the discarded one by accident.

The scaling MUST introduce no configured parameter governing its strength: a branch whose best candidate matched everything the query can express keeps its full declared weight, and one whose best candidate matched a fraction of it keeps that fraction.

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

#### Scenario: Only the selected scaling form exists

- **WHEN** the settings and the fusion module are inspected
- **THEN** exactly one coverage scaling form is implemented
- **AND** no configuration can select the form the calibration discarded

#### Scenario: An empty typed list does not by itself lower the weight

- **GIVEN** a query whose literal phrasing matches no document but whose equivalence groups match well
- **WHEN** coverage is computed
- **THEN** it is computed from the coordination tally of the group-based list
- **AND** the emptiness of the typed list does not lower it

### Requirement: Weights and smoothing are configuration, and the weakest branch weighs less

The per-**branch** weights and the smoothing constant MUST be read from settings and MUST NOT be written into the code. Their effective values MUST also travel as parameters of the retrieval orchestration call, so that several configurations can be evaluated in one process without restarting it and without adding a field to the retrieval request schema.

**The fusion is composed in two stages, and that is the only composition that exists.** The lists belonging to the lexical branch MUST first be fused with each other into one ranked lexical list, and that list MUST then be fused with the vector list under the per-branch weights. A branch's total vote MUST be exactly its declared weight, whatever number of lists it is composed of and however many of them returned candidates. **A single flat fusion over every list MUST NOT be implemented at all**, not merely be non-default, because it makes the effective weight of a branch depend on how many of its own lists happened to match — a property of the query that no configuration declares — and because it was measured to prevent the vector branch from placing any candidate the lexical branch did not also produce.

Per-list weights MUST NOT exist in settings, since no code path reads them.

The weights internal to the lexical branch MUST be equal and MUST NOT be swept, because the measured evidence establishes that both of its lists are necessary and not that either is worth more.

Only the **ratio** of the branch weights may change the order, so a calibration sweep over them MUST be one-dimensional and MUST be expressed as that ratio. The default ratio MUST be declared with a rationale that can be stated in one sentence.

#### Scenario: Weights are not hardcoded

- **WHEN** the fused retrieval runs
- **THEN** the branch weights and the smoothing constant come from settings or from the call parameters
- **AND** no weight value is written into the fusion module

#### Scenario: Two configurations run in one process

- **GIVEN** the settings supply a default set of weights
- **WHEN** the orchestration call is made once with those weights and once with different ones
- **THEN** both calls succeed without restarting the process
- **AND** neither call mutates the settings object

#### Scenario: No flat fusion path exists

- **WHEN** the fusion module and the settings are inspected
- **THEN** no configuration selects a single-stage fusion over every list
- **AND** no per-list weight is defined

#### Scenario: A configuration naming a retired knob fails loudly

- **GIVEN** a deployment configuration or an evaluation configuration that names a retired fusion knob
- **WHEN** it is loaded
- **THEN** the load fails and names the retired knob
- **AND** the value is not silently ignored

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
