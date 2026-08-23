# catalog-enrichment-pipeline Specification

## Purpose
Real extractor behind `POST /v1/enrich/products` when `STUB_MODE` is off: closed vocabularies versioned in the repo, size regex on `Name` then `Description` (never the SKU), structured extraction via LiteLLM at temperature 0, confidence by evidence span in the input text, proposed profiles without title/description/family, and batch quality gates evaluated by an auditor outside the HTTP request. The C08 stub remains the handler when stub mode is on so committed contract tests stay green. The OpenAPI snapshot is not regenerated.

## Requirements

### Requirement: Real enrichment replaces the stub when stub mode is off
When `STUB_MODE` is disabled, `POST /v1/enrich/products` MUST run the catalog enrichment pipeline and MUST return one `ProposedProfile` per requested product. It MUST NOT return HTTP 501 naming a later change, MUST NOT return the deterministic stub cycle, and MUST NOT invent profiles when the RAG LLM key is missing. When `STUB_MODE` is enabled, the existing C08 stub MUST remain the handler so committed contract tests stay green. The OpenAPI snapshot MUST NOT be regenerated.

#### Scenario: Stub mode keeps the C08 fixture cycle
- **GIVEN** `STUB_MODE` is enabled
- **WHEN** an authenticated catalog client calls `POST /v1/enrich/products` with a valid batch
- **THEN** the response is produced by the existing enrichment stub
- **AND** `prompt_version` is the stub version
- **AND** no model provider is called

#### Scenario: Real mode produces extracted profiles
- **GIVEN** `STUB_MODE` is disabled and a RAG LLM key is configured
- **WHEN** an authenticated catalog client calls `POST /v1/enrich/products` with a valid batch
- **THEN** the response status is 200
- **AND** each profile is produced by the enrichment pipeline rather than the stub cycle
- **AND** `prompt_version` equals `enrichment/v1`
- **AND** `usage.model` identifies the configured provider model

#### Scenario: Real mode without a key fails explicitly
- **GIVEN** `STUB_MODE` is disabled and `JPV_RAG_LLM_API_KEY` is absent
- **WHEN** an authenticated catalog client calls `POST /v1/enrich/products`
- **THEN** the call fails with an explicit configuration error
- **AND** no proposed profile is invented
- **AND** the status is not 501 claiming the implementation has not arrived

#### Scenario: OpenAPI snapshot stays frozen
- **WHEN** `test_openapi_snapshot_is_stable` runs against this change
- **THEN** the live schema equals the committed `ai-service/openapi.json`
- **AND** the snapshot file has not been regenerated

### Requirement: Size is read from name then description and never from the SKU
A deterministic size normalizer MUST run before the model call. It MUST search `name` first and `description` second. A regex hit MUST set `size_label.source` to `rule` and `size_label.confidence` to `1.0`. The SKU MUST NOT be inspected for size. When name and description disagree, the name wins. Canonical tokens MUST include the C06a/C06b set (`xxs`…`xxl`, `mini`, `extramini`, S/M/L, mm/cm, ring sizes 5–48). The normalizer MUST be a pure function in `jbg_ai.enrichment` and MUST NOT import `jbg_ai.data`.

#### Scenario: Size on the name is marked rule
- **GIVEN** a product whose name is `Colgante erizo de mar S` and whose SKU is `SKU06`
- **WHEN** the size normalizer runs
- **THEN** `size_label.value` is the canonical size `S`
- **AND** `size_label.source` is `rule`
- **AND** `size_label.confidence` is `1.0`

#### Scenario: Name wins over a conflicting description
- **GIVEN** a product whose name contains `M` as a size token and whose description says size `L`
- **WHEN** the size normalizer runs
- **THEN** `size_label.value` is the canonical size from the name

#### Scenario: Description is used when the name has no size
- **GIVEN** a product whose name has no size token and whose description contains a size token
- **WHEN** the size normalizer runs
- **THEN** `size_label` is taken from the description
- **AND** `source` is `rule` when the regex hits

#### Scenario: Size is never read from the SKU
- **GIVEN** a product whose SKU contains a token that looks like a size and whose name and description do not
- **WHEN** the size normalizer runs
- **THEN** `size_label` is not populated from the SKU

### Requirement: Closed vocabularies reject unknown values and invent nothing
The pipeline MUST load closed vocabularies from versioned repository files, not from a PostgreSQL `ENUM`. Every persisted `piece_type`, `materials` entry, `stone_type`, `size_label` and commercial tag MUST be a canonical term from those files. Synonyms MUST be normalized in code before the value is proposed. A value outside the vocabulary MUST be discarded and MUST produce a warning; it MUST NOT be stored as a free string. `materials` MUST be an empty list when the input text names no vocabulary substance; the pipeline MUST NOT write a default material.

