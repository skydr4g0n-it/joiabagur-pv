## ADDED Requirements

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

## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: This capability generates no prose and calls no provider
**Reason**: This requirement existed to declare the absence of the generation layer as a deliberate shape rather than an omission, so that the layer could be measured against the structured one as an ablation. The layer is now delivered and the prohibition it stated is no longer true: the service calls a language model provider in the two piece-anchored modes and emits prose, a prompt version and real usage.

**Migration**: Its guarantees are preserved and narrowed rather than dropped. The prohibition on calling a provider survives for the free-query mode and for an abstained request, in *The provider is not called when there is nothing to write about*. The prohibition on introducing embedding calls beyond the retrieval's own is unchanged and untouched by this change, which adds no vector search. The empty argument with an absent prompt version remains the response of a deployment that does not generate, now stated in *The reported prompt version states whether the generation layer ran*.
