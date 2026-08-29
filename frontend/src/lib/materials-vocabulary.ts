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
] as const;

/** Example queries, so what the system can be asked is expressed by the interface. */
export const EXAMPLE_QUERIES: readonly string[] = [
  'un anillo de plata para regalar',
  'pendientes pequeños para el día a día',
  'algo azul para una boda',
  'collar de perlas clásico',
] as const;
