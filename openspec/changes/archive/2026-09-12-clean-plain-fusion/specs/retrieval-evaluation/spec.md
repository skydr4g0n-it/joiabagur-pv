## MODIFIED Requirements

### Requirement: An ablation table isolates each change it reports

When one evaluation reports more than one change to the retrieval pipeline, the table MUST contain a row for each change applied **on its own**, in addition to the row that applies them together. A table that reports only the combined result MUST NOT be published, because an improvement it shows cannot be attributed to a cause.

**The baseline row MUST remain citable, and citable is not the same as re-executable.** When the configuration a published baseline was measured under is retired from the code, the evaluation MUST preserve that row's figures, its full provenance tuple **and the configuration it was measured under** as versioned artefacts in the repository, and MUST mark the row as **historical and not re-executable** wherever it is cited. The report MUST state which rows can be re-run and which cannot.

The retired configuration MUST NOT remain loadable as a configuration: it is preserved as a record of what was measured, not as something that can be selected, and an attempt to load it MUST fail naming what no longer exists.

A retired baseline configuration MUST NOT be reimplemented inside the evaluation harness in order to keep it runnable: a harness that restates the pipeline measures the restatement, not the pipeline.

#### Scenario: Each change has its own row

- **GIVEN** an evaluation that reports both a fusion change and a ranking change
- **WHEN** the ablation table is published
- **THEN** it contains a row with the fusion change alone
- **AND** a row with both changes applied
- **AND** the improvement of each is attributable

#### Scenario: A retired baseline row stays citable

- **GIVEN** the configuration a published baseline was measured under has been retired from the code
- **WHEN** that baseline is cited
- **THEN** its figures, its full provenance tuple and the configuration it was measured under are present as versioned artefacts
- **AND** the row is marked historical and not re-executable

#### Scenario: The preserved configuration is a record and not a choice

- **GIVEN** the preserved configuration of a retired baseline
- **WHEN** it is loaded as a configuration
- **THEN** the load fails naming the knobs that no longer exist
- **AND** it is not listed among the configurations the table can run

#### Scenario: The report says which rows can be re-run

- **WHEN** an ablation table containing a retired row is published
- **THEN** it states for each row whether it can be re-executed
- **AND** a reader can tell which figures are reproducible and which are archived

#### Scenario: A retired configuration is not reimplemented in the harness

- **WHEN** the evaluation harness is inspected after a baseline configuration is retired
- **THEN** the harness contains no restatement of that pipeline
- **AND** the row's figures come from the archived artefact rather than from a copy of the code

### Requirement: A run is comparable to another only when its provenance matches

Every evaluation run MUST record the golden set version, the configuration, a stable fingerprint of the indexed document set, the embedding model version, the code revision that produced it **and how its ranked lists were composed**. Two runs whose provenance differs MUST be reported as not comparable rather than compared.

**The composition MUST be recorded even when it can no longer be chosen.** Recording it and selecting it are different things: once a single composition remains, no configuration may select one, but a run archived under a retired composition MUST still be distinguishable from a current one, and a run MUST still declare what it actually composed rather than what its environment was thought to request. The recorded value MUST therefore come from the code and never from a setting, and a configuration that composes no ranked lists at all MUST record that absence rather than inherit the live value.

Query embeddings MUST be frozen as a versioned artefact keyed by the embedding model version, so that repeating a run does not depend on the provider answering identically.

#### Scenario: Repeating a run yields identical metrics

- **WHEN** the same configuration runs twice with the same provenance
- **THEN** the metrics are identical

#### Scenario: A moved index makes previous runs incomparable

- **WHEN** the indexed document set changes and a run is compared with an earlier one
- **THEN** the report states that the two are not comparable and names the differing element

#### Scenario: The composition is recorded although no configuration selects it

- **WHEN** an evaluation run is recorded
- **THEN** its provenance names how its ranked lists were composed
- **AND** that value comes from the code rather than from any setting
- **AND** a run whose configuration composes no ranked lists records that absence instead of the live value

#### Scenario: A run archived under a retired composition is not comparable with a current one

- **GIVEN** an archived run recorded under a composition that has since been retired
- **WHEN** it is compared with a run taken after the retirement
- **THEN** the two are reported as not comparable
- **AND** the composition is named as the differing element
