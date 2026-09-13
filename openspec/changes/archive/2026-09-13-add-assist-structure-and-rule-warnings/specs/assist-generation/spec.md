## ADDED Requirements

### Requirement: Sale assistance is served in three modes, anchored by piece, by query, or by both

The service SHALL serve `POST /v1/assist/sale` in three modes, selected by which anchors the request carries: a free query with no piece, a piece with no question, or a piece with a question. The request MUST accept a product identifier and a query as independent optional fields and MUST require **at least one** of them. A request carrying neither MUST be rejected as invalid, naming both fields.

The `pos_id` scope MUST come from the token claim and never from the request body, and the response MUST echo the scope actually applied.

#### Scenario: A piece with no question is served as a piece-anchored assistance
- **WHEN** an authenticated client calls the route with a product identifier and no query
- **THEN** the response carries exactly one group, the one holding that product
- **AND** the detected intent is the piece-anchored one

#### Scenario: A free query with no piece is served
- **WHEN** an authenticated client calls the route with a query and no product identifier
- **THEN** the response is served over the candidates the retrieval produced
- **AND** the detected intent is the unclassified one

#### Scenario: A piece with a question is served as both
- **WHEN** an authenticated client calls the route with a product identifier and a query
- **THEN** the groups are anchored to that product
- **AND** the citations answer the question asked

#### Scenario: A request with neither anchor is rejected
- **WHEN** an authenticated client calls the route with neither a product identifier nor a query
- **THEN** the response is a validation error
- **AND** the error names both fields as the alternatives

#### Scenario: The scope comes from the token and never from the body
- **GIVEN** the token declares one point of sale and the body declares a different one
- **WHEN** the route is called
- **THEN** the scope applied is the one in the token
- **AND** the response echoes that same scope

### Requirement: The detected intent is derived from the request shape and never guessed from words

The service SHALL derive the detected intent from which anchors the request carries and MUST NOT infer it from the wording of the query. When a piece is anchored and no question is asked, the intent MUST be reported as the piece-anchored one. In every other mode the intent MUST be reported as unclassified, because classifying a query is not this capability's work.

#### Scenario: A piece with no question reports a determinate intent
- **WHEN** the route is called with a product identifier and no query
- **THEN** the reported intent is the piece-anchored one

#### Scenario: A query reports an unclassified intent whatever it says
- **WHEN** the route is called with any query
- **THEN** the reported intent is the unclassified one
- **AND** two queries with different wording but the same anchors report the same intent

### Requirement: Candidates are grouped by family, and a product without a family is a group of one

The response SHALL group candidates by their family identifier, exposing the variant label of every member when it is known. A group whose family is unknown MUST carry a null family identifier and MUST contain **exactly one** member, because a group of several products with no family asserts a grouping the catalogue does not hold.

Every member MUST expose the match reasons the retrieval recorded for it, so that the reason a candidate is present travels as data rather than as prose.

#### Scenario: Members of one family are grouped under it
- **GIVEN** a product that belongs to a family with several members
- **WHEN** the route is called anchored to that product
- **THEN** the group carries that family identifier
- **AND** the members expose their variant label when it is known

#### Scenario: A product with no family is a group of one
- **GIVEN** a product that belongs to no family
- **WHEN** the route is called anchored to that product
- **THEN** the group carries a null family identifier
- **AND** the group contains exactly one member

#### Scenario: No group with a null family carries more than one member
- **WHEN** any response is produced
- **THEN** every group with a null family identifier contains exactly one member

#### Scenario: Each member carries the reasons it was retrieved for
- **WHEN** a group member is returned
- **THEN** it exposes the match reasons the retrieval recorded
- **AND** those reasons are the retrieval vocabulary and not a generated sentence

### Requirement: Warnings are computed from rules and travel as a closed vocabulary of codes

Warnings SHALL be computed from data by deterministic rules and MUST NOT be produced by a model. Every warning emitted MUST belong to a closed vocabulary declared by this capability, and the service MUST NOT emit a warning in natural language: the wording for a human reader belongs to the presentation layer.

This capability SHALL emit exactly two codes: one stating that the product's family holds other members, and one stating that the product declares no size label.

The service MUST NOT emit any warning that depends on real stock. Stock is the .NET API's authority and is known only after hydration, and the availability bucket this service holds is carried for ranking, is never emitted, and may be stale.

#### Scenario: A family with other members raises the variants warning
- **GIVEN** a product whose family holds more than one member
- **WHEN** the route is called anchored to that product
- **THEN** the warnings contain the code stating that the family holds other members

#### Scenario: A missing size label raises its warning
- **GIVEN** a product that declares no size label
- **WHEN** the route is called anchored to that product
- **THEN** the warnings contain the code stating that the size label is absent

