/**
 * Family review (EP13 / C18b).
 *
 * The browser cannot reach jbg-ai — it is private by design and publishes no port — so the .NET
 * API serves everything here. Routes are relative: `VITE_API_BASE_URL` already carries `/api`.
 *
 * Two operations read and two write, and the split is deliberate rather than tidy: `getAudit`
 * must never write, which is what lets the backend assert that auditing changed nothing.
 */

import apiClient from './api.service';
import type {
  AuditOutcome,
  FamilyAudit,
  FamilyListQuery,
  FamilyVerdict,
  PaginatedFamilies,
  RecordVerdictsResult,
} from '@/types/family-review.types';
import type { ApiError } from '@/types/api.types';

const AUDIT_ENDPOINT = '/ai/catalog/family-audit';
const VERDICTS_ENDPOINT = '/ai/catalog/family-verdicts';
const FAMILIES_ENDPOINT = '/product-families';

export const familyReviewService = {
  /**
   * Asks for the audit, and reports **why** there is none when there is none.
   *
   * Returns a discriminated outcome rather than throwing or returning an empty audit. On a screen
   * whose subject is catalogue quality, an empty result and a service that did not answer look
   * identical once the rows are drawn, and "nothing to review" reads as "nothing is wrong" — the
   * conclusion the review exists to establish with evidence rather than assert by accident. That
   * is exactly how the C17 risk materialised, and the type here is what makes repeating it
   * awkward: a caller cannot reach the lists without passing through the state.
   */
  getAudit: async (signal?: AbortSignal): Promise<AuditOutcome> => {
    try {
      const response = await apiClient.post<FamilyAudit>(AUDIT_ENDPOINT, {}, { signal });
      return { state: 'loaded', audit: response.data };
    } catch (error) {
      const apiError = error as ApiError;
      return {
        state: 'unavailable',
        reason:
          apiError?.message ??
          'El servicio de IA no respondió. No se ha podido calcular la auditoría.',
      };
    }
  },

  /**
   * Lists families. Throws on failure, unlike the audit.
   *
   * The difference is not an inconsistency: this reads the transactional database and its failure
   * is an ordinary error the caller should surface, whereas an unavailable audit is a *state of
   * the review* that the screen has to keep showing while the rest of it stays usable.
   */
  listFamilies: async (
    query: FamilyListQuery = {},
    signal?: AbortSignal,
  ): Promise<PaginatedFamilies> => {
    const response = await apiClient.get<PaginatedFamilies>(FAMILIES_ENDPOINT, {
      params: query,
      signal,
    });
    return response.data;
  },

  /**
   * Records what the reviewer decided about a batch of pairs.
   *
   * Batched rather than one call per row: a reviewer works through a queue, and a request per
   * judgement turns a session into hundreds of round trips. Idempotent per pair on the server —
   * judging the same pair again corrects the standing record instead of adding a second one.
   */
  recordVerdicts: async (verdicts: FamilyVerdict[]): Promise<RecordVerdictsResult> => {
    const response = await apiClient.post<RecordVerdictsResult>(VERDICTS_ENDPOINT, { verdicts });
    return response.data;
  },

  /**
   * Dissolves a family. Its members stop belonging to it and are free to be assigned elsewhere.
   *
   * Not the same as declaring an empty membership: an empty family is a legitimate state for one
   * being built and meaningless for one that was wrong, and the shell would come back in every
   * later listing as a row to decide about again.
   */
  dissolveFamily: async (familyId: string): Promise<void> => {
    await apiClient.delete(`${FAMILIES_ENDPOINT}/${familyId}`);
  },
};

export default familyReviewService;
