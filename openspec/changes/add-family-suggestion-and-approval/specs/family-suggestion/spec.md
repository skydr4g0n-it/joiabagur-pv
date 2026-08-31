## ADDED Requirements

### Requirement: Suggestion groups by normalized name root within one piece type

The system SHALL propose product families by grouping products whose **normalized name root** coincides, where normalization case-folds, strips diacritics, reduces punctuation and parentheses to whitespace, collapses runs of whitespace, and removes a trailing size token. The size vocabulary MUST cover the Latin scale (`XS`, `S`, `M`, `L`, `XL`, matched case-insensitively because the real catalogue contains `Xs`) and the Spanish word scale (`mini`, `pequeño/a`, `mediano/a`, `grande`).

Grouping MUST NOT cross piece types. A product whose `piece_type` is null MUST NOT group with any other product: the null is a value of the gate, not a wildcard.

#### Scenario: Products differing only in a size suffix are proposed as one family

- **WHEN** the catalogue contains `Colgante hoja roble pequeña`, `Colgante hoja roble mediana` and `Colgante hoja roble grande`, all of the same piece type
- **THEN** the three are proposed as members of a single family
- **AND** the family's root is the name without the size token

#### Scenario: Inconsistent capitalisation does not split a family

- **WHEN** the catalogue contains `Anillo erizo de mar S`, `Anillo erizo de mar M`, `Anillo erizo de mar L` and `Anillo Erizo de mar XL`
- **THEN** the four are proposed as members of one family
- **AND** the differing capitalisation of one member does not produce a second family

#### Scenario: Grouping never crosses piece types

- **WHEN** the catalogue contains `Anillo erizo de mar M` and `Colgante erizo de mar M`
- **THEN** the two products are not proposed as members of the same family

#### Scenario: A product without a piece type groups with nobody

- **WHEN** a product whose `piece_type` is null shares a normalized root with other products
- **THEN** it is not proposed as a member of any family
- **AND** the remaining products may still form a family among themselves

### Requirement: Material distinguishes variants by fusing groups, never by stripping roots

The system SHALL treat a material token as a variant axis by **merging two already-formed groups whose roots differ in exactly one material token**, and MUST NOT remove material tokens from the root before grouping. Removing them globally collapses legitimate roots: `Anillo plata S/M/L/XL` would reduce to the bare piece type and absorb unrelated products.

A merge MUST be rejected when the resulting root equals the bare piece type or falls below two tokens. A rejected merge MUST be reported as a review item rather than silently dropped, because the same guard surfaces catalogue entries that are not products at all.

#### Scenario: Two groups differing in one material token are merged

- **WHEN** the catalogue contains `Colgante conchiglie`, `Colgante conchiglie Oro`, `Colgante mini conchiglie` and `Colgante mini conchiglie Oro`
- **THEN** the four are proposed as members of one family
- **AND** each member carries the variant label that distinguishes it

#### Scenario: A material-only pair forms a family

- **WHEN** the catalogue contains `Anillo lapislázuli mediano` and `Anillo lapislázuli mediano oro` and no other member of that root
- **THEN** the two are proposed as one family whose variant axis is the material

#### Scenario: A name whose material belongs to the root is not degraded

- **WHEN** the catalogue contains `Anillo plata S`, `Anillo plata M`, `Anillo plata L` and `Anillo plata XL`
- **THEN** the four are proposed as one family whose root retains the material token
- **AND** the root is not reduced to the bare piece type

#### Scenario: A merge that would degenerate the root is rejected and reported

- **WHEN** merging two groups would leave a root equal to the bare piece type or shorter than two tokens, as with `Encargos plata` and `Encargos Oro`
- **THEN** no family is proposed for them
- **AND** they appear in the review list with the reason for the rejection

### Requirement: The embedding veto is relative to its own group and marks rather than removes

The system SHALL use embedding similarity as a **veto relative to the candidate group**, comparing each member against its own group's centroid and flagging the member whose cosine falls below `median − k·MAD` **of that group**. The system MUST NOT apply a single global similarity threshold, because the population of worst siblings and the population of nearest strangers overlap: measured over the indexed corpus, worst siblings span 0.847–0.948 and nearest strangers reach 0.936–0.945.

A flagged member MUST remain in the proposal, marked for review together with its distance. The system MUST NOT remove it silently. The veto's parameters — the multiplier and the neighbour count — MUST be read from configuration and MUST NOT be hard-coded.

#### Scenario: A member the vector does not support is flagged, not dropped

- **WHEN** a candidate shares root and piece type with its group but its cosine to the group centroid falls below the group's relative threshold
- **THEN** the member appears in the proposal flagged for review, with its distance reported
- **AND** the member is not removed from the proposal
- **AND** the proposal remains applicable as returned

#### Scenario: No global similarity threshold decides membership

- **WHEN** two products in different groups have a cosine higher than the lowest cosine observed inside some other group
- **THEN** they are still not proposed as members of the same family
- **AND** membership follows the root and piece-type gate, not the absolute similarity

#### Scenario: Veto parameters come from configuration

- **WHEN** the veto multiplier or the neighbour count is changed in configuration
- **THEN** the suggestion result changes accordingly without any code modification

### Requirement: Variant labels are stored verbatim and member order follows a canonical size rank

