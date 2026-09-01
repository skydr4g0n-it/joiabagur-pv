## ADDED Requirements

### Requirement: Auditing recomputes unsupported memberships over the families that exist

The system SHALL report, over **persisted** families rather than proposed ones, every member for which a product of a **different** family sits closer than that member's own worst sibling, by more than a configured margin. The comparison MUST be relative to the member's own family and MUST NOT use a single global similarity threshold.

Recomputation over persisted families is the only way the signal can exist at all. Suggestion converges by excluding products that already belong somewhere, so once a batch is approved its flagged members are absent from every subsequent suggestion, and the flags themselves were never persisted. A member flagged at approval time is therefore unreachable by any later suggestion run.

A flagged member MUST remain in its family. Auditing reports; it does not change membership.

#### Scenario: A member another family sits closer to is reported

- **WHEN** a product belongs to a family and a product of a different family is closer to it than its own worst sibling by more than the margin
- **THEN** the member is reported as flagged, with the margin and the identity of the closer product
- **AND** the member still belongs to its family after the audit

#### Scenario: The flag is produced for products suggestion can no longer see

- **WHEN** a member was flagged when its family was approved and now belongs to that family
- **THEN** the audit still reports it
- **AND** the fact that a suggestion run would exclude it does not prevent the report

#### Scenario: No global similarity threshold decides a flag

- **WHEN** two products of different families have a cosine higher than the lowest cosine observed inside some other family
- **THEN** neither is flagged on that basis alone
- **AND** a flag follows only from a stranger beating that member's own worst sibling by more than the margin

### Requirement: Unassigned products are nominated by margin relative to the target family

The system SHALL nominate a product belonging to no family as a candidate for family F when its similarity to F's members exceeds F's own worst-sibling similarity by more than a configured margin. Nomination MUST NOT be decided by how many of a product's nearest neighbours belong to one family; that measure MAY be reported as a ranking signal but MUST NOT select candidates.

Measured over the indexed corpus, neighbourhood purity nominates 55 synthetic products against 19 real ones, because the synthetic corpus was built with deliberate near-duplicate families that purity cannot tell apart from missing members. The relative margin nominates 21 real products against 1 synthetic. Purity selects for the one thing the corpus guarantees is not a missing membership.

A candidate MUST share the piece type of the family it is nominated for. A product without a piece type MUST NOT be nominated for any family. Each candidate MUST report the data origin of the product, so the two populations can be counted separately.

The margin MUST be read from configuration and MUST NOT be hard-coded.

#### Scenario: A product closer to a family than its worst member is nominated

- **WHEN** a product belongs to no family, shares a piece type with family F, and its similarity to F's members exceeds F's worst-sibling similarity by more than the margin
- **THEN** it is reported as a candidate for F, with that similarity, F's worst-sibling similarity and the margin between them

#### Scenario: Neighbourhood purity does not nominate

- **WHEN** a product's nearest neighbours belong predominantly to one family but it does not beat that family's worst sibling by the margin
- **THEN** it is not reported as a candidate
- **AND** the purity measure may still accompany candidates that were nominated, as a ranking signal

#### Scenario: Nomination never crosses piece types

- **WHEN** a product without a family is closest to the members of a family of a different piece type
- **THEN** it is not nominated for that family

#### Scenario: A product without a piece type is nominated for nothing

- **WHEN** a product belongs to no family and has no piece type
- **THEN** it appears in no candidate list

#### Scenario: The data origin of every candidate is reported

- **WHEN** candidates are reported
- **THEN** each one carries the data origin of its product
- **AND** the counts of real and synthetic candidates are distinguishable without inspecting the catalogue

#### Scenario: The nomination margin comes from configuration

- **WHEN** the orphan margin is changed in configuration
- **THEN** the set of candidates changes accordingly without any code modification

### Requirement: Auditing writes nothing

The system SHALL treat the audit as a read. Requesting it MUST NOT create, modify or delete any family, any membership, any verdict, or any product watermark. Recording a human judgement MUST be a separate operation on a separate route.

Separating them is what makes the read verifiable: an audit that could also write leaves no way to assert that it did not.

#### Scenario: An audit leaves the catalogue untouched

