## MODIFIED Requirements

### Requirement: Relevance is graded, and both the graded and the binary readings are published

Each judgement MUST take one of three grades. The report MUST publish every ranking metric twice: once using the grades and once using the binary reading derived from them, where a document is relevant when its grade is at least the intermediate one. The binarisation rule MUST be fixed and declared, never chosen per configuration.

**A third, operational reading MUST be published whenever a configuration under evaluation reorders candidates by a business signal.** Its gain function MUST be a declared function of the labelled grade and the availability signal, MUST be declared before the measurement is executed, and MUST NOT modify the recorded judgements. It MUST be justified from the annotation criterion's own scale rather than from a new constant, because the criterion judges what a piece **is** and never what the shop **has**, so a metric computed over labelled relevance alone is at best orthogonal to availability.

When the readings order the configurations differently, the report MUST state it as a finding.

#### Scenario: Both readings appear in the report

- **WHEN** an evaluation run completes
- **THEN** the report contains the graded metrics and the binary metrics for every configuration
- **AND** the binarisation rule is stated once and applies to all of them

#### Scenario: The operational reading appears when business signals are evaluated

- **WHEN** an evaluation run includes a configuration that reorders by a business signal
- **THEN** the report contains the operational metric alongside the graded and binary ones
- **AND** the gain function is stated once and applies to every configuration

#### Scenario: The operational reading does not alter the judgements

- **GIVEN** a judged document whose availability signal lowers its effective gain
- **WHEN** the operational metric is computed
- **THEN** the judgement file is unchanged
- **AND** the labelled grade is still the one that was recorded

#### Scenario: Divergence between readings is surfaced

- **WHEN** two readings rank two configurations in opposite order
- **THEN** the report states that the comparison is not robust to the choice of scale

### Requirement: Queries used to calibrate the retriever are marked and reported separately

Queries that were used to fix the fusion weights, the branch depth or the coordination rule MUST be marked in the golden set. Every metric MUST be reported three times: over the whole set, over the marked subset only, and over the unmarked subset only.

**The reading that decides is the unmarked subset.** The marked subset MUST be reported as a diagnostic of contamination and MUST NOT veto a decision. The reason is a property of that subset and not of any result taken over it: it is the set of queries selected to calibrate one branch, so using it to arbitrate that branch's weight is validating a model on its training set; and its metrics are saturated, so it cannot register an improvement at all. Whenever the marked subset disagrees with the unmarked one, the report MUST state the disagreement and MUST state which queries are saturated.

The marked subset MUST be reported with the count of its queries that sit at the ceiling of the deciding metric, so a reader can see whether it had room to move.

#### Scenario: The three readings are published

- **WHEN** an evaluation run completes
- **THEN** each metric appears for the whole set, for the tuning subset and for the new queries
- **AND** queries carry the mark that assigns them to a subset

#### Scenario: The unmarked subset decides

- **GIVEN** a configuration that improves on the new queries and does not improve on the tuning subset
- **WHEN** the decision rule is applied
- **THEN** the decision is taken on the new queries
- **AND** the report states the disagreement and names it as contamination of the tuning subset

#### Scenario: Saturation is reported

- **WHEN** the tuning subset is reported
- **THEN** the report states how many of its queries sit at the ceiling of the deciding metric
- **AND** a reader can tell whether that subset had room to improve

#### Scenario: A result that holds on neither subset is not a confirmation

- **WHEN** a configuration fails to improve on the new queries
- **THEN** the report states that the decision is not confirmed
- **AND** the configuration is not adopted

### Requirement: A configured default changes only when the verdict is material

A default retrieval setting MUST NOT be changed on the basis of this evaluation unless the improvement exceeds the agreed margin **in the reading that decides**, and degrades no measured category beyond the agreed margin. The rule MUST be recorded before the measurement is executed, together with which reading decides and why.

The reading that decides MUST be the subset of queries that no calibration has seen. A saturated or contaminated reading MUST NOT block a change; it MUST be reported alongside, so that a reader can weigh it.

The outcome MUST be documented whether or not any default moves.

#### Scenario: A small improvement does not move a default

- **WHEN** a configuration improves the deciding metric by less than the agreed margin
- **THEN** the default is unchanged
- **AND** the report records the measured difference and the decision not to act on it

#### Scenario: A change of default is justified against the written rule

- **WHEN** a default is changed
- **THEN** the report shows every reading and the per-category effect
- **AND** cites the rule that was written before the measurement, including which reading decides

#### Scenario: A degraded category blocks a change

- **WHEN** a configuration improves the deciding metric beyond the margin
- **AND** degrades a measured category beyond the margin
- **THEN** the default is unchanged
- **AND** the report names the category that paid

#### Scenario: A contaminated reading does not block a change

- **GIVEN** a configuration that improves the deciding reading beyond the margin
- **AND** does not improve a reading reported as contaminated or saturated
- **WHEN** the rule is applied
- **THEN** the change is not blocked by that reading
- **AND** the report publishes it alongside the decision

## REMOVED Requirements

### Requirement: Abstention is measured and its distance distribution published, and the threshold is not changed

**Reason**: La prohibición pertenecía al change que construyó este arnés, que no tenía insumo de
calibración propio: medía la abstención y publicaba la distribución precisamente para que un change
posterior pudiese re-fijar el umbral. Ese insumo ya existe, así que la prohibición ha cumplido su
función. Se retira el requisito entero en lugar de modificarlo porque su **nombre** afirma que el
umbral no se cambia, y un requisito cuyo título contradice su cuerpo queda bien formado y falso —
que es peor defecto que uno malformado, porque el validador no lo caza.

