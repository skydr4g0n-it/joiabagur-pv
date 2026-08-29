/**
 * Assisted Search Service Tests (EP14 / C16)
 *
 * The mapping of failures is the substance here. The panel has to say four different things when
 * a search produces nothing, and two of them are decided by the status code rather than by the
 * body — so a service that collapsed them into one thrown error would make the interface lie.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

import { aiSearchService } from './ai-search.service';
import apiClient from './api.service';
import type { AssistedSearchResponse } from '@/types/ai-search.types';

vi.mock('./api.service', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const response: AssistedSearchResponse = {
  results: [],
  searchEventId: '11111111-1111-1111-1111-111111111111',
  aiAvailable: true,
  lowConfidence: false,
  pointOfSaleId: '22222222-2222-2222-2222-222222222222',
  candidatesReturned: 0,
  survivedHydration: 0,
};

const request = {
  query: 'un anillo de plata para regalar',
  pointOfSaleId: '22222222-2222-2222-2222-222222222222',
};

describe('aiSearchService.search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should post to the relative ai search route when a search is issued', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: response });

    const outcome = await aiSearchService.search(request);

    // Relative on purpose: VITE_API_BASE_URL already carries `/api`, and duplicating it here is
    // the mistake this route has to be protected from.
    expect(apiClient.post).toHaveBeenCalledWith('/ai/search', request);
    expect(outcome).toEqual({ kind: 'ok', response });
  });

  it('should report a rate limit as its own outcome when the server answers 429', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ statusCode: 429, message: 'too many' });

    const outcome = await aiSearchService.search(request);

    // Not folded into a generic error: a caller must be able to tell "wait a few seconds" from
    // "the assisted search service is down", which have opposite remedies.
    expect(outcome).toEqual({ kind: 'rate-limited' });
  });

  it('should report a forbidden point of sale as its own outcome when the server answers 403', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ statusCode: 403, message: 'forbidden' });

    expect(await aiSearchService.search(request)).toEqual({ kind: 'forbidden' });
  });

  it('should surface the validation messages when the server answers 400 with an array', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      statusCode: 400,
      message: 'bad request',
      errors: ['La búsqueda requiere un texto.'],
    });

    expect(await aiSearchService.search(request)).toEqual({
      kind: 'invalid',
      errors: ['La búsqueda requiere un texto.'],
    });
  });

  it('should surface the validation messages when the server answers 400 with a field dictionary', async () => {
    // Most controllers answer with a field-keyed dictionary while the AI endpoints answer with a
    // plain array. Both shapes reach the client, so both are handled.
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      statusCode: 400,
      message: 'bad request',
      errors: { Query: ['La búsqueda requiere un texto.'] },
    });

    expect(await aiSearchService.search(request)).toEqual({
      kind: 'invalid',
      errors: ['La búsqueda requiere un texto.'],
    });
  });

  it('should fall back to the error message when a 400 carries no details', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ statusCode: 400, message: 'bad request' });

    expect(await aiSearchService.search(request)).toEqual({
      kind: 'invalid',
      errors: ['bad request'],
    });
  });

  it('should never throw when the transport fails', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ statusCode: 500, message: 'boom' });

    const outcome = await aiSearchService.search(request);

    expect(outcome).toEqual({ kind: 'error', message: 'boom' });
  });
});

describe('aiSearchService.reportSelection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should post the selected product to the event route when a result is selected', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: null });

    await aiSearchService.reportSelection('event-1', 'product-1');

    expect(apiClient.post).toHaveBeenCalledWith('/ai/search-events/event-1/selection', {
      productId: 'product-1',
    });
  });

  it('should resolve rather than reject when reporting the selection fails', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ statusCode: 404, message: 'gone' });

    // The caller does not await this in a click handler, so a rejection here would surface as an
    // unhandled promise rejection rather than as anything the operator could act on.
    await expect(aiSearchService.reportSelection('event-1', 'product-1')).resolves.toBeUndefined();
  });
});
