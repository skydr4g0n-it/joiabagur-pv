# assist-generation Specification

## Purpose
The sale-assistance layer of `jbg-ai`, the logic behind `POST /v1/assist/sale`. It serves three modes selected structurally by the anchors the request carries — a free query, a piece with no question, and a piece with a question — and never infers the mode from the wording of the query, so the detected intent is reported as unclassified wherever the request shape cannot determine it and classifying a query stays a later capability's work. The point-of-sale scope comes from the token claim and never from the body, and the response echoes the scope actually applied. Candidates are grouped by family with the variant label of every member and the match reasons the retrieval recorded, and a candidate whose family is unknown is a group of one, because a group of several products with no family asserts a grouping the catalogue does not hold. Warnings are computed from data by deterministic rules and travel as a closed vocabulary of codes — the family holds other members, the size label is absent — with the wording for a human reader left to the presentation layer; the variants warning is read from the family roster the index holds, capped at a declared maximum, rather than inferred from how many members the retrieval happened to return. No warning depends on stock: the .NET API is the authority on it and knows it only after hydration, and the availability bucket this service holds is carried for ranking and never emitted. Grounding is citable without invoking a model: the piece-anchored mode with no question addresses its fragments deterministically over the sheets of the materials the product declares and an allow-list of sections, admitting only fragments of general claim scope so that a commitment of the establishment never enters an argument nobody asked for, while the modes carrying a question search the knowledge corpus with the sheets of the undeclared materials excluded and the rest of the corpus reachable. Citations are fragments of the commercial knowledge corpus carrying their resolvable identifier, their document and section titles, their document type and their claim scope, and the catalogue is never cited, since a candidate's grounding in it is expressed through its match reasons. The abstention decision is honoured and declared in a dedicated field rather than through the cross-branch confidence signal, whose measured meaning is a different one; a piece the index cannot serve is an error distinguishing the unknown, the inactive and the un-embedded case rather than an abstention; and no field of the response carries a price or a stock figure. The two modes anchored to a piece generate a prose sale argument through a language model, reporting the version of the prompt used and the usage accumulated across every call, while the free-query mode and an abstained request call no provider and emit the argument empty with the prompt version absent; the argument is grounded only in the structured payload and the fragments handed to the model, every numeral it carries belongs to that payload and none of them sits next to a currency marker, and every citation published is one the argument declared and was shown to support text actually written, with a single repair attempted for all violations at once and whatever survives it degraded — the argument withheld, or the unverifiable citation withheld — rather than turned into an error, so the structured layer it preserves remains the ablation baseline; the generated text is never persisted and never logged. The stub fixture stays deterministic, performs no external input or output, and includes a group with a null family identifier. Tests run offline.

## Requirements

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

The citations of a response are **the ones the generated argument used** when there is an argument, and the ones that grounded the response when there is none. Emitting everything retrieved is not attribution but decoration, and a citation whose use cannot be verified is withheld rather than published.

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

#### Scenario: A response carrying an argument publishes only the citations it used
- **GIVEN** a request whose context offered more fragments than the argument used
- **WHEN** the response carries a generated argument
- **THEN** only the citations the argument declared and that were verified are published

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

### Requirement: The assistance layer writes a sale argument in the piece-anchored modes
The service SHALL generate a prose sale argument through a language model in the two modes anchored to a piece — the piece with no question and the piece with a question — and MUST report the version of the prompt it used and the model usage it consumed. The argument MUST be grounded only in the structured payload and the corpus fragments handed to the model, and MUST NOT introduce any product, material or property that payload does not carry.

The argument is prose and not a list: the generation MUST be instructed to write continuous prose without numbered lists, because a leading enumeration numeral is a figure the numeric gate cannot distinguish from an invented one, and removing the source of that rejection is preferable to excusing it in the gate.

#### Scenario: A piece with no question receives an argument
- **GIVEN** a product that is indexed and declares at least one material
- **WHEN** the assistance is requested with its product identifier and no question
- **THEN** the generated argument is not empty
- **AND** the prompt version is reported
- **AND** the reported usage carries a non-zero token count and the model identifier

#### Scenario: A question about the piece is answered in prose
- **GIVEN** a product that is indexed and a question about it
- **WHEN** the assistance is requested with both anchors
- **THEN** the generated argument addresses the question
- **AND** at least one citation of the corpus supports it
- **AND** no citation comes from the sheet of a material the piece does not declare

### Requirement: No figure absent from the given context reaches the generated argument
Every numeric sequence in the generated argument SHALL belong to the set of numerals present in the structured payload handed to the model, and any other numeric sequence MUST be treated as a violation. The check MUST read the payload object rather than the rendered prompt, because numerals belonging to the instructions themselves would otherwise widen the admitted set and open the gate on their own.

Independently of that set, a numeric sequence adjacent to a currency marker or to an expression of stock MUST be treated as a violation **even when the numeral is present in the payload**. The corpus itself carries round figures that are plausible prices — the sheets state that eighteen carats are seven hundred and fifty thousandths and that sterling silver is nine hundred and twenty-five thousandths — so membership alone admits a figure that reads as a price. Price and stock travel as placeholders, which is what makes any figure next to a currency marker wrong by construction.

