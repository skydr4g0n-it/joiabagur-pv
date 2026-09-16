## ADDED Requirements

### Requirement: The detected intent is a routing verdict in the free-query mode and remains structural in the anchored ones
The service SHALL report, for a request carrying a query and no piece, an intent that states the routing verdict the classifier reached, and MUST keep deriving the intent structurally in the two piece-anchored modes, where the piece-anchored value MUST NOT change. The reported value MUST belong to a closed vocabulary declared by this capability, and when no classification could be made the service MUST report the unclassified value rather than guessing one.

The unclassified value therefore carries a second meaning from this capability onwards: it no longer states that queries are not classified at all, it states that this particular request could not be classified. Both readings are honest and a consumer needs no new field to tell them apart, because the log records why.

#### Scenario: A piece with no question keeps its determinate intent
- **WHEN** the route is called with a product identifier and no query
- **THEN** the reported intent is the piece-anchored one, unchanged from before this capability routed anything
- **AND** no classifier call is made

#### Scenario: A free query reports the verdict the router reached
- **WHEN** the route is called with a query and no piece
- **THEN** the reported intent is the routing verdict
- **AND** the value belongs to the closed vocabulary of this capability

### Requirement: A query that is not about jewellery is refused before any retrieval runs
The service SHALL classify a free-text query that falls outside the jewellery domain and MUST refuse it without executing the product retrieval or the knowledge search, returning a successful response with no group and a refusal reason code from a closed vocabulary. The refusal MUST NOT be expressed as prose written by the model, because the Spanish a human reads belongs to the presentation layer.

#### Scenario: An out-of-domain query short-circuits before retrieval
- **WHEN** a query unrelated to the jewellery business is served
- **THEN** no product retrieval and no knowledge search are executed
- **AND** no group is returned and the response is successful
- **AND** the reported intent states that the query is out of domain
- **AND** a refusal reason code from the closed vocabulary is present

### Requirement: A jewellery query this catalogue cannot stock is refused, and that refusal is distinct from being out of domain
The service SHALL classify a free-text query that is plausible within jewellery but asks for a kind of object this catalogue does not stock, and MUST refuse it before retrieving, with a reason code that is distinct from the out-of-domain one. These two refusals MUST NOT share a code, because what an operator says to a customer differs between a trade the shop does not practise and a piece the shop does not carry.

#### Scenario: A neighbouring-trade request is refused with its own code
- **GIVEN** a query asking for an object a jewellery shop might sell and this catalogue does not carry
- **WHEN** the assistance is served
- **THEN** no group is returned and no retrieval is executed
- **AND** the reason code differs from the one used for an out-of-domain query

#### Scenario: An answerable query is never refused
- **GIVEN** a query belonging to any answerable category of the evaluation set, including those that name no piece type at all
- **WHEN** the assistance is served
- **THEN** the router admits it
- **AND** the retrieval is executed and groups are returned

### Requirement: A query that does not carry enough to search receives a clarification question instead of candidates
The service SHALL emit a clarification question when the classifier determines that the query lacks the information needed to search, and MUST return no group and call no generation provider in that case. The clarification question MUST name the axis the query left out rather than asking for more detail in general terms.

#### Scenario: An ambiguous query is answered with a question
- **GIVEN** a query that does not determine what is being asked for
- **WHEN** the assistance is served
- **THEN** the clarification question is present and written in Spanish
- **AND** no group is returned
- **AND** no generation provider call is made

### Requirement: The clarification question is resolved in code from a closed catalogue of templates
The service SHALL select the text of the clarification question in code, from a closed catalogue of templates keyed by the missing axis, and MUST NOT publish text the language model wrote for that field. Two requests carrying the same query MUST produce exactly the same clarification text.

The contract types this field as prose rather than as a code, so the presentation layer cannot resolve it the way it resolves warning codes. Resolving it in code preserves determinism without changing the type, and keeps model-written prose out of a field that no numeric gate inspects.

#### Scenario: The same query always yields the same question
- **GIVEN** a query the classifier reports as insufficient
- **WHEN** the assistance is served twice
- **THEN** the clarification text is identical on both occasions
- **AND** the text corresponds to the axis the classifier reported as missing