**Migration**: Lo sustituye el requisito *«The abstention behaviour may be re-fixed under a rule
written before the measurement, justified from the per-query distribution»*, que conserva las dos
obligaciones de medir y publicar, y añade de qué distribución debe salir la decisión. La capacidad
`retrieval-abstention` recoge el comportamiento de la regla en sí.

## ADDED Requirements

### Requirement: The abstention behaviour may be re-fixed under a rule written before the measurement, justified from the per-query distribution

The evaluation MUST measure abstention over the out-of-domain category and MUST publish the distribution of retrieval distances separating relevant from irrelevant documents.

The live distance threshold and the abstention rule MAY be changed by an evaluation, under a rule recorded **before** the measurement is executed.

A change to the abstention behaviour MUST be justified from the distribution of the **best distance per query**, separating answerable queries from out-of-domain ones, and MUST NOT be justified from the per-document distribution alone, because the two answer different questions: a total overlap between the distances of relevant and irrelevant documents does not imply that the best hit of an answerable query cannot be separated from the best hit of an out-of-domain one. The report MUST publish both distributions, MUST state whether a single value separates the per-query populations, and MUST state whether the adopted rule alters the candidate set or only the decision to serve it.

The report MUST publish, for every candidate rule, the abstention rate over out-of-domain queries **and** the number of answerable queries the rule turned into abstentions.

#### Scenario: The distribution is published per grade

- **WHEN** an evaluation run completes
- **THEN** the report contains the distance distribution of relevant documents and of irrelevant ones
- **AND** states whether the two are separable by a single value

#### Scenario: The per-query distribution is published and decides

- **WHEN** an abstention rule is adopted
- **THEN** the report contains the best-distance distribution of answerable queries and of out-of-domain ones
- **AND** the justification rests on that distribution rather than on the per-document one

#### Scenario: A threshold change cites a rule written beforehand

- **WHEN** the live distance threshold or the abstention rule is changed
- **THEN** the report cites a rule recorded before the measurement was executed
- **AND** states whether the change alters the candidate set

#### Scenario: Both sides of the abstention trade are published

- **WHEN** a candidate abstention rule is reported
- **THEN** its abstention rate over out-of-domain queries appears
- **AND** the number of answerable queries it turned into abstentions appears

### Requirement: An ablation table isolates each change it reports

When one evaluation reports more than one change to the retrieval pipeline, the table MUST contain a row for each change applied **on its own**, in addition to the row that applies them together. A table that reports only the combined result MUST NOT be published, because an improvement it shows cannot be attributed to a cause.

The baseline row MUST remain reproducible: whatever configuration the previously published baseline was measured under MUST still be selectable, so the new table keeps the row every other row is read against.

#### Scenario: Each change has its own row

- **GIVEN** an evaluation that reports both a fusion change and a ranking change
- **WHEN** the ablation table is published
- **THEN** it contains a row with the fusion change alone
- **AND** a row with both changes applied
- **AND** the improvement of each is attributable

#### Scenario: The baseline row is still reproducible

- **WHEN** the baseline configuration is evaluated after the change
- **THEN** it runs under the configuration it was originally measured with
- **AND** reproduces the published figures against the same golden set version

### Requirement: Deepening the golden set re-runs every row and re-confirms the decision

When an evaluation appends judgements or adds queries, the golden set version changes and every previously published figure stops being comparable. Every row of the table MUST therefore be re-run under the new version, so that the published table carries **one** provenance tuple.

A decision taken against the previous version MUST be **re-confirmed** against the new one before it is fixed. Re-confirmation MUST compare the winning configuration against the incumbent; it MUST NOT require re-running the whole calibration grid.

A configuration whose results were substantially unjudged MUST be marked not comparable rather than presented alongside the others.

#### Scenario: Every row shares one provenance

- **GIVEN** judgements were appended and queries were added
- **WHEN** the table is published
- **THEN** every row reports the same golden set version and the same provenance tuple
- **AND** figures from the previous version are cited as historical rather than as comparable rows

#### Scenario: The winner is re-confirmed on the new version

- **GIVEN** a configuration chosen by a sweep run against the previous version
- **WHEN** the golden set version changes
- **THEN** that configuration is compared against the incumbent under the new version before the default is fixed
- **AND** the full grid is not re-run

#### Scenario: An unjudged row is marked not comparable

- **GIVEN** a configuration promoting documents that carry no judgement
- **WHEN** the table is published
- **THEN** its unjudged proportion is reported
- **AND** the row is marked not comparable when that proportion exceeds the declared threshold

### Requirement: An acceptance criterion the evidence cannot reach is restated as a relative one and its gap declared

When a measured baseline shows that an absolute acceptance threshold is beyond the reach of the changes under evaluation, the evaluation MUST NOT be reported as a failure of those changes and MUST NOT relabel data until the figure is met. The criterion MUST be restated as a **relative** one — each configuration beats the one it is built on, in the reading that decides and beyond the agreed margin — and the distance to the absolute threshold MUST be declared as a limitation.

The restatement MUST record the measured figures that justify it.

#### Scenario: The relative criterion is applied and the gap declared

- **GIVEN** a configuration that beats the one it is built on beyond the margin in the deciding reading
- **AND** does not reach the absolute threshold the design states
- **WHEN** the evaluation is reported
- **THEN** the configuration is accepted under the relative criterion
- **AND** the distance to the absolute threshold is declared as a limitation with its measured figures

#### Scenario: Judgements are not relabelled to meet a threshold

- **WHEN** an absolute threshold is not met
- **THEN** the recorded judgements are unchanged
- **AND** the annotation criterion is unchanged
