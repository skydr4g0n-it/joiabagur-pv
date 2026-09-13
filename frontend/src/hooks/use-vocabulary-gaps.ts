/**
 * The vocabulary gaps a review session uncovers (EP13 / C28).
 *
 * A gap is **not a correction**. When the source text names a material the closed vocabulary
 * does not contain, the extractor did not fail — it could not have produced that term at all.
 * Counting it as an addition would report the vocabulary's coverage as the extractor's error
 * rate, merging two defects whose remedies are different: widening a list, and tightening a
 * prompt. So gaps are collected here, reported separately, and never reach the metric.
 *
 * **Why they are not persisted server-side.** Widening the vocabulary cannot happen in this
 * change and the reason is measurable rather than procedural: the confidence of a field is
 * computed from whether its vocabulary phrase appears in the text, so adding a term moves
 * products between evidence strata — up to twenty-four of them for `platino` and `cobre`, out of
 * a stratum holding a hundred and twenty-two. The batch would stop being the batch a published
 * figure was drawn from. A gap is therefore an input to a *later* change, exactly as C18a's
 * `FIX1` was, and a session-scoped list that can be exported is all that input needs. A table
 * for it would mean a migration this capability was designed not to need.
 *
 * Kept in `localStorage` so a closed tab does not lose an hour of findings. Every access is
 * guarded: a private window, cleared site data or a browser refusing storage must leave the
 * review working, because the gap list is a by-product and the judgements are the point.
 */

import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'c28-vocabulary-gaps';

export interface VocabularyGap {
  /** Field whose vocabulary lacks the term. */
  field: string;
  /** The term the source text names. */
  term: string;
  /** The product that revealed it. */
  sku: string;
  /** When it was recorded, ISO-8601. */
  recordedAt: string;
}

function read(): VocabularyGap[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as VocabularyGap[]) : [];
  } catch {
    return [];
  }
}

function write(gaps: VocabularyGap[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(gaps));
  } catch {
    // A browser refusing storage must not interrupt a review session. The list stays in
    // component state for this tab, which is strictly better than losing the judgement.
  }
}

export interface VocabularyGapRegistry {
  gaps: VocabularyGap[];
  record: (field: string, term: string, sku: string) => void;
  remove: (index: number) => void;
  clear: () => void;
  /** The findings as a table, ready to paste into the implementation report. */
  asMarkdown: () => string;
}

export function useVocabularyGaps(): VocabularyGapRegistry {
  const [gaps, setGaps] = useState<VocabularyGap[]>([]);

  useEffect(() => setGaps(read()), []);

  const persist = useCallback((next: VocabularyGap[]) => {
    setGaps(next);
    write(next);
  }, []);

  const record = useCallback(
    (field: string, term: string, sku: string) => {
      const clean = term.trim().toLowerCase();
      if (!clean) return;

      setGaps((current) => {
        // The same term from the same field twice is one finding with two witnesses, not two
        // findings. The second SKU is still worth keeping: a term that shows up once may be a
        // one-off, and one that shows up thirty times is a gap in the list.
        const already = current.some(
          (gap) => gap.field === field && gap.term === clean && gap.sku === sku,
        );
        if (already) return current;

        const next = [
          ...current,
          { field, term: clean, sku, recordedAt: new Date().toISOString() },
        ];
        write(next);
        return next;
      });
    },
    [],
  );

  const remove = useCallback(
    (index: number) => persist(gaps.filter((_, position) => position !== index)),
    [gaps, persist],
  );

  const clear = useCallback(() => persist([]), [persist]);

  const asMarkdown = useCallback(() => {
    if (gaps.length === 0) return 'Ningún hueco de vocabulario registrado.';

    const byTerm = new Map<string, { field: string; term: string; skus: string[] }>();
    for (const gap of gaps) {
      const key = `${gap.field}:${gap.term}`;
      const found = byTerm.get(key);
      if (found) {
        found.skus.push(gap.sku);
      } else {
        byTerm.set(key, { field: gap.field, term: gap.term, skus: [gap.sku] });
      }
    }

    const rows = [...byTerm.values()]
      .sort((a, b) => b.skus.length - a.skus.length)
      .map((row) => `| \`${row.field}\` | \`${row.term}\` | ${row.skus.length} | ${row.skus.join(', ')} |`);

    return [
      '| campo | término ausente | productos | SKU |',
      '|---|---|---:|---|',
      ...rows,
    ].join('\n');
  }, [gaps]);

  return { gaps, record, remove, clear, asMarkdown };
}

export default useVocabularyGaps;
