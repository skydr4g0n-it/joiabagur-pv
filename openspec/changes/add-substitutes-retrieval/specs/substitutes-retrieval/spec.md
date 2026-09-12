## ADDED Requirements

### Requirement: Substitutes are retrieved from the stored embedding without calling the provider
When `STUB_MODE` is disabled, `POST /v1/retrieval/substitutes` MUST run the substitutes pipeline over `ai.product_document` and MUST return a body that validates against the frozen `SubstitutesResponse` model. The candidate ordering MUST be derived from the embedding already stored on the source product's row; the handler MUST NOT call the embedding provider or any LLM, and MUST NOT run the lexical branch, the query expansion or any rank fusion. When `STUB_MODE` is enabled, the existing C02 stub MUST remain the handler so committed contract tests stay green. The OpenAPI snapshot MUST NOT be regenerated. Python MUST NOT read schema `public`.

#### Scenario: Real mode returns substitutes instead of 501
- **GIVEN** `STUB_MODE` is disabled and retrieval dependencies are available
- **WHEN** an authenticated client with `pos_id` calls `POST /v1/retrieval/substitutes` for an indexed product
- **THEN** the response status is 200 or 503 according to index and dependency state
- **AND** the status is not 501 claiming the implementation arrives in a later change
- **AND** a 200 body validates against `SubstitutesResponse`

#### Scenario: No embedding provider is called
- **GIVEN** the embedding client is a double that raises when invoked
- **WHEN** a substitutes request is served in real mode
- **THEN** the request succeeds
- **AND** the double is never invoked

#### Scenario: Stub mode keeps the C02 fixtures
- **GIVEN** `STUB_MODE` is enabled
- **WHEN** an authenticated client calls `POST /v1/retrieval/substitutes` with a valid body
- **THEN** the response is produced by the existing C02 substitutes stub
- **AND** no database session is opened

#### Scenario: The frozen contract does not move
- **WHEN** `test_openapi_snapshot_is_stable` runs against this change
- **THEN** the live schema equals the committed `ai-service/openapi.json`
- **AND** the snapshot file has not been regenerated

### Requirement: The piece type is the only hard filter on the candidate universe
The candidate universe MUST be restricted to active indexed documents whose `piece_type` equals the source product's `piece_type`. The source product MUST NOT be returned as its own substitute, and identifiers listed in the request's `exclude_product_ids` MUST NOT be returned. No other attribute MAY remove a candidate from the universe; in particular, availability MUST NOT remove any candidate.

#### Scenario: A different piece type is never returned
- **GIVEN** the source product is a pendant and the nearest neighbours by cosine distance include a ring
- **WHEN** substitutes are requested
- **THEN** no returned candidate has a `piece_type` different from the source product's
- **AND** this holds even when the excluded candidate outranks every returned one on raw similarity

#### Scenario: The source product is not its own substitute
- **WHEN** substitutes are requested for a product
- **THEN** that product does not appear among the candidates

#### Scenario: Explicitly excluded products are not returned
- **GIVEN** a request whose `exclude_product_ids` names an indexed product of the same piece type
- **WHEN** substitutes are requested
- **THEN** that product does not appear among the candidates

### Requirement: Ordering composes continuous terms and no integer block enters the key
Candidates MUST be ordered by a score composed of the cosine similarity to the source product plus continuous penalty terms for size mismatch and for unavailability. No term of the ordering key MAY be an integer block, because an integer block partitions the result instead of breaking ties. The availability term MUST reuse the business score calibrated by `business-signals-ranking` and MUST only ever subtract. The size penalty weight MUST be read from configuration and MUST NOT be written into the code.