#### Scenario: Every warning belongs to the closed vocabulary
- **WHEN** any response is produced
- **THEN** every warning it carries is a member of the declared closed vocabulary
- **AND** none of them is a sentence in natural language

#### Scenario: No stock warning is emitted by this service
- **GIVEN** a product whose availability bucket at the requesting point of sale is zero
- **WHEN** the route is called anchored to that product
- **THEN** the warnings contain no code about critical stock and none about members out of stock

### Requirement: The variants warning is computed from the family roster, not from the candidates retrieved

The warning stating that a family holds other members SHALL be computed from the family's full roster as the index holds it, and MUST NOT be inferred from how many members the retrieval happened to return. Grouping operates over retrieved candidates; knowing that a member exists which was not retrieved requires reading the roster.

The roster MUST be read from the index schema only, and MUST be capped at a declared maximum so a large family cannot produce an unbounded read.

#### Scenario: The warning fires on a member the retrieval did not return
- **GIVEN** a product belonging to a family of four members, of which the retrieval returned two
- **WHEN** the route is called
- **THEN** the variants warning is raised
- **AND** the reason it is raised is the roster's count and not the candidate count

#### Scenario: A family of one raises no variants warning
- **GIVEN** a product whose family holds only that product
- **WHEN** the route is called
- **THEN** the variants warning is not raised

#### Scenario: The roster is bounded
- **GIVEN** a family whose membership exceeds the declared cap
- **WHEN** the roster is read
- **THEN** it returns at most the capped number of members
- **AND** the cap is a declared value and not an incidental limit

### Requirement: A piece with no question is grounded by deterministic addressing, never by a search

When the request anchors a piece and asks no question, the service SHALL obtain its citable fragments by addressing them directly by identity, from the material sheets of the materials the product declares, over an explicit allow-list of sections. It MUST NOT run a similarity search for this mode, because the address is exact and a search could return a fragment about another material.

The service MUST include **only** fragments whose claim scope is general. A fragment that records a commitment of the establishment MUST NOT enter an argument nobody asked for.

The number of materials considered and the allow-list of sections MUST be parameters of the call and not inlined constants, so a later change can compare configurations in one process.

#### Scenario: The citations come from the declared materials' sheets
- **GIVEN** a product declaring one canonical material
- **WHEN** the route is called anchored to that product with no question
- **THEN** the citations are fragments of that material's sheet
- **AND** they belong to the declared allow-list of sections

#### Scenario: No sheet of an undeclared material is cited
- **GIVEN** a product declaring one canonical material
- **WHEN** the route is called anchored to that product with no question
- **THEN** no citation comes from the sheet of any material the product does not declare

#### Scenario: A commitment of the establishment never enters an unrequested argument
- **GIVEN** a product whose declared material has a sheet carrying a section of establishment scope
- **WHEN** the route is called anchored to that product with no question
- **THEN** no citation carries the establishment claim scope

#### Scenario: No similarity search runs for this mode
- **WHEN** the route is called anchored to a product with no question
- **THEN** no vector search over the knowledge index is performed
- **AND** no embedding provider call is made

#### Scenario: A piece declaring two materials also receives the mixed-piece guidance
- **GIVEN** a product declaring two canonical materials
- **WHEN** the route is called anchored to that product with no question
- **THEN** the citations also include the mixed-piece section about which part governs

### Requirement: Citations are corpus fragments carrying their scope, and the catalogue is never cited

Citations SHALL be fragments of the commercial knowledge corpus and nothing else. Each citation MUST carry its resolvable citation identifier, its document title, its section title, its document type and its **claim scope**, so that a commitment of the establishment is distinguishable from a fact of the world by the consumer that renders it.

The service MUST NOT emit a citation that points at a product or at the catalogue: the product's metadata already travels in the response, so citing it would verify nothing. The grounding of a candidate in the catalogue is expressed through its match reasons.

#### Scenario: A citation resolves and locates
- **WHEN** a citation is returned
- **THEN** it carries its citation identifier, its document title and its section title

#### Scenario: The claim scope travels with every citation
- **WHEN** a citation is returned
- **THEN** it carries its claim scope
- **AND** the scope is one of the values the corpus declares

#### Scenario: The catalogue is never cited
- **WHEN** any response is produced
- **THEN** no citation refers to a product or to the catalogue as its source

### Requirement: Abstention is honoured and declared in a field of its own

The service SHALL return no group when the retrieval layer's abstention rule decides that the catalogue cannot answer the query, and MUST declare the abstention in a dedicated boolean field of the response. The field MUST be emitted in every mode, and in the piece-anchored mode with no question its value MUST be false, because there is no retrieval to abstain from.

