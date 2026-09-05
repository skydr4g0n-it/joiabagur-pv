import { describe, it, expect } from 'vitest';

import {
  MATERIAL_OPTIONS,
  PIECE_TYPE_OPTIONS,
  EXAMPLE_QUERIES,
} from './materials-vocabulary';

/**
 * Pins the replicated vocabulary against its source of truth,
 * `ai-service/src/jbg_ai/enrichment/vocabularies.yaml`.
 *
 * Without this the drift is invisible: a canonical term that stops matching the index raises no
 * error at runtime, it just returns an empty result list for that filter — which the panel would
 * then present as "nothing of this in your shop", a sentence that would be false.
 */
describe('materials vocabulary', () => {
  it('should carry the nine canonical material terms when compared with the enrichment vocabulary', () => {
    expect(MATERIAL_OPTIONS.map((option) => option.value)).toEqual([
      'plata',
      'oro',
      'baño de oro',
      'hilo',
      'latón',
      'acero',
      'resina',
      'cuero',
      'perla',
    ]);
  });

  it('should carry the twelve canonical piece types when compared with the enrichment vocabulary', () => {
    expect(PIECE_TYPE_OPTIONS.map((option) => option.value)).toEqual([
      'anillo',
      'pendientes',
      'collar',
      'pulsera',
      'colgante',
      'tobillera',
      'broche',
      'cadena',
      'diadema',
      'gemelos',
      'cinturon',
      'llavero',
    ]);
  });

  it('should keep the canonical unaccented and the accent in the label when the two differ', () => {
    // The value is compared by exact equality against `piece_type` in the index, so an
    // accented `cinturón` here would silently match nothing. The accent belongs to the label.
    const belt = PIECE_TYPE_OPTIONS.find((option) => option.label === 'Cinturón');
    expect(belt?.value).toBe('cinturon');
    for (const option of PIECE_TYPE_OPTIONS) {
      expect(option.value).toBe(option.value.normalize('NFD').replace(/[̀-ͯ]/g, ''));
    }
  });

  it('should give every option a label when rendered in the quick filters', () => {
    for (const option of [...MATERIAL_OPTIONS, ...PIECE_TYPE_OPTIONS]) {
      expect(option.label.trim().length).toBeGreaterThan(0);
    }
  });

  it('should offer example queries in natural language when the panel opens', () => {
    expect(EXAMPLE_QUERIES.length).toBeGreaterThanOrEqual(3);
    // Natural language, not SKUs: the point is to teach what the system can be asked, and a
    // one-word example would teach the opposite of what assisted search is for.
    for (const query of EXAMPLE_QUERIES) {
      expect(query.trim().split(/\s+/).length).toBeGreaterThanOrEqual(3);
    }
  });
});