Reusing that business score has a measured consequence this requirement ACCEPTS rather than forbids. Its calibrated weight is `1.0` and the cosine similarity lives in `[0, 1]`, so the availability term spans the whole similarity range and in practice orders every out-of-stock candidate behind every available one. That is a partition in effect, and it is permitted here for four reasons: the term is continuous in FORM, so lowering the weight reorders the list without a line of code changing; it only ever subtracts; it removes nothing, which is the invariant that matters; and the golden set is labelled with no point-of-sale scope, so no slice of it can calibrate that weight — re-fixing it would be a figure chosen rather than measured. What the prohibition above forbids is an integer block in the key, and the SIZE term is where one would have gone.

#### Scenario: A same-size candidate outranks a same-family candidate of a different size
- **GIVEN** the source product declares a size and its family has members of other sizes
- **AND** a candidate outside the family shares the source product's piece type and size
- **WHEN** substitutes are requested
- **THEN** the same-size candidate is ordered above at least one same-family candidate of a different size

#### Scenario: The demoted sibling stays inside the visible window
- **GIVEN** the conditions of the previous scenario
- **WHEN** substitutes are requested
- **THEN** the same-family candidate of a different size is still present within the returned window
- **AND** it is not pushed behind every candidate that matches the size

#### Scenario: Material overlap breaks a tie in favour of the shared material
- **GIVEN** two candidates with equivalent cosine similarity and the same size status
- **AND** one shares at least one material with the source product and the other shares none
- **WHEN** substitutes are requested
- **THEN** the candidate sharing a material is ordered above the other
- **AND** its `material_overlap` is greater than zero while the other's is zero

#### Scenario: The size weight comes from configuration
- **WHEN** the substitutes ordering is inspected
- **THEN** the size penalty weight is read from settings
- **AND** setting that weight to zero reproduces exactly the ordering the remaining terms produce alone

### Requirement: The size term is inert unless both sides declare a size
The size penalty MUST apply only when the source product and the candidate both declare a `size_label`. When either side declares none, the term MUST contribute nothing, because an absent size is not a size mismatch.

#### Scenario: An undeclared source size disables the term
- **GIVEN** the source product declares no `size_label`
- **WHEN** substitutes are requested
- **THEN** no candidate is penalised for its size
- **AND** the ordering equals the ordering the same computation produces with the size term removed

#### Scenario: An undeclared candidate size disables the term for that candidate
- **GIVEN** the source product declares a size and a candidate declares none
- **WHEN** substitutes are requested
- **THEN** that candidate is not penalised for its size

### Requirement: Availability demotes and never removes
When the request carries a point of sale, the availability projection MUST be read as a signal and MUST NOT restrict the candidate universe. A candidate the projection reports as out of stock MUST still be returned, ordered below its available peers. A candidate for which no projection row was read MUST NOT be treated as out of stock. The response MUST declare the age of the projection.

#### Scenario: An out-of-stock candidate is demoted, not dropped
- **GIVEN** the request carries a point of sale and the projection reports a candidate as out of stock
- **WHEN** substitutes are requested
- **THEN** that candidate is present in the response
- **AND** it is ordered below comparable candidates the projection reports as available
- **AND** the response declares the projection age

#### Scenario: An absent projection row is not read as zero stock
- **GIVEN** a candidate the point of sale does not carry, so no projection row exists for it
- **WHEN** substitutes are requested
- **THEN** that candidate is not demoted by the availability term

### Requirement: No rule of this capability drops a live family member
No rule of this capability MAY remove an active member of the source product's family from the candidate universe. The only hard filter is the piece type, which every member of a family shares by construction, so a sibling can only ever be absent by falling outside the over-retrieval window — never by being excluded. Every family member inside that window MUST report `family_match` as true.

**The guarantee is the absence of an excluding rule and not a bound on the window**, and that distinction is what this wording exists to make. Under the default window — three times the requested page size, so thirty rows — every active sibling is reached, because a product's distance to its own family runs to a measured maximum of 0,123; the scenario below is stated against that default for exactly that reason. A caller that asks for a page smaller than the family MUST NOT expect every sibling back, and the retriever MUST NOT silently widen the window to pretend otherwise: what it produced is declared in `candidates_returned`.