- **WHEN** an administrator requests the audit
- **THEN** the response carries the flagged members, the candidates, the refused groups and the excluded products
- **AND** no family, membership or verdict is created, modified or removed
- **AND** no product's `UpdatedAt` changes

### Requirement: A human verdict on a product and a family is persisted and honoured

The system SHALL persist each human judgement about a `(product, family)` pair, recording the verdict, the administrator who made it, the instant, and the margin observed at that moment. A pair MUST carry at most one verdict: judging the same pair again corrects the existing record rather than adding a second one.

A pair that carries a verdict MUST NOT be reported again by the audit. The same product MAY still be reported as a candidate for a different family.

The verdict MUST be stored so that removing a family removes the verdicts recorded against it, leaving no judgement about a family that no longer exists.

The system MUST NOT re-open a verdict automatically when the product is re-enriched or re-embedded. The margin recorded at review time MUST be retained and reported alongside the current one, so a reviewer can see that the evidence moved rather than being told nothing.

#### Scenario: A dismissed candidate does not come back

- **WHEN** an administrator dismisses a product as a candidate for a family and the audit is requested again
- **THEN** that pair is absent from the candidates
- **AND** the same product may still be reported as a candidate for another family

#### Scenario: Judging the same pair twice corrects rather than duplicates

- **WHEN** a pair that already carries a verdict is judged again
- **THEN** the stored verdict reflects the later judgement
- **AND** exactly one verdict exists for that pair

#### Scenario: Confirming a family records the judgement without moving the catalogue

- **WHEN** an administrator confirms a family without changing its name, its members or their labels
- **THEN** a verdict is recorded for each of its `(product, family)` pairs with the reviewer and the instant
- **AND** no product's `UpdatedAt` changes
- **AND** an incremental catalog pull from a cursor earlier than the confirmation emits none of those products

#### Scenario: Dissolving a family takes its verdicts with it

- **WHEN** a family that carries verdicts is deleted
- **THEN** those verdicts no longer exist
- **AND** no verdict refers to a family that is absent

#### Scenario: A stale verdict is shown as stale, not silently reopened

- **WHEN** a pair carrying a verdict is examined after the product's similarity has changed
- **THEN** the margin recorded at review time is reported together with the current margin
- **AND** the pair is not reported again as a flag or a candidate

### Requirement: Family review is restricted to administrators

The system SHALL restrict requesting the audit, recording verdicts, listing families and dissolving a family to authenticated administrators. None of those operations may be invoked by an operator or by an unauthenticated caller.

#### Scenario: An operator cannot audit or judge

- **WHEN** a user with the operator role requests the audit or records a verdict
- **THEN** the request is rejected with 403 Forbidden
- **AND** no verdict, family or membership is created or modified

#### Scenario: An unauthenticated caller is rejected

- **WHEN** an unauthenticated caller invokes any family review operation
- **THEN** the request is rejected with 401 Unauthorized

### Requirement: A list that could not be computed is never presented as a list that came back empty

The system SHALL report, for each list the review surface presents, whether it was computed and returned no findings or could not be computed at all. The two states MUST be distinguishable to the reviewer, and an audit that failed MUST NOT be rendered as an audit that found nothing.

The distinction cannot live only in the client that calls the service. An empty list drawn without qualification **is** the wrong answer regardless of what the layer beneath it knew, and on a screen whose subject is catalogue quality "nothing to review" is read as "nothing is wrong" — the conclusion this capability exists to support with evidence rather than to assert by accident.

Availability MUST be tracked per list rather than per screen: reviewing the families that exist requires no vectors, so it MUST remain usable while the lists that do require them are unavailable.

#### Scenario: An unavailable audit is shown as unavailable

- **WHEN** the audit cannot be computed because the AI service did not answer
- **THEN** the lists that depend on it report that they are unavailable
- **AND** they are distinguishable from a list that was computed and returned no findings

#### Scenario: A computed empty list is shown as empty

- **WHEN** the audit is computed and finds no flagged member and no candidate
- **THEN** those lists report that they were computed and found nothing
- **AND** they are not reported as unavailable

#### Scenario: Family review survives an unavailable audit

- **WHEN** the audit cannot be computed
- **THEN** the families that exist are still listed and can still be reviewed and judged
- **AND** the unavailability is confined to the lists that need the vectors

### Requirement: A recorded judgement is not a membership, and the difference is visible

