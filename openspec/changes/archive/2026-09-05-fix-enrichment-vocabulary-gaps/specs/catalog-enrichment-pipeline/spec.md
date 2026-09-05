## MODIFIED Requirements

### Requirement: Real enrichment replaces the stub when stub mode is off
When `STUB_MODE` is disabled, `POST /v1/enrich/products` MUST run the catalog enrichment pipeline and MUST return one `ProposedProfile` per requested product. It MUST NOT return HTTP 501 naming a later change, MUST NOT return the deterministic stub cycle, and MUST NOT invent profiles when the RAG LLM key is missing. When `STUB_MODE` is enabled, the existing C08 stub MUST remain the handler so committed contract tests stay green. The OpenAPI snapshot MUST NOT be regenerated.

The prompt file the pipeline loads MUST be derived from the declared prompt version rather than named independently, so the two cannot diverge. The loaded prompt MUST identify itself as that version in its heading. The prompt file of a previous version MUST remain in the repository unmodified, because profiles produced by it continue to declare its version and that declaration MUST stay verifiable.

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
- **AND** `prompt_version` equals `enrichment/v2`
- **AND** `usage.model` identifies the configured provider model

#### Scenario: The prompt version cannot disagree with the prompt that was sent
- **WHEN** the pipeline loads its extraction prompt
- **THEN** the file path is derived from the declared prompt version
- **AND** the first heading of the loaded file names that same version
- **AND** the prompt file of the previous version is still present and unmodified

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

### Requirement: Closed vocabularies reject unknown values and invent nothing
The pipeline MUST load closed vocabularies from versioned repository files, not from a PostgreSQL `ENUM`. Every persisted `piece_type`, `materials` entry, `stone_type`, `size_label` and commercial tag MUST be a canonical term from those files. Synonyms MUST be normalized in code before the value is proposed. A value outside the vocabulary MUST be discarded and MUST produce a warning; it MUST NOT be stored as a free string. `materials` MUST be an empty list when the input text names no vocabulary substance; the pipeline MUST NOT write a default material.

Canonical `piece_type` values are the hypernyms `anillo`, `pendientes`, `collar`, `pulsera`, `colgante`, `tobillera`, `broche`, `cadena`, `diadema`, `gemelos`, `cinturon` and `llavero`. `gemelos` is canonical in the plural, as `pendientes` is, because the piece is a pair. `cinturon` is canonical without its accent, because the canonical term is compared by exact equality when a person selects it as a filter. Extraction synonyms (sortija/alianza → `anillo`, gargantilla → `collar`, brazalete/esclava → `pulsera`, criollas/aro → `pendientes`) MUST NOT be persisted. `colgante` MUST NOT collapse to `collar`. `style_tags` MUST NOT be used as a subtype taxonomy.

A proper name that contains a piece type MUST NOT override the head noun of the product name: the piece type is what the product *is*, not what its name mentions.

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

#### Scenario: The widened vocabulary names the pieces the eight hypernyms could not
- **GIVEN** names `Diadema Luz de Luna`, `Gemelos Hércules`, `Llavero Cala Galdana` and `Cinturón Ola Dorada`
- **WHEN** `piece_type` is extracted
- **THEN** the values are `diadema`, `gemelos`, `llavero` and `cinturon` respectively
- **AND** none of them is stored as `broche`, `collar` or `colgante`
- **AND** the canonical value carries no accent where the vocabulary declares it unaccented

#### Scenario: A proper name containing a piece type does not beat the head noun
- **GIVEN** names `Broche Cinturón de Orión` and `Anillo Cinturón de Orión`, where `Cinturón de Orión` is a constellation
- **WHEN** `piece_type` is extracted with `cinturon` present in the closed vocabulary
- **THEN** the values are `broche` and `anillo` respectively
- **AND** neither is stored as `cinturon`

## ADDED Requirements

### Requirement: Rows that are not finished jewellery get a null piece type
The extraction prompt MUST state that the catalogue may contain entries that are not finished jewellery — services, consumables and gift articles among them — and that for those entries `piece_type` is null. The pipeline MUST NOT store the most plausible hypernym for such a row, and MUST NOT invent a vocabulary term to represent "this is not a piece": the absence of a type is expressed by null.

A product whose text carries no evidence of any canonical piece type MUST keep `piece_type` null. Null MUST NOT be treated as a failure of extraction when no canonical term applies.

#### Scenario: A service is not given a piece type
- **GIVEN** a catalogue row naming a service or a repair rather than a piece, for example `Arreglos oro`
- **WHEN** the pipeline proposes the profile
- **THEN** `piece_type` is null
- **AND** no hypernym of the closed vocabulary is stored for it

#### Scenario: A jewel the vocabulary cannot name keeps a null type
- **GIVEN** a product whose name and description carry no evidence of any canonical piece type, for example `Joya del Zodiaco` with an empty description
- **WHEN** the pipeline proposes the profile
- **THEN** `piece_type` is null
- **AND** that null is the correct outcome rather than a rejected extraction
