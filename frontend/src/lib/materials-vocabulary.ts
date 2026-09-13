/**
 * Closed material vocabulary of the catalog enrichment pipeline.
 *
 * Mirror of `materials.terms` in
 * `ai-service/src/jbg_ai/enrichment/vocabularies.yaml`. It is replicated here rather than
 * fetched because it is a *closed* vocabulary of nine terms that only changes when that file
 * changes — a deliberate act in another service — and an endpoint returning it would duplicate
 * the list anyway, in .NET configuration, plus a round trip when the panel opens.
 *
 * The failure mode of replicating it is silent: a term that drifts out of sync with the index
 * does not raise an error, it simply matches nothing. `materials-vocabulary.test.ts` pins the
 * list for exactly that reason.
 *
 * A better answer exists and is deliberately deferred to C28: an endpoint aggregating the
 * materials actually present in a given point of sale's assortment would never offer a filter
 * that returns zero.
 */

export interface MaterialOption {
  /** Canonical term. This is what travels to the retriever. */
  value: string;
  /** What the operator reads. */
  label: string;
}

export const MATERIAL_OPTIONS: readonly MaterialOption[] = [
  { value: 'plata', label: 'Plata' },
  { value: 'oro', label: 'Oro' },
  { value: 'baño de oro', label: 'Baño de oro' },
  { value: 'hilo', label: 'Hilo' },
  { value: 'latón', label: 'Latón' },
  { value: 'acero', label: 'Acero' },
  { value: 'resina', label: 'Resina' },
  { value: 'cuero', label: 'Cuero' },
  { value: 'perla', label: 'Perla' },
] as const;

/**
 * Piece categories, mirroring `piece_type.terms` of the same file. The retriever matches this
 * one by equality, so a single value rather than a multi-selection.
 *
 * The `value` must be byte-for-byte the canonical of the YAML, because it travels to
 * `AND d.piece_type = :category` and is compared by exact equality. The accent lives only in
 * the `label`: `cinturon` is unaccented as a canonical, «Cinturón» is what the operator reads.
 */
export const PIECE_TYPE_OPTIONS: readonly MaterialOption[] = [
  { value: 'anillo', label: 'Anillo' },
  { value: 'pendientes', label: 'Pendientes' },
  { value: 'collar', label: 'Collar' },
  { value: 'pulsera', label: 'Pulsera' },
  { value: 'colgante', label: 'Colgante' },
  { value: 'tobillera', label: 'Tobillera' },
  { value: 'broche', label: 'Broche' },
  { value: 'cadena', label: 'Cadena' },
  { value: 'diadema', label: 'Diadema' },
  { value: 'gemelos', label: 'Gemelos' },
  { value: 'cinturon', label: 'Cinturón' },
  { value: 'llavero', label: 'Llavero' },
] as const;

/**
 * Stones, mirroring `stone_type.terms`.
 *
 * Not a retrieval filter — no query reads it, so a value outside this list is still reachable
 * through the embedding. It is offered as a closed list for the other reason: an addition the
 * vocabulary does not contain would be counted as a correction of the extractor, when the
 * extractor could not have produced it. The stone is sensitive and enters the evidence stratum,
 * so its correction rate is one of the figures the delivery cites.
 *
 * The `value` is the canonical of the YAML, unaccented; the accent lives only in the `label`.
 */
