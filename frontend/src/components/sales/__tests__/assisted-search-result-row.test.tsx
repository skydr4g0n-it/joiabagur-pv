/**
 * Assisted search result row (EP14 / C21).
 *
 * The subject is the origin badge. Until C21 it was one decision taken once for the whole
 * response from `aiAvailable`, which was honest only while every result came from the same
 * branch. C21 fuses a vector branch and two lexical ones and serves the lexical branch alone
 * when the embedding provider fails, so a response-wide badge would print "semantic match"
 * over results no semantic search produced — claiming a capability that did not run.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import {
  AssistedSearchResultRow,
  originLabel,
  resultOrigin,
  searchOrigin,
} from '../assisted-search-result-row';
import type { AssistedSearchResult } from '@/types/ai-search.types';

function result(overrides: Partial<AssistedSearchResult> = {}): AssistedSearchResult {
  return {
    productId: 'prod-1',
    sku: 'SKU-001',
    name: 'Anillo de plata',
    price: 39.9,
    quantityAtPointOfSale: 3,
    hasStock: true,
    primaryPhotoUrl: null,
    collectionName: null,
    score: 0.8,
    matchReasons: ['vector'],
    materials: ['plata'],
    familyId: null,
    variantLabel: null,
    ...overrides,
  };
}

function renderRow(overrides: Partial<AssistedSearchResult> = {}) {
  render(<AssistedSearchResultRow result={result(overrides)} onSelect={vi.fn()} />);
  return screen.getByTestId('assisted-search-result');
}

describe('AssistedSearchResultRow origin badge', () => {
  it('should show the lexical origin badge when a result has no vector provenance', () => {
    const row = renderRow({ matchReasons: ['lexical'] });

    expect(within(row).getByText('Búsqueda por texto')).toBeInTheDocument();
    expect(within(row).queryByText('Coincidencia semántica')).not.toBeInTheDocument();
  });

  it('should show the assisted badge when the result came from both branches', () => {
    const row = renderRow({ matchReasons: ['vector', 'lexical'] });

    expect(within(row).getByText('Coincidencia semántica')).toBeInTheDocument();
  });

  it('should decide per result, so one list can carry both origins', () => {
    render(
      <>
        <AssistedSearchResultRow
          result={result({ productId: 'a', sku: 'SKU-A', matchReasons: ['vector'] })}
          onSelect={vi.fn()}
        />
        <AssistedSearchResultRow
          result={result({ productId: 'b', sku: 'SKU-B', matchReasons: ['lexical'] })}
          onSelect={vi.fn()}
        />
      </>,
    );

    const [first, second] = screen.getAllByTestId('assisted-search-result');
    expect(within(first).getByText('Coincidencia semántica')).toBeInTheDocument();
    expect(within(second).getByText('Búsqueda por texto')).toBeInTheDocument();
  });

  it('should fall back to a neutral label for an origin it does not know', () => {
    const row = renderRow({ matchReasons: ['business_signal'] });

    expect(within(row).getByText('Resultado')).toBeInTheDocument();
    expect(within(row).getByText('SKU-001')).toBeInTheDocument();
  });

  it('should call the degraded path a text search when no retriever reported itself', () => {
    const row = renderRow({ matchReasons: [] });

    expect(within(row).getByText('Búsqueda por texto')).toBeInTheDocument();
  });

  it('should not render the raw match reasons', () => {
    const row = renderRow({ matchReasons: ['vector', 'lexical'] });

    expect(within(row).queryByText(/vector/i)).not.toBeInTheDocument();
    expect(within(row).queryByText(/^lexical$/i)).not.toBeInTheDocument();
  });

  it('should display the materials the retriever recognised', () => {
    const row = renderRow({ materials: ['plata', 'nacar'] });

    expect(within(row).getByText('plata')).toBeInTheDocument();
    expect(within(row).getByText('nacar')).toBeInTheDocument();
  });

  it('should leave no gap when the variant label is absent', () => {
    const row = renderRow({ variantLabel: null });

    expect(within(row).queryByText(/^Talla/)).not.toBeInTheDocument();
  });

  it('should show the size when the variant label is present', () => {
    const row = renderRow({ variantLabel: '16' });

    expect(within(row).getByText('Talla 16')).toBeInTheDocument();
  });
});

describe('resultOrigin', () => {
  it('should map provenance to the origin the operator reads', () => {
    expect(resultOrigin(['vector'])).toBe('assisted');
    expect(resultOrigin(['lexical', 'vector'])).toBe('assisted');
    expect(resultOrigin(['lexical'])).toBe('lexical');
    expect(resultOrigin([])).toBe('lexical');
    expect(originLabel(resultOrigin(['whatever']))).toBe('Resultado');
  });
});

describe('searchOrigin', () => {
  const withReasons = (...reasons: string[][]) =>
    reasons.map((matchReasons) => ({ matchReasons }));

  it('should report the assisted mode when any result came from the semantic branch', () => {
    expect(searchOrigin(withReasons(['lexical'], ['vector', 'lexical']), true)).toBe('assisted');
  });

  it('should report the service text search when nothing came from the semantic branch', () => {
    expect(searchOrigin(withReasons(['lexical'], ['lexical']), true)).toBe('service-lexical');
  });

  it('should report the legacy text search when the assisted path did not serve', () => {
    expect(searchOrigin(withReasons(['vector']), false)).toBe('legacy-lexical');
    expect(searchOrigin([], false)).toBe('legacy-lexical');
  });

  it('should claim nothing about the mode when there are no results to read', () => {
    expect(searchOrigin([], true)).toBe('unknown');
  });
});