### Requirement: The router's refusal is never expressed by reusing the abstention flag
The service SHALL report false in the abstention field when the router refused the request, and MUST carry the refusal in the intent and in the reason code instead. A request that reaches the retrieval and triggers the abstention rule MUST keep declaring the abstention exactly as before.

The two decisions come from different mechanisms: the abstention rule reads the shape of the distance profile after retrieving, and the router classifies before retrieving. Collapsing them onto one field would make the two rates this capability publishes indistinguishable from each other.

#### Scenario: A refused request does not claim to have abstained
- **WHEN** the router refuses a query
- **THEN** the abstention field is false
- **AND** the refusal is stated through the intent and the reason code

#### Scenario: An abstained request still declares its abstention
- **GIVEN** a query the router admits and for which the abstention rule then fires
- **WHEN** the assistance is served
- **THEN** the abstention field is true

### Requirement: The piece-anchored question mode is routed structurally and consults both indexes
The service SHALL treat a request carrying both a piece and a question as addressed to the catalogue and the corpus at once, deriving that from the request shape, and MUST NOT call the classifier in that mode. Refusing there would refuse a piece the caller named explicitly, which is a statement about the request that this service has not established.

#### Scenario: An anchored question makes no classifier call
- **WHEN** a request carrying a product identifier and a question is served
- **THEN** both indexes are consulted
- **AND** no classifier call is made
- **AND** the total provider calls for that request do not exceed the generation ceiling

### Requirement: A question the corpus does not cover is declared by a warning code and costs no extra provider call
The service SHALL emit a warning code from the closed vocabulary when an anchored question produces no citation after the knowledge distance threshold has been applied, and MUST determine this from the search result already computed rather than by making an additional provider call. The generated argument MUST then describe the piece without asserting that the question was answered.

Zero citations after that threshold already means the corpus cannot answer the question: the separation was measured when the threshold was calibrated. What was missing was a consumer able to tell that case apart from there being nothing worth citing.

#### Scenario: An uncovered question is declared rather than silently ignored
- **GIVEN** an anchored request whose question yields no citation after the threshold
- **WHEN** the assistance is served
- **THEN** the citation list is empty and the warning code is present
- **AND** no additional provider call was made to establish it
- **AND** the generated argument does not claim to answer the question

### Requirement: The free-query mode writes a sale argument over the route the classifier decided
The service SHALL generate prose for a free-text query the router admitted, selecting the task section of the prompt according to the route the classifier decided, and MUST report the prompt version it ran with. It MUST NOT generate when the router refused the request, when a clarification question was emitted, or when the abstention rule fired.

#### Scenario: An admitted free query receives an argument
- **GIVEN** a free query the router admits and for which candidates are returned
- **WHEN** the assistance is served
- **THEN** the generated argument is not empty
- **AND** the prompt version is reported
- **AND** the task section used corresponds to the decided route

### Requirement: No figure absent from the free-query context reaches its generated argument
The service SHALL admit, in the argument generated for a free-text query, only figures literally present in the material handed to the model, and MUST exclude from that material the internal product identifiers and the retrieval scores. Price and availability MUST travel as placeholders in this mode exactly as they do in the piece-anchored ones.

Each candidate admitted into the material widens the set of admissible figures, which is why the identifiers and the scores are excluded explicitly: their digits are arbitrary and a counter argument never mentions them.

#### Scenario: An invented figure is refused in the free-query mode too
- **GIVEN** a free query that produced several groups of candidates
- **WHEN** the generated argument contains a figure absent from the material handed to the model
- **THEN** the argument is refused by the same gate that governs the anchored modes

#### Scenario: Internal identifiers do not widen the admissible set
- **WHEN** the material for a free-text query is composed
- **THEN** it carries no internal product identifier and no retrieval score

### Requirement: An unavailable classifier degrades to the unclassified intent and to the previous behaviour
The service SHALL serve a successful response when the classifier has no credential, fails, exceeds its time limit or returns something that does not parse, reporting the unclassified intent and proceeding with the retrieval exactly as it did before this capability routed anything, and MUST record the degradation and its cause in the log. It MUST NOT answer with a server error and MUST NOT refuse the request on the classifier's behalf.