The system SHALL report, for every recorded judgement, whether the catalogue would still have to
change to honour it: a member the reviewer rejected must be removed, a candidate they confirmed
must be added, and the other two combinations are decisions the catalogue already reflects.

Without this the gap is invisible. The audit omits pairs that carry a verdict — which is what makes
a dismissal stick — so a decision nobody acted on disappears from every list and reads as work
already finished. A reviewer can complete a queue and leave the catalogue untouched.

The system SHALL allow a reviewer to enact such a judgement, and the resulting membership change
MUST go through the same path that stamps the catalog watermark of entering and leaving products.

#### Scenario: A judgement the catalogue has not acted on is listed as pending

- **WHEN** a reviewer rejects a member and does not remove it
- **THEN** that judgement is reported as pending a removal
- **AND** a candidate that was confirmed but never added is reported as pending an addition
- **AND** a confirmed member and a dismissed candidate are reported as pending nothing

#### Scenario: Enacting a judgement moves the membership and the watermark

- **WHEN** a reviewer enacts a pending addition
- **THEN** the product becomes a member of that family
- **AND** the judgement stops being reported as pending
- **AND** an incremental catalog pull emits that product

### Requirement: A member's variant label can be corrected after the fact

The system SHALL allow an administrator to change the variant label of a product already in a
family, without disturbing the other members.

A label written wrongly is not a rare case but the expected one: it is typed while judging, the
canonical form of a material is easy to miss, and leaving it blank silently declares the product to
be the family's base piece. A review surface that can create a membership but not correct its label
forces the fix through the API by hand.

#### Scenario: A label is corrected without touching the rest of the family

- **WHEN** an administrator changes one member's variant label
- **THEN** that member carries the new label
- **AND** every other member keeps its own label and position

#### Scenario: A label that collides with a sibling is refused

- **WHEN** the new label equals another member's label in the same family
- **THEN** the change is refused
- **AND** neither member's label is modified

### Requirement: Review time is recorded per judgement, not held in a screen

The system SHALL persist the time a reviewer spent on each judgement, and MUST compute the average
review time from those records rather than from any figure held by a client.

A number that lives only in a screen is lost when it closes, and the delivery checklist asks for an
average review time as evidence that the review happened. It is also the only signal that a queue
has degraded into clicking through, which is the failure the review exists to avoid.

When no judgement carries a timing, the system MUST report the absence rather than zero: zero
claims an instantaneous review, and the truth is that nothing was measured.

The system SHALL record which population each judgement came from — a member the vectors questioned
or an unassigned candidate — at the moment it is made. It MUST NOT infer that afterwards from the
current membership, because a rejected member that was removed is indistinguishable from a rejected
candidate, and the two populations have very different rates.

#### Scenario: The seconds spent survive the session

- **WHEN** a reviewer judges an item and the judgement is recorded
- **THEN** the time spent on it is stored with the judgement
- **AND** the average review time is computed from the stored judgements

#### Scenario: Nothing timed reports an absence, not a zero

- **WHEN** no recorded judgement carries a timing
- **THEN** the reported average review time is absent
- **AND** it is not reported as zero

#### Scenario: The two populations are reported apart

- **WHEN** metrics are requested after both members and candidates have been judged
- **THEN** the confirmation rate of questioned memberships is reported separately from the
  acceptance rate of nominated candidates

#### Scenario: Acting on a judgement does not move it between populations

- **WHEN** a member the reviewer rejected is removed from its family
- **THEN** that judgement is still counted among the members
- **AND** it is not counted as a candidate

### Requirement: The audit is deterministic and calls no model

The system SHALL produce the same audit for the same catalogue state, the same verdicts and the same configuration. The audit MUST NOT call a language model, MUST NOT call the embedding provider — the vectors are already persisted on the index — and MUST NOT read or write the transactional catalogue schema by SQL from the AI service.

#### Scenario: Two audits over an unchanged catalogue agree

- **WHEN** the audit is requested twice with no catalogue change, no new verdict and no configuration change in between
- **THEN** both responses contain the same flagged members and the same candidates, in the same order

#### Scenario: No provider call is made

- **WHEN** the audit is requested
- **THEN** no request reaches the embedding provider or any language model
- **AND** similarity is computed from the vectors already stored on the index