The service MUST NOT express this decision by reusing the cross-branch confidence signal, whose measured meaning is a different one.

The effective value of the abstention configuration MUST travel as a parameter of the call rather than being read from the environment inside, so an evaluation can compare configurations in one process.

#### Scenario: An abstained query returns nothing and says so
- **GIVEN** a query for which the abstention rule fires
- **WHEN** the route is called with it
- **THEN** the abstention field is true
- **AND** no group is returned

#### Scenario: An answerable query is not silenced
- **GIVEN** a query the catalogue can answer
- **WHEN** the route is called with it
- **THEN** the abstention field is false
- **AND** at least one group is returned

#### Scenario: The field is always present
- **WHEN** any response is produced in any mode
- **THEN** the abstention field is present
- **AND** in the piece-anchored mode with no question its value is false

### Requirement: An unusable piece is an error and never an abstention

When the request anchors a product that the index does not hold, or holds as inactive, or holds without an embedding, the service SHALL answer with an error that distinguishes the three cases. It MUST NOT answer successfully with the abstention field set, because that would assert that the catalogue cannot answer when the problem is the piece.

#### Scenario: An unknown product is an error
- **WHEN** the route is called anchored to a product the index does not hold
- **THEN** the response is an error naming that case

#### Scenario: An inactive product is a different error
- **WHEN** the route is called anchored to a product the index holds as inactive
- **THEN** the response is an error naming that case

#### Scenario: A product without an embedding is a third error
- **WHEN** the route is called anchored to a product the index holds without an embedding
- **THEN** the response is an error naming that case

#### Scenario: None of the three is served as an abstention
- **WHEN** any of the three unusable cases occurs
- **THEN** the response is not a success with the abstention field set

### Requirement: This capability generates no prose and calls no provider

Until the generation change delivers it, the service SHALL emit the generated argument as an empty value, the prompt version as absent, and the reported model usage as zero. The assistance module MUST NOT call a language model provider, and MUST NOT introduce an embedding call beyond the ones the retrieval it consumes already makes.

#### Scenario: The argument is empty and its provenance absent
- **WHEN** any response is produced with stubs disabled
- **THEN** the generated argument is empty
- **AND** the prompt version is absent
- **AND** the reported usage is zero

#### Scenario: No provider is called
- **WHEN** the route is served in any mode
- **THEN** no language model provider call is made

### Requirement: No price and no stock figure appears anywhere in the response

The response SHALL contain no concrete price and no stock quantity in **any** field, not only in the generated argument. The index holds a copy of the price for ordering and holds an availability bucket for demotion, and neither may cross the boundary: the .NET API is the authority on both.

#### Scenario: The whole response is free of price and stock figures
- **WHEN** the route is served in any mode
- **THEN** no field of the response carries a price
- **AND** no field carries a stock quantity or an availability bucket

### Requirement: With stubs disabled the route serves the real implementation

When `STUB_MODE` is disabled, `POST /v1/assist/sale` SHALL serve the real implementation and MUST NOT answer HTTP 501: the placeholder that named a future change no longer applies. When `STUB_MODE` is enabled, the route MUST keep serving a deterministic fixture that performs no external input or output.

The fixture MUST include at least one group with a null family identifier, so that a client cannot ship without ever handling the case that is the majority of the catalogue.

#### Scenario: The route no longer answers 501 with stubs disabled
- **GIVEN** `STUB_MODE` is disabled
- **WHEN** an authenticated client calls the route with a valid body
- **THEN** the response status is not 501

#### Scenario: The fixture stays deterministic
- **GIVEN** `STUB_MODE` is enabled
- **WHEN** the route is called twice with the same body
- **THEN** both responses are identical
- **AND** no database, provider or network call is made

#### Scenario: The fixture exercises the absent family
- **GIVEN** `STUB_MODE` is enabled
- **WHEN** the route is called
- **THEN** at least one returned group carries a null family identifier

### Requirement: Assistance tests run offline

The tests of this capability SHALL run with no call to a language model, to an embedding provider or to a managed database. Fakes MUST be injected through the existing constructor seams and fixtures MUST live in the service's test tree. Tests that require a database MUST use an ephemeral container and MUST skip when it is unreachable rather than failing.

#### Scenario: No external call is made by the suite
- **WHEN** the assistance tests run
- **THEN** no language model, embedding provider or managed database is contacted

#### Scenario: Database tests skip when the container is unavailable
- **GIVEN** the container runtime is unreachable
- **WHEN** the tests that need a database run
- **THEN** they are skipped rather than reported as failures