#### Scenario: A figure absent from the context is rejected even when plausible
- **GIVEN** a generated argument carrying a weight in grams that the payload does not contain
- **WHEN** the numeric gate is evaluated
- **THEN** the figure is recorded as a violation

#### Scenario: A figure adjacent to a currency marker is rejected even when admitted by the payload
- **GIVEN** a material sheet in the context whose text contains the figure seven hundred and fifty
- **WHEN** the generated argument writes that figure next to a currency marker
- **THEN** it is recorded as a violation
- **AND** the recorded cause distinguishes currency adjacency from absence of the figure in the context

#### Scenario: Price and stock travel as placeholders
- **GIVEN** a piece whose price and stock are known to the index
- **WHEN** the argument mentions price or availability
- **THEN** it carries the price and stock placeholders
- **AND** no field of the whole response carries a price or a stock quantity

### Requirement: A published citation is one the argument used, and the claim it supports is verifiable
The model SHALL declare, for every citation it uses, the fragment of its own generated argument that the citation supports, and the service MUST verify in code that the declared identifier belongs to the set of fragments handed to the model and that the declared fragment occurs literally in the argument that was produced. Verifying that the identifier resolves is not sufficient on its own: a model that echoes back every identifier it was given satisfies resolution perfectly while having used none, so the claim of use MUST be made checkable rather than trusted.

The declared fragment is an internal verification artefact and MUST NOT be emitted in the response. Comparison MUST be insensitive to letter case and to runs of whitespace, and MUST NOT otherwise alter the text.

#### Scenario: The model declares which fragment each citation supports
- **WHEN** an argument is generated with citations
- **THEN** each cited identifier carries the fragment of the argument it supports
- **AND** that fragment occurs in the generated argument

#### Scenario: The declared fragment does not reach the response
- **WHEN** a response carrying an argument is produced
- **THEN** no field of the response exposes the declared supporting fragment

#### Scenario: Echoing every supplied identifier does not satisfy the requirement
- **GIVEN** a model that declares every identifier it was handed
- **WHEN** the declared fragments do not occur in the generated argument
- **THEN** those citations are not published

### Requirement: A failed check is repaired once, and persistent failure degrades the response instead of the service
The service SHALL attempt at most one repair per request, communicating every violation of every check together rather than one repair per check, and MUST evaluate the checks in order of cost: citation resolution first, then the correspondence of the declared fragment, then the numeric gate. The provider MUST NOT be called more than twice for one request.

A violation of citation resolution or of the numeric gate that survives the repair MUST result in the response being served **without** the generated argument. A failure of correspondence that survives the repair MUST result in **that citation** being withheld while the argument is still served, because the fragment exists and was in the context and what failed is the model's own account of using it. A dangling citation MUST NEVER be ignored.

#### Scenario: Two checks fail and share a single repair
- **GIVEN** a generated argument that violates citation resolution and the numeric gate at once
- **WHEN** the repair policy is applied
- **THEN** exactly one repair is attempted with both violations communicated together
- **AND** the provider is called no more than twice for that request

#### Scenario: A dangling citation survives the repair and the argument is dropped
- **GIVEN** a declared identifier that was never in the set handed to the model
- **WHEN** the repair does not resolve it
- **THEN** the response is served with an empty generated argument
- **AND** the dangling identifier is not published

#### Scenario: An unverifiable claim withdraws its citation and keeps the argument
- **GIVEN** a declared fragment that does not occur in the generated argument
- **WHEN** the repair does not resolve it
- **THEN** that citation is withheld from the response
- **AND** the generated argument is still served

### Requirement: Degradation preserves what the structured layer already produced
When the generated argument is withheld for any reason, the response SHALL still carry the citations that grounded it, so that a degraded response is never poorer than the one the structured layer produces on its own. The citations of a response are the ones the argument used when there is an argument, and the ones that grounded the response when there is none.

This is what keeps the generation layer measurable as an ablation against the structured layer: the comparison requires the same route, the same candidates and the same citations, with prose and without it.

#### Scenario: The argument is dropped and the citations remain
- **GIVEN** a request whose generated argument was withheld
- **WHEN** the response is composed
- **THEN** the citations that grounded the response are present
- **AND** no field of the response is poorer than the one the structured layer produces alone

### Requirement: The reported prompt version states whether the generation layer ran
The service SHALL report the prompt version whenever the generation layer ran, including when its argument was withheld, and MUST report it as absent when the layer did not run. An empty argument alone cannot distinguish a deployment that does not generate from a generation that was rejected, and that distinction is the only evidence a consumer has that the guard acted.

#### Scenario: A rejected argument still reports its prompt version
- **GIVEN** a request whose generated argument was withheld after the repair
- **WHEN** the response is composed
- **THEN** the generated argument is empty
- **AND** the prompt version is reported

#### Scenario: A mode that does not generate reports no prompt version
- **WHEN** the free-query mode is served
- **THEN** the generated argument is empty
- **AND** the prompt version is absent