Failing closed would turn a provider interruption into a universal polite refusal, which is a total outage of the useful path. Failing open degrades to a behaviour that is already shipped, tested and declared, and the abstention rule remains in place as the net it was.

#### Scenario: A classifier fault does not change the outcome of an answerable query
- **GIVEN** a classifier that is unavailable, times out or returns an unparseable reply
- **WHEN** a free-text query is served
- **THEN** the response is successful and the reported intent is the unclassified one
- **AND** the retrieval is executed and the abstention rule still applies
- **AND** the degradation and its cause are recorded in the log

#### Scenario: No classifier credential is a valid deployment state
- **GIVEN** a deployment that configures no credential for the classifier
- **WHEN** a free-text query is served
- **THEN** no classifier call is attempted
- **AND** the response is the one this capability served before routing existed

### Requirement: One request makes at most three provider calls
The service SHALL make at most one classifier call and at most two generation calls for a single request, and the total MUST NOT exceed three. The classifier MUST NOT be retried and MUST NOT repair its own output, because an unparseable label is a degradation and not a violation to fix.

#### Scenario: The ceiling holds for a routed, generated and repaired request
- **GIVEN** a free-text query that is classified, generates and requires one repair
- **WHEN** the request completes
- **THEN** exactly three provider calls were made and never more
- **AND** the reported usage accumulates all of them

#### Scenario: An unparseable classifier reply is not retried
- **GIVEN** a classifier reply that does not parse
- **WHEN** the request is served
- **THEN** no second classifier call is made

### Requirement: The classifier's label is validated against a closed vocabulary before it is used
The service SHALL validate the label returned by the classifier against the closed vocabulary declared by this capability before acting on it, and MUST treat a value outside that vocabulary as an unparseable reply rather than propagating it. The action taken for each label MUST be determined in code and MUST NOT be delegated to the model.

The classification may be made by a model; the enforcement may not. This is what makes the guardrail a deterministic check around a non-deterministic component rather than an instruction the model is free to disregard.

#### Scenario: A label outside the vocabulary never reaches the response
- **GIVEN** a classifier reply carrying a label the vocabulary does not contain
- **WHEN** the request is served
- **THEN** the reply is treated as unparseable and the request degrades to the unclassified intent
- **AND** the unknown label does not appear in the response

### Requirement: The operator's query travels as data into the classifier call as well
The service SHALL place the operator's query inside a delimited block labelled as data within the user message of the classifier call, and MUST NOT concatenate it into the system message. A query written as an instruction MUST NOT change the classifier's system message.

#### Scenario: An instruction-shaped query does not alter the classifier's system message
- **GIVEN** a query containing text instructing the assistant to disregard its rules
- **WHEN** the classifier call is built
- **THEN** the query travels inside the delimited data block of the user message
- **AND** the system message is identical to the one used for any other query

### Requirement: The refusal rate of the router and the abstention rate of the retrieval are reported as separate figures
The evaluation SHALL report the router's refusal rate and the retrieval's abstention rate as distinct figures and MUST NOT present their sum as a single measure, and it MUST also report, as a figure of its own, the rate at which answerable queries are refused. A configuration that refuses any query of the unanchored descriptive category MUST be rejected regardless of how many impossible queries it catches.

The two rates come from different mechanisms and mean different things. Silencing a query the shop can answer is a visible failure at the counter, while failing to refuse an impossible one shows candidates that do not fit and the operator can see that, which is why the asymmetry decides the veto.

#### Scenario: The report keeps the two rates apart
- **WHEN** the routing evaluation is reported
- **THEN** the router's refusal rate and the retrieval's abstention rate appear as separate figures
- **AND** the report states that they are not summable
- **AND** the refusal rate over answerable queries is reported as a figure of its own

### Requirement: The classifier's prompt is derived from the catalogue vocabulary and never from the evaluation sets
The classifier's prompt SHALL be written from the closed catalogue vocabularies and the corpus documentation, and MUST NOT be derived from the annotations of the evaluation sets it will be measured against. The implementation MUST declare that this was observed.

The annotations of the golden set state the classification rule in words, so a prompt written from them would confirm itself by construction and the measurement would arbitrate nothing. This is the structural risk the golden set declared of its own construction, in a sharper form.