Canonical `piece_type` values are the hypernyms `anillo`, `pendientes`, `collar`, `pulsera`, `colgante`, `tobillera`, `broche` and `cadena`. Extraction synonyms (sortija/alianza → `anillo`, gargantilla → `collar`, brazalete/esclava → `pulsera`, criollas/aro → `pendientes`) MUST NOT be persisted. `colgante` MUST NOT collapse to `collar`. `style_tags` MUST NOT be used as a subtype taxonomy.

Canonical `materials` values are `plata`, `oro`, `baño de oro`, `hilo`, `latón`, `acero`, `resina`, `cuero` and `perla`. Synonyms include plata de ley / 925 / sterling → `plata`, 18k / 18kl → `oro`, and hilo encerado → `hilo`. `piedras preciosas`, ámbar and ónix MUST NOT be stored as materials.

#### Scenario: Several materials become a canonical list
- **GIVEN** input text that names `plata de ley` and `baño de oro`
- **WHEN** the pipeline proposes the profile
- **THEN** `materials.value` contains `plata` and `baño de oro`
- **AND** `materials.source` is `inferred`
- **AND** no value outside the closed materials vocabulary is present

#### Scenario: A material synonym is normalized and an invented value is rejected
- **GIVEN** one product whose text says `925` or `sterling`
- **AND** another product whose model output proposes `mithril`
- **WHEN** vocabulary validation runs
- **THEN** the first product stores `plata`
- **AND** `mithril` is not stored
- **AND** the second product has `materials` as `[]` or omits the rejected value, with a warning

#### Scenario: No material evidence yields an empty list
- **GIVEN** a name and description that mention no vocabulary substance
- **WHEN** the pipeline proposes the profile
- **THEN** `materials.value` is `[]`
- **AND** materials confidence is the absent-evidence value
- **AND** neither `plata` nor any other default material is written

#### Scenario: Piece type stores the hypernym
- **GIVEN** names `Gargantilla Horizonte Marfil`, `Brazalete suspiro` and `Anillo mini conchiglie`
- **WHEN** `piece_type` is extracted
- **THEN** the values are `collar`, `pulsera` and `anillo` respectively
- **AND** `gargantilla`, `brazalete` and `sortija` are not persisted as `piece_type`
- **AND** `style_tags` does not record those hyponyms as a subtype taxonomy

### Requirement: Stone type is a closed list with residual piedra
`stone_type` MUST be either a canonical type from the YAML, the residual `piedra`, or null. The YAML is closed for the model and expandable by a maintainer without a database migration. A specific type in the YAML MUST be stored as that type and MUST NOT also write `piedra`. When the text asserts a gem or setting without naming a listed type, or the model proposes a type outside the list, the value MUST be `piedra`. When the text does not assert a gem (for example it only mentions `relieve` or `brillo`), `stone_type` MUST be null. Free strings MUST never be stored. Ámbar and ónix belong here, not in `materials`. Pearl as a setting or as the body of the piece (`collar de perlas`) MUST go to `stone_type`; the chain metal MUST stay in `materials` and MUST NOT be duplicated.

#### Scenario: A generic gem mention stores residual piedra
- **GIVEN** a product whose text says it carries a precious stone without naming which
- **WHEN** the pipeline proposes the profile
- **THEN** `stone_type.value` is `piedra`
- **AND** `materials` contains only named substances

#### Scenario: A specific stone does not also write the residual
- **GIVEN** a product whose text names `ámbar`
- **WHEN** the pipeline proposes the profile
- **THEN** `stone_type.value` is the canonical `ambar`
- **AND** `stone_type` is not also `piedra`
- **AND** ámbar is not stored in `materials`

#### Scenario: An unlisted stone type becomes residual or null
- **GIVEN** a product whose text asserts a gem with a type that is not in the YAML
- **WHEN** the pipeline proposes the profile
- **THEN** `stone_type.value` is `piedra`
- **AND** the free string is not stored

#### Scenario: Ornament language without a gem leaves stone type null
- **GIVEN** copy that only mentions `relieve` or `brillo`
- **WHEN** the pipeline proposes the profile
- **THEN** `stone_type` is null

### Requirement: Confidence follows an evidence span, not the model score
Confidence MUST be assigned by a deterministic heuristic over the input text. A regex size hit MUST be `1.0`. A value whose canonical form or synonym appears as a span in `name` or `description` MUST be `0.85`. A value without a span MUST be `0.45`. An absent field or empty list MUST be `0.20`. The number a model emits MUST NOT be copied. For list fields the field confidence MUST be that of the least-evidenced member. The C08 tag auto-approval threshold of `0.80` MUST remain above the no-span value.

#### Scenario: A literal span scores above the C08 tag threshold
- **GIVEN** `plata` appears literally in the description
- **AND** an occasion tag is asserted without appearing in the text
- **WHEN** confidences are assigned
- **THEN** materials confidence is `0.85`
- **AND** the occasion tag confidence is `0.45`
- **AND** no model-emitted confidence is copied onto those fields