Family membership MUST NOT by itself place a candidate ahead of another; its position MUST be decided by the ordering rule like any other candidate.

#### Scenario: Every living sibling is present
- **GIVEN** the source product belongs to a family with other active members
- **WHEN** substitutes are requested with the default over-retrieval window
- **THEN** every active member of that family appears in the returned candidate set
- **AND** each of them reports `family_match` as true

#### Scenario: Family membership does not force the first position
- **GIVEN** a candidate outside the family scores higher under the ordering rule than a family member
- **WHEN** substitutes are requested
- **THEN** the non-family candidate is ordered above that family member

### Requirement: Every candidate explains itself, and an absent signal is declared
Each candidate MUST carry `similarity_signals` with `material_overlap` computed from the material sets, `style_similarity` computed from the style tag sets, `family_match`, and `visual_similarity` as null because the visual and textual vector spaces are not fused. Each candidate MUST also carry human-readable `match_reasons` that state the size relationship to the source product. When neither side carries style tags, `match_reasons` MUST state that there were no style tags to compare, so that a `style_similarity` of zero can never be read as evidence of differing styles. `style_similarity` MUST NOT be derived from the embedding.

#### Scenario: The size relationship is always stated
- **WHEN** a candidate is returned for a source product that declares a size
- **THEN** its `match_reasons` state whether the candidate matches that size or differs from it

#### Scenario: Absent style tags are declared rather than reported as zero similarity
- **GIVEN** neither the source product nor the candidate carries style tags
- **WHEN** the candidate is returned
- **THEN** its `style_similarity` is zero
- **AND** its `match_reasons` state that there were no style tags to compare

#### Scenario: The visual signal is null by design
- **WHEN** any candidate is returned
- **THEN** its `visual_similarity` is null

### Requirement: Substitutes do not abstain, and the response says so
The substitutes endpoint MUST NOT abstain: `low_confidence` MUST be reported as false. The decision MUST be documented together with the measured nearest-neighbour distribution that justifies it, so the absence of abstention is recorded as a decision rather than an omission.

#### Scenario: A source product without family or obvious equivalents still gets an answer
- **GIVEN** the source product has no family and no near equivalent in the catalogue
- **WHEN** substitutes are requested
- **THEN** candidates are returned
- **AND** `low_confidence` is false

### Requirement: An unusable source product is an explicit error, never an empty success
When the requested `product_id` is absent from the index, inactive, or carries no embedding, the service MUST answer with an explicit error that names the cause. It MUST NOT answer 200 with an empty candidate list, because an empty success is indistinguishable from a catalogue with no substitutes.

#### Scenario: An unknown source product is rejected by name
- **GIVEN** the requested `product_id` does not exist in the index
- **WHEN** substitutes are requested
- **THEN** the response is an explicit error naming the cause
- **AND** the response is not a 200 with an empty candidate list

#### Scenario: A source product without an embedding is rejected by name
- **GIVEN** the requested product exists in the index but carries no embedding
- **WHEN** substitutes are requested
- **THEN** the response is an explicit error naming the cause

### Requirement: Substitutes are evaluated in their own slice anchored by source product
The golden-set queries reserved for substitutes MUST each declare an explicit source product, and MUST be evaluated by calling the substitutes pipeline with that product rather than by resolving the query text with the product retriever first. The evaluation MUST be reported as a slice of its own and MUST NOT alter the published ablations table, its configurations or its judgements. The set MUST include at least one source product that belongs to no family.

#### Scenario: Each substitutes query is anchored to a source product
- **WHEN** the substitutes evaluation slice is loaded
- **THEN** every query in it declares an explicit source product identifier
- **AND** the run calls the substitutes pipeline with that identifier

#### Scenario: The published ablations table is untouched
- **WHEN** the substitutes evaluation has run
- **THEN** the published ablations table, its configurations and its judgements are unchanged

#### Scenario: The slice covers a source product without a family
- **WHEN** the substitutes evaluation slice is loaded
- **THEN** at least one of its source products belongs to no family