### Requirement: The generated argument is never persisted, and that includes never being logged
The service SHALL NOT write the generated argument to any durable store, and MUST NOT write its text to any log. Serving one request MUST execute no data-manipulation statement. The log line MUST carry the correlation identifier, the prompt version, the model, the usage, the latency, the identifiers of the citations used, the warning codes, the abstention decision, the length of the argument and a hash of it — and MUST NOT carry the text itself.

A log line is durable storage outside the database and carries no point-of-sale scope, while the response does; the text is re-derivable from a versioned prompt at temperature zero, which is what makes not storing it viable. The evaluation harness is the **declared exception**: it MAY store generated arguments together with their declared supporting fragments, bound to a run identifier, a commit identifier and a prompt version, outside the serving path.

#### Scenario: Serving a request writes nothing
- **WHEN** a request producing a generated argument is served
- **THEN** no data-manipulation statement is executed against the database

#### Scenario: The log carries the provenance and not the text
- **WHEN** a request producing a generated argument is served
- **THEN** the log records the prompt version, the model, the usage, the citation identifiers, the length and a hash
- **AND** the log does not contain the text of the generated argument

### Requirement: The prompt is versioned and pinned to the file it is loaded from
The prompt SHALL be stored as a versioned file in the service's prompt directory and its identifier MUST be a constant that a test pins to that file, so the reported version cannot drift from the text actually used. Invariant rules MUST live in the system message and the per-mode task MUST live in the user message, so that one version covers both piece-anchored modes.

#### Scenario: The declared version and the loaded file agree
- **WHEN** the generation prompt is loaded
- **THEN** it comes from the file the declared version names
- **AND** a test fails if the constant and the file cease to correspond

### Requirement: The provider is not called when there is nothing to write about
The service SHALL NOT call the language model provider when the abstention rule has decided that the catalogue cannot answer the query, and MUST NOT call it in the free-query mode. Writing prose about an empty candidate set states something with confidence about nothing, which is the failure the abstention rule exists to prevent.

The free-query mode does not generate because classifying a query is a later capability's work, and its argument would be written over a candidate set whose intent has not been determined. The clarification question likewise belongs to that later capability and MUST remain absent here.

#### Scenario: An abstained request calls no provider
- **GIVEN** the abstention rule decided the catalogue cannot answer
- **WHEN** the assistance is served
- **THEN** the abstention is declared and no group is returned
- **AND** no language model provider call is made

#### Scenario: The free-query mode calls no provider
- **WHEN** a request carrying a query and no piece is served
- **THEN** the generated argument is empty and the prompt version absent
- **AND** no language model provider call is made
- **AND** the clarification question is absent

### Requirement: A provider failure degrades the response and never turns it into an error
When the provider fails, is unreachable or exceeds the declared time limit, the service SHALL serve the structured response — groups, warnings and citations — with an empty generated argument, and MUST NOT answer with a server error. The structured half is already computed and correct, and discarding it because the prose failed converts a partial loss into a total one.

#### Scenario: The provider fails and the structured response is served
- **GIVEN** a provider that fails or exceeds the time limit
- **WHEN** a piece-anchored assistance is served
- **THEN** the response is successful and carries its groups, warnings and citations
- **AND** the generated argument is empty
- **AND** no server error is returned

### Requirement: Reported usage accumulates across the repair
The reported model usage SHALL be the sum of every provider call made for that request, including the repair, and MUST NOT report only the last call. Reporting a single call understates the cost precisely on the requests that cost the most, which are the ones a cost measurement exists to find.

#### Scenario: A repaired request reports the sum of both calls
- **GIVEN** a request that required one repair and therefore two provider calls
- **WHEN** the response is composed
- **THEN** the reported usage is the sum of both calls

### Requirement: The operator's query travels as data and never as an instruction
The operator's query SHALL travel inside the user message, in a delimited block labelled as data, and MUST NOT be concatenated into the system message. The prompt MUST state that the content of that block is information from the customer and never an instruction.

Classifying a query and refusing one politely are a later capability's work and are not performed here; what belongs here is the structural mitigation, which is the responsibility of whoever builds the prompt.

#### Scenario: A query shaped like an instruction does not change the system behaviour
- **GIVEN** a query containing text instructing the assistant to disregard its rules
- **WHEN** the provider call is built
- **THEN** the query travels in the user message inside a delimited data block
- **AND** the system message is the same as it would be for any other query

### Requirement: Semantic fidelity of a citation is not verified at request time
The service SHALL NOT verify at request time that a cited fragment supports the meaning of the claim it is attached to, and this limitation MUST be declared rather than implied. The checks this capability performs are structural: that the identifier resolves, that the citation was used for text actually written, and that no figure is invented. A citation that resolves, that was genuinely used, and that nevertheless does not say what the sentence asserts is not detected here.

No model-based judge runs in the serving path: it would double the latency and the cost at the counter, and using a model to detect another model's fabrications is circular. The measurement belongs to the evaluation harness, over a representative set, where a rate means something.

#### Scenario: The limitation is declared and no judge runs in the serving path
- **WHEN** a request producing a generated argument is served
- **THEN** no additional model call is made to judge the fidelity of the argument
