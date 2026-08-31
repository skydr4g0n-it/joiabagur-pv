## ADDED Requirements

### Requirement: Suggestion groups by normalized name root within one piece type

The system SHALL propose product families by grouping products whose **normalized name root** coincides, where normalization case-folds, strips diacritics, reduces punctuation and parentheses to whitespace, collapses runs of whitespace, and removes one size token.

The size token MUST be removed from **any position in the name, not only the last**. Restricting removal to the suffix satisfies the synthetic corpus, built entirely of `<name> <SIZE>`, and fails the real one: `Anillo lapislázuli mediano oro` carries its size behind a material, and `Anillo mini conchiglie` would never reach `Anillo conchiglie`. Removing from any position is safe because of an asymmetry — when a size word is genuinely part of a model's name, every member carries it and every root is shortened alike, so the grouping is unchanged; it only alters the outcome where some members carry it and others do not, which is exactly the case where the size *is* the variant axis.

The size vocabulary MUST cover the Latin scale (`XS`, `S`, `M`, `L`, `XL`, matched case-insensitively because the real catalogue contains `Xs`) and the Spanish word scale (`mini`, `pequeño/a`, `mediano/a`, `grande`). A vocabulary entry spanning more than one word MUST be matched whole and in preference to any single word inside it, so that `extra mini` is one size rather than a stray `extra` left in the root beside a size of `mini`.

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

#### Scenario: A size hidden inside the name is still removed

- **WHEN** the catalogue contains `Anillo mini conchiglie` and `Anillo conchiglie`
- **THEN** the two are proposed as members of one family
- **AND** the size is removed from the middle of the name, not only from its end

#### Scenario: A multi-word size is removed whole

- **WHEN** the catalogue contains `Anillo conchiglie extra mini` and `Anillo conchiglie mini`
- **THEN** the two are proposed as members of one family
- **AND** the first is labelled `extra mini`
- **AND** no fragment of that size is left behind in the root

### Requirement: The piece-type gate names what it excludes

The system SHALL report, alongside the proposals, every product the piece-type gate removed from consideration, naming the product and the reason. A product without a piece type disappears from the review queue as well as from families, and no other output would ever mention it: an exclusion nobody can see is indistinguishable from a product that simply had no siblings.

Products skipped because they already belong to a family MUST be reported as a count rather than named individually. That exclusion is the convergence rule working as designed, and after the first approved batch it covers hundreds of products, which would bury the exclusions worth reading.

#### Scenario: A product without a piece type is named, not silently dropped

- **WHEN** the catalogue contains a product whose piece type is null
- **THEN** it appears in the reported exclusions with its identifier, SKU, name and the reason
- **AND** it is absent from every proposal

#### Scenario: Products already in a family are counted, not listed

- **WHEN** suggestions are requested after a batch has been approved
- **THEN** the products belonging to a family are reported as a count
- **AND** they do not appear individually among the reported exclusions

### Requirement: Material distinguishes variants by fusing groups, never by stripping roots

The system SHALL treat a material as a variant axis by **merging two already-formed groups whose roots differ in exactly one material**, and MUST NOT remove material tokens from the root before grouping. Removing them globally collapses legitimate roots: `Anillo plata S/M/L/XL` would reduce to the bare piece type and absorb unrelated products. A material named by more than one word counts as **one** material, matched whole and in preference to any single word inside it, so that `baño de oro` is not read as plain `oro` with a residue of `baño de` left in the root to keep the two groups apart.

A merge MUST be rejected when the resulting root equals the bare piece type or falls below two tokens. A rejected merge MUST be reported as a review item rather than silently dropped, because the same guard surfaces catalogue entries that are not products at all.

A group whose members cannot all be given **distinct** variant labels MUST also be rejected and reported, never proposed. Two members sharing a label are indistinguishable on every axis the grouping knows, and a proposal carrying them would be refused downstream by the family's uniqueness index — turning a question a person can answer into a database constraint error.

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

#### Scenario: A group whose members cannot be told apart is rejected

- **WHEN** two members of a candidate group would receive the same variant label
- **THEN** no family is proposed for that group
- **AND** it appears in the review list with the reason for the rejection

### Requirement: The embedding veto is relative to the other proposals and marks rather than removes

The system SHALL use embedding similarity as a **veto relative to the other proposed memberships**, flagging a member when a product of a **different proposed family** is closer to it than its own worst sibling, by more than a configured margin. The system MUST NOT apply a single global similarity threshold, because the population of worst siblings and the population of nearest strangers overlap: measured over the indexed corpus, worst siblings span 0.847–0.948 and nearest strangers reach 0.936–0.945.

The comparison universe MUST be the members of proposed families and nothing else. A product competing for no membership is not an alternative membership and MUST NOT be able to veto one; widening the universe to the whole catalogue flags members against products that were never candidates for anything.

The system MUST NOT decide membership from a member's distance to its own group's centre. That is a test *within* a group, and every group has a least-typical member by construction, so it flags on ordinary spread rather than on evidence.

A flagged member MUST remain in the proposal, marked for review together with the margin by which the stranger won. The system MUST NOT remove it silently. The margin MUST be read from configuration and MUST NOT be hard-coded.

#### Scenario: A member another family sits closer to is flagged, not dropped

- **WHEN** a candidate shares root and piece type with its group, and a member of another proposed family is closer to it than its own worst sibling by more than the margin
- **THEN** the member appears in the proposal flagged for review, with the margin reported
- **AND** the member is not removed from the proposal
- **AND** the proposal remains applicable as returned

#### Scenario: No global similarity threshold decides membership

- **WHEN** two products in different groups have a cosine higher than the lowest cosine observed inside some other group
- **THEN** they are still not proposed as members of the same family
- **AND** membership follows the root and piece-type gate, not the absolute similarity

#### Scenario: The veto margin comes from configuration

- **WHEN** the veto margin is changed in configuration
- **THEN** the suggestion result changes accordingly without any code modification

### Requirement: Variant labels are stored verbatim and member order follows a canonical size rank

The system SHALL derive each member's **size** label from the fragment removed during normalization, normalized but otherwise verbatim, down to its accent and its capitalisation. A size label MUST NOT be translated onto another scale: `mini` is the word the workshop uses and MUST NOT be recorded as `XS`. A member of a family that carries no distinguishing token — the base piece — MUST be proposed with no variant label, which is a legitimate state and not a defect.

The **material** half of a label MUST instead be recorded as the material's canonical term. The two halves differ because the risk differs: `mini` and `XS` are two sizes, so keeping both as written records what the shop said, whereas `Oro` and `18k` are one material spelled twice, and keeping both as written would give two members different labels for the same thing — a pair that walks past the uniqueness guard, which compares labels rather than meanings, and reaches the shop as a family whose two variants are indistinguishable in the case.

Member order MUST be derived from an **internal canonical size rank** rather than from alphabetical order, so that `XL` does not precede `S`. That rank MUST NOT be persisted as a label.

Where a family varies along two axes at once, the label MUST be the composite of both, which still satisfies the uniqueness of variant label within a family.

#### Scenario: A word-scale label is preserved as written

- **WHEN** a family groups `Colgante hoja roble pequeña`, `mediana` and `grande`
- **THEN** the persisted variant labels are `pequeña`, `mediana` and `grande`
- **AND** none of them is recorded as `S`, `M` or `L`

#### Scenario: One material spelled two ways does not become two variants

- **WHEN** a candidate group differs only in two spellings of a single material, as with `Oro` and `18k`
- **THEN** both members resolve to the same material term and therefore to the same label
- **AND** the group is reported as a review item rather than proposed as a family

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
