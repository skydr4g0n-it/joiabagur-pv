import { describe, it, expect } from 'vitest';

import {
  CLOSED_VOCABULARIES,
  COLOR_TAG_OPTIONS,
  MATERIAL_OPTIONS,
  OCCASION_TAG_OPTIONS,
  PIECE_TYPE_OPTIONS,
  STONE_TYPE_OPTIONS,
  STYLE_TAG_OPTIONS,
  EXAMPLE_QUERIES,
  hasClosedVocabulary,
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

  it('should carry the thirty-three canonical stones when compared with the enrichment vocabulary', () => {
    expect(STONE_TYPE_OPTIONS).toHaveLength(33);
    expect(STONE_TYPE_OPTIONS.map((option) => option.value)).toEqual([
      'piedra', 'ambar', 'onix', 'perla', 'coral', 'turquesa', 'cuarzo', 'amatista', 'jade',
      'lapislazuli', 'citrino', 'granate', 'malaquita', 'nacar', 'howlita', 'aventurina',
      'obsidiana', 'hematites', 'ojo de tigre', 'piedra luna', 'labradorita', 'amazonita',
      'agata', 'jaspe', 'madreperla', 'circonita', 'diamante', 'zafiro', 'esmeralda', 'rubi',
      'topacio', 'opalo', 'calcedonia',
    ]);
  });

  it('should carry the canonical commercial tags when compared with the enrichment vocabulary', () => {
    expect(COLOR_TAG_OPTIONS.map((option) => option.value)).toEqual([
      'plateado', 'dorado', 'blanco', 'negro', 'azul', 'verde', 'rojo', 'rosa', 'beige', 'marron',
    ]);
    expect(STYLE_TAG_OPTIONS.map((option) => option.value)).toEqual([
      'clasico', 'moderno', 'minimalista', 'boho', 'marino', 'vintage', 'etnico', 'romantico',
    ]);
    expect(OCCASION_TAG_OPTIONS.map((option) => option.value)).toEqual([
      'diario', 'regalo', 'fiesta', 'boda', 'verano', 'ceremonia',
    ]);
  });

  it('should follow the vocabulary file about diacritics rather than tidying them', () => {
    // The YAML is **not uniform about this**, and the asymmetry has to be mirrored rather than
    // smoothed: `materials` keeps its diacritics in the canonical, every other closed vocabulary
    // strips them. The canonical travels to the index and is compared by exact equality, so
    // "correcting" either side of this — writing `bano de oro`, or writing `ámbar` — produces a
    // term that matches nothing and reports it as an empty result rather than as an error.
    expect(MATERIAL_OPTIONS.map((option) => option.value)).toContain('baño de oro');
    expect(MATERIAL_OPTIONS.map((option) => option.value)).toContain('latón');

    const unaccented = (value: string) => value.normalize('NFD').replace(/[̀-ͯ]/g, '');

    for (const [field, options] of Object.entries(CLOSED_VOCABULARIES)) {
      if (field === 'materials') continue;
      for (const option of options) {
        expect(option.value).toBe(unaccented(option.value));
      }
    }
  });

  it('should leave the size label out of the closed vocabularies', () => {
    // The one field the extractor produces from a deterministic rule — all 539 of them — and the
    // rule emits ring sizes and chain lengths the vocabulary never contained: the corpus carries
    // twenty distinct labels against twelve terms, the extra ones being `05`, `17`, `40`, `2mm`.
    // Offering a closed list there would make a size of 17 unrecordable.
    expect(hasClosedVocabulary('size_label')).toBe(false);
    expect(hasClosedVocabulary('materials')).toBe(true);
    expect(hasClosedVocabulary('piece_type')).toBe(true);
    expect(hasClosedVocabulary('stone_type')).toBe(true);
  });

  it('should give every option a label when rendered in the quick filters', () => {
    for (const options of Object.values(CLOSED_VOCABULARIES)) {
      for (const option of options) {
        expect(option.label.trim().length).toBeGreaterThan(0);
      }
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