#### Scenario: The provenance of the prompt is declared
- **WHEN** the implementation is reported
- **THEN** it states that the classifier's prompt was written from the catalogue vocabularies and the corpus documentation
- **AND** it states that the annotations of the evaluation sets were not used to write it

### Requirement: The prompt version that adds the free-query task sections does not replace the previous one
The service SHALL introduce the free-query task sections in a new prompt version and MUST keep the previous version's file unchanged, so measurements taken against it stay interpretable. The reported prompt version MUST continue to be pinned to the file actually loaded.

#### Scenario: Both prompt versions exist and neither shadows the other
- **WHEN** the prompt files are inspected
- **THEN** the previous version's file is present and unmodified
- **AND** the reported prompt version matches the file that was loaded

## MODIFIED Requirements

### Requirement: Warnings are computed from rules and travel as a closed vocabulary of codes
Warnings SHALL be computed from data by deterministic rules and MUST NOT be produced by a model. Every warning emitted MUST belong to a closed vocabulary declared by this capability, and the service MUST NOT emit a warning in natural language: the wording for a human reader belongs to the presentation layer.

This capability SHALL emit **five** codes: the two that describe the piece — the product's family holds other members, and the product declares no size label — and the three this capability adds once it routes, which are the two distinct refusal reasons and the one stating that the corpus does not cover an anchored question.

The two refusal codes MUST remain distinct from each other. A trade this shop does not practise and a piece this shop does not carry are two different things for an operator to say to a customer, and one shared code would make the two rates this capability publishes separately indistinguishable where a consumer reads them.

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

#### Scenario: The two refusal codes are two and never one
- **WHEN** the closed vocabulary is inspected
- **THEN** the code for a query outside the domain differs from the code for a query this catalogue cannot stock
- **AND** both belong to the same declared vocabulary the rule-derived codes belong to

#### Scenario: No stock warning is emitted by this service
- **GIVEN** a product whose availability bucket at the requesting point of sale is zero
- **WHEN** the route is called anchored to that product
- **THEN** the warnings contain no code about critical stock and none about members out of stock

### Requirement: The provider is not called when there is nothing to write about
The service SHALL NOT call the language model provider when the abstention rule has decided that the catalogue cannot answer the query, when the router has refused the request, or when a clarification question has been emitted. Writing prose about an empty candidate set states something with confidence about nothing, which is the failure the abstention rule exists to prevent.

The free-query mode no longer withholds generation for want of a classification: the intent of such a query is now determined before retrieval, and the argument is written over a route that was decided rather than over a candidate set nobody classified. What remains forbidden is generating when there is nothing to write about — an abstention, a refusal or an unanswered question.

#### Scenario: An abstained request calls no provider
- **GIVEN** the abstention rule decided the catalogue cannot answer
- **WHEN** the assistance is served
- **THEN** the abstention is declared and no group is returned
- **AND** no language model generation call is made

#### Scenario: A refused request calls no generation provider
- **WHEN** the router refuses a free-text query
- **THEN** the generated argument is empty and the prompt version absent
- **AND** no language model generation call is made

#### Scenario: A clarified request calls no generation provider
- **WHEN** a clarification question is emitted for a free-text query
- **THEN** the generated argument is empty and the prompt version absent
- **AND** no language model generation call is made

## REMOVED Requirements

### Requirement: The detected intent is derived from the request shape and never guessed from words
**Reason**: This change delivers the classifier whose absence made the requirement true. The intent of a free-text query is now a routing verdict reached by reading the query, so the requirement's own name — "never guessed from words" — would be false as written, and a requirement that is false is worse than one that is missing. Its piece-anchored half is preserved verbatim in the requirement that replaces it, which keeps the anchored value unchanged and keeps the unclassified value as the honest report when no classification could be made.
**Migration**: Replaced by "The detected intent is a routing verdict in the free-query mode and remains structural in the anchored ones". Consumers reading the piece-anchored value need no change: that value and the conditions under which it is emitted are identical. Consumers that treated the unclassified value as "queries are never classified" must instead treat it as "this request was not classified", which is what the log distinguishes.