#### Scenario: Empty materials use the absent-evidence confidence
- **GIVEN** a profile whose `materials.value` is `[]`
- **WHEN** confidences are assigned
- **THEN** materials confidence is `0.20`
- **AND** `source` is `inferred`

#### Scenario: A mixed list uses the least-evidenced member confidence
- **GIVEN** a materials list with `plata` present as a span and `oro` asserted without appearing in the text
- **WHEN** confidences are assigned
- **THEN** materials confidence is `0.45`
- **AND** both canonical values remain in the list

### Requirement: Real profiles leave title, description and family null
The real extractor MUST set `title`, `description`, `family_id` and `variant_label` to null. It MUST NOT write any column of `Product`. The C08 stub MAY keep filling those fields when `STUB_MODE` is enabled.

#### Scenario: Real extractor omits copy and family
- **GIVEN** `STUB_MODE` is disabled and the pipeline produces a profile
- **WHEN** the response is read
- **THEN** `title`, `description`, `family_id` and `variant_label` are null
- **AND** no `Product` column is updated

### Requirement: Extraction uses a dedicated LiteLLM port with bounded concurrency
The runtime client MUST be a dedicated `EnrichLlm` port implemented with LiteLLM. It MUST NOT reuse `OpenAICatalogLlm`. Temperature MUST be `0`. The pipeline MUST make one model call per product. In-flight calls inside a batch of at most 50 MUST be capped by `JPV_RAG_LLM_CONCURRENCY` (default 8). A parse failure MAY be retried once; a second failure MUST raise rather than invent a profile. `litellm` MUST be pinned to an exact version in `pyproject.toml`. `jbg_ai.api.main` MUST NOT import `jbg_ai.data`. Unit tests MUST inject a fake port and MUST open no sockets to providers.

#### Scenario: The enrich client is LiteLLM, not the catalog generate client
- **WHEN** the real enrichment client is constructed
- **THEN** it implements `EnrichLlm` over LiteLLM
- **AND** it does not import or call `OpenAICatalogLlm`

#### Scenario: Concurrency caps in-flight calls
- **GIVEN** `JPV_RAG_LLM_CONCURRENCY` is 8 and a batch of 50 products
- **WHEN** the pipeline calls the model
- **THEN** at most 8 calls are in flight at once
- **AND** each product still produces its own model call

#### Scenario: The unit suite makes no provider calls
- **WHEN** `ai-service/tests/enrichment/` runs
- **THEN** every test uses a fake `EnrichLlm`
- **AND** no socket is opened to a model provider
- **AND** `jbg_ai.api.main` does not import `jbg_ai.data`

### Requirement: Batch quality gates are evaluated by an auditor, not by the HTTP POST
A pure auditor MUST evaluate uniqueness of SKU, closed-vocabulary membership, and tag coverage against a supplied text-quality stratum (from JSONL or a fixture). Tag coverage MUST count a product when at least one of `color_tags`, `style_tags` or `occasion_tags` is non-empty. Products with stratum `original` or `short` MAY have all three lists empty and MUST NOT count as failures in the global denominator. Products with stratum `sparse` MUST have at least one non-empty tag list. Coverage over the `ai_assisted` stratum MUST be at least 90 %. Global coverage MUST be at least 70 % excluding `original`/`short` from the failing set. `POST /v1/enrich/products` MUST NOT return HTTP 422 because of these figures.

#### Scenario: HTTP accepts empty tags on a batch of original products
- **GIVEN** an HTTP batch of products whose commercial tag lists are empty
- **WHEN** `POST /v1/enrich/products` is called
- **THEN** the response is 200 with honest empty lists
- **AND** the status is not 422

#### Scenario: The auditor measures tag coverage per text provenance
- **GIVEN** fixtures that carry `text_quality_tier` / `text_provenance` from the catalog JSONL
- **WHEN** the auditor runs
- **THEN** empty tag lists on `original` or `short` are accepted
- **AND** `sparse` requires at least one non-empty tag list
- **AND** the 90 % threshold is evaluated on the `ai_assisted` stratum
- **AND** the 70 % global threshold does not treat `original`/`short` as failures

#### Scenario: Coverage below threshold fails the auditor, not the POST
- **GIVEN** a fixture batch whose `ai_assisted` tag coverage is below 90 %
- **WHEN** the auditor runs
- **THEN** the auditor reports a failed gate
- **AND** that failure is not expressed as an HTTP status from `POST /v1/enrich/products`

#### Scenario: Duplicate SKUs fail the auditor
- **GIVEN** two audit records that share the same SKU
- **WHEN** the auditor runs
- **THEN** the auditor reports a failed uniqueness gate
- **AND** that failure is not expressed as an HTTP status from `POST /v1/enrich/products`