export const STONE_TYPE_OPTIONS: readonly MaterialOption[] = [
  { value: 'piedra', label: 'Piedra (genérica)' },
  { value: 'ambar', label: 'Ámbar' },
  { value: 'onix', label: 'Ónix' },
  { value: 'perla', label: 'Perla' },
  { value: 'coral', label: 'Coral' },
  { value: 'turquesa', label: 'Turquesa' },
  { value: 'cuarzo', label: 'Cuarzo' },
  { value: 'amatista', label: 'Amatista' },
  { value: 'jade', label: 'Jade' },
  { value: 'lapislazuli', label: 'Lapislázuli' },
  { value: 'citrino', label: 'Citrino' },
  { value: 'granate', label: 'Granate' },
  { value: 'malaquita', label: 'Malaquita' },
  { value: 'nacar', label: 'Nácar' },
  { value: 'howlita', label: 'Howlita' },
  { value: 'aventurina', label: 'Aventurina' },
  { value: 'obsidiana', label: 'Obsidiana' },
  { value: 'hematites', label: 'Hematites' },
  { value: 'ojo de tigre', label: 'Ojo de tigre' },
  { value: 'piedra luna', label: 'Piedra luna' },
  { value: 'labradorita', label: 'Labradorita' },
  { value: 'amazonita', label: 'Amazonita' },
  { value: 'agata', label: 'Ágata' },
  { value: 'jaspe', label: 'Jaspe' },
  { value: 'madreperla', label: 'Madreperla' },
  { value: 'circonita', label: 'Circonita' },
  { value: 'diamante', label: 'Diamante' },
  { value: 'zafiro', label: 'Zafiro' },
  { value: 'esmeralda', label: 'Esmeralda' },
  { value: 'rubi', label: 'Rubí' },
  { value: 'topacio', label: 'Topacio' },
  { value: 'opalo', label: 'Ópalo' },
  { value: 'calcedonia', label: 'Calcedonia' },
] as const;

/** Colours, mirroring `color_tags.terms`. Commercial: an error costs ranking, not a bad sale. */
export const COLOR_TAG_OPTIONS: readonly MaterialOption[] = [
  { value: 'plateado', label: 'Plateado' },
  { value: 'dorado', label: 'Dorado' },
  { value: 'blanco', label: 'Blanco' },
  { value: 'negro', label: 'Negro' },
  { value: 'azul', label: 'Azul' },
  { value: 'verde', label: 'Verde' },
  { value: 'rojo', label: 'Rojo' },
  { value: 'rosa', label: 'Rosa' },
  { value: 'beige', label: 'Beige' },
  { value: 'marron', label: 'Marrón' },
] as const;

/** Styles, mirroring `style_tags.terms`. */
export const STYLE_TAG_OPTIONS: readonly MaterialOption[] = [
  { value: 'clasico', label: 'Clásico' },
  { value: 'moderno', label: 'Moderno' },
  { value: 'minimalista', label: 'Minimalista' },
  { value: 'boho', label: 'Boho' },
  { value: 'marino', label: 'Marino' },
  { value: 'vintage', label: 'Vintage' },
  { value: 'etnico', label: 'Étnico' },
  { value: 'romantico', label: 'Romántico' },
] as const;

/** Occasions, mirroring `occasion_tags.terms`. */
export const OCCASION_TAG_OPTIONS: readonly MaterialOption[] = [
  { value: 'diario', label: 'Diario' },
  { value: 'regalo', label: 'Regalo' },
  { value: 'fiesta', label: 'Fiesta' },
  { value: 'boda', label: 'Boda' },
  { value: 'verano', label: 'Verano' },
  { value: 'ceremonia', label: 'Ceremonia' },
] as const;

/**
 * The closed vocabulary of each enriched field, keyed as the provenance documents key it.
 *
 * <strong>`size_label` is deliberately absent, and its absence is the point.</strong> It is the
 * only field the extractor produces from a deterministic rule — all 539 of them — and the rule
 * emits ring sizes and chain lengths the vocabulary never contained: the corpus carries twenty
 * distinct size labels against twelve terms, the extra ones being `05`, `17`, `40`, `2mm` and
 * the like. Offering a closed list there would make a size of 17 unrecordable, so that field
 * stays free text.
 */
export const CLOSED_VOCABULARIES: Readonly<Record<string, readonly MaterialOption[]>> = {
  piece_type: PIECE_TYPE_OPTIONS,
  materials: MATERIAL_OPTIONS,
  stone_type: STONE_TYPE_OPTIONS,
  color_tags: COLOR_TAG_OPTIONS,
  style_tags: STYLE_TAG_OPTIONS,
  occasion_tags: OCCASION_TAG_OPTIONS,
};

/** Whether a field is governed by a closed vocabulary, and therefore offered as a list. */
export const hasClosedVocabulary = (field: string): boolean => field in CLOSED_VOCABULARIES;

/** Example queries, so what the system can be asked is expressed by the interface. */
export const EXAMPLE_QUERIES: readonly string[] = [
  'un anillo de plata para regalar',
  'pendientes pequeños para el día a día',
  'algo azul para una boda',
  'collar de perlas clásico',
] as const;