The system SHALL derive each member's variant label from the **fragment removed during normalization**, normalized but otherwise verbatim. A label MUST NOT be translated onto another scale: `mini` is the word the workshop uses and MUST NOT be recorded as `XS`. A member of a family that carries no distinguishing token — the base piece — MUST be proposed with no variant label, which is a legitimate state and not a defect.

Member order MUST be derived from an **internal canonical size rank** rather than from alphabetical order, so that `XL` does not precede `S`. That rank MUST NOT be persisted as a label.

Where a family varies along two axes at once, the label MUST be the composite of the removed fragments, which still satisfies the uniqueness of variant label within a family.

#### Scenario: A word-scale label is preserved as written

- **WHEN** a family groups `Colgante hoja roble pequeña`, `mediana` and `grande`
- **THEN** the persisted variant labels are `pequeña`, `mediana` and `grande`
- **AND** none of them is recorded as `S`, `M` or `L`

#### Scenario: Members are ordered by size rank, not alphabetically

- **WHEN** a family groups members labelled `S`, `M`, `L` and `XL`
- **THEN** the proposed order follows the canonical size rank
- **AND** `XL` is not placed before `S`

#### Scenario: The base piece carries no variant label

- **WHEN** a family groups `Anillo mini conchiglie` and `Anillo conchiglie`
- **THEN** the first is labelled `mini`
- **AND** the second is proposed with no variant label

#### Scenario: A two-axis family gets a composite label that stays unique

- **WHEN** a family varies along both size and material, as with `mini`, `mini oro` and a base member
- **THEN** each member's label is the composite of its removed fragments
- **AND** no two members of that family share a label

### Requirement: Suggesting never writes, and applying is the only write path

The system SHALL expose the proposal and the approval as **two separate operations**. Requesting suggestions MUST NOT create, modify or delete any family, any membership, or any product watermark. Applying MUST accept the subset of proposals the caller returns and MUST persist only those.

Proposals MUST NOT be persisted between the two calls: the caller returns what it accepts, so no suggestion store exists and no state can go stale.

#### Scenario: Requesting suggestions leaves the catalogue untouched

- **WHEN** an administrator requests family suggestions
- **THEN** the response contains the proposals with their members, variant labels and review flags
- **AND** no family or membership is created, modified or removed
- **AND** no product's `UpdatedAt` changes

#### Scenario: Only the returned subset is persisted

- **WHEN** an administrator applies a strict subset of the proposals received
- **THEN** exactly the families in that subset are created
- **AND** the proposals left out leave no trace in the system

#### Scenario: Repeating the suggestion converges

- **WHEN** suggestions are requested again after a batch has been applied
- **THEN** the products that now belong to a family are absent from the new proposals
- **AND** the remaining proposals are the same ones the previous call produced for those products

### Requirement: Applying records that the family came from an assisted suggestion

The system SHALL persist an applied family through the existing family service, never by direct SQL, so that the catalogue watermark of entering products is stamped and the single-family invariant is enforced by the database. Each applied family MUST record its origin as approved from an assisted suggestion, together with the administrator who applied it and the instant of approval. A family created through the manual family endpoints MUST continue to record manual origin.

When a proposal names a product that already belongs to another family, the operation MUST report which products conflict and which family holds each of them, and MUST NOT leave any family partially created.

#### Scenario: An applied family records assisted approval

- **WHEN** an administrator applies a proposal
- **THEN** the family is created with its members in the proposed order and with their variant labels
- **AND** the family records assisted-approval origin, the approving administrator and the approval instant

#### Scenario: A manually created family still records manual origin

- **WHEN** an administrator creates a family through the manual family endpoints
- **THEN** that family records manual origin
- **AND** its approving user and approval instant remain empty

#### Scenario: A conflicting product does not bring down the batch

- **WHEN** a proposal names a product that meanwhile was assigned to another family
- **THEN** the response identifies which products conflict and which family holds each of them
- **AND** the remaining families of the batch are created
- **AND** no family is left partially created

#### Scenario: Entering products are visible to an incremental catalog pull

- **WHEN** a batch is applied and the catalog feed is pulled incrementally from a cursor earlier than the approval
- **THEN** the feed emits exactly the products that entered a family
- **AND** no additional product is emitted

### Requirement: Family suggestion is restricted to administrators

The system SHALL restrict both requesting suggestions and applying them to authenticated administrators. Neither operation may be invoked by an operator or by an unauthenticated caller.

#### Scenario: An operator cannot request or apply suggestions

- **WHEN** a user with the operator role invokes either family-suggestion operation
- **THEN** the request is rejected with 403 Forbidden
- **AND** no family or membership is created or modified

#### Scenario: An unauthenticated caller is rejected

- **WHEN** an unauthenticated caller invokes either family-suggestion operation
- **THEN** the request is rejected with 401 Unauthorized

### Requirement: Suggestion is deterministic and calls no language model

The system SHALL produce the same proposals for the same catalogue state and the same configuration. Suggestion MUST NOT call a language model, MUST NOT call the embedding provider — the vectors are already persisted on the index — and MUST NOT read or write the transactional catalogue schema by SQL from the AI service.

#### Scenario: Two runs over an unchanged catalogue agree

- **WHEN** suggestions are requested twice with no catalogue change and no configuration change in between
- **THEN** both responses contain the same families, with the same members, labels and order

#### Scenario: No provider call is made

- **WHEN** suggestions are requested
- **THEN** no request reaches the embedding provider or any language model
- **AND** similarity is computed from the vectors already stored on the index
