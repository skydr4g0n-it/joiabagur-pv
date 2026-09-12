## MODIFIED Requirements

### Requirement: An ablation table isolates each change it reports

When one evaluation reports more than one change to the retrieval pipeline, the table MUST contain a row for each change applied **on its own**, in addition to the row that applies them together. A table that reports only the combined result MUST NOT be published, because an improvement it shows cannot be attributed to a cause.

**The baseline row MUST remain citable, and citable is not the same as re-executable.** When the configuration a published baseline was measured under is retired from the code, the evaluation MUST preserve that row's figures and its full provenance tuple as versioned artefacts in the repository, and MUST mark the row as **historical and not re-executable** wherever it is cited. The report MUST state which rows can be re-run and which cannot.

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
- **THEN** its figures and its full provenance tuple are present as versioned artefacts
- **AND** the row is marked historical and not re-executable

#### Scenario: The report says which rows can be re-run

- **WHEN** an ablation table containing a retired row is published
- **THEN** it states for each row whether it can be re-executed
- **AND** a reader can tell which figures are reproducible and which are archived

#### Scenario: A retired configuration is not reimplemented in the harness

- **WHEN** the evaluation harness is inspected after a baseline configuration is retired
- **THEN** the harness contains no restatement of that pipeline
- **AND** the row's figures come from the archived artefact rather than from a copy of the code
