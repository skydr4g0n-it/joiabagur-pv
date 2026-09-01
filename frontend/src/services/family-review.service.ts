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
  FamilyDetail,
  FamilyListQuery,
  FamilyReviewMetrics,
  FamilyVerdict,
  PaginatedFamilies,
  RecordedVerdict,
  RecordVerdictsResult,
} from '@/types/family-review.types';
import type { ApiError } from '@/types/api.types';

const AUDIT_ENDPOINT = '/ai/catalog/family-audit';
const VERDICTS_ENDPOINT = '/ai/catalog/family-verdicts';
const FAMILIES_ENDPOINT = '/product-families';
const METRICS_ENDPOINT = '/ai/catalog/family-review-metrics';

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
   * Lists the judgements already recorded, each with the change it still implies.
   *
   * The audit cannot show these: it omits judged pairs on purpose, which is what makes a dismissal
   * stick. Without this read a decision nobody acted on disappears from every list and looks like
   * work already finished.
   */
  listVerdicts: async (signal?: AbortSignal): Promise<RecordedVerdict[]> => {
    const response = await apiClient.get<RecordedVerdict[]>(VERDICTS_ENDPOINT, { signal });
    return response.data;
  },

  /**
   * Enacts one judgement: adds the product to the family, or removes it.
   *
   * **Read, modify, declare.** Membership is replaced as a whole list rather than patched, which
   * is C07's contract and not a choice here: the position of every member comes from its place in
   * the declared list, so gaps and duplicates cannot be expressed. That also means this has to
   * fetch the family first — sending a partial list would silently remove everybody else.
   *
   * Going through the family endpoint rather than a new one is what keeps the index watermark
   * coherent: that service stamps the products entering and leaving, and without the stamp an
   * incremental pull never emits them.
   */
  applyVerdict: async (
    verdict: RecordedVerdict,
    variantLabel?: string | null,
  ): Promise<void> => {
    const family = (
      await apiClient.get<FamilyDetail>(`${FAMILIES_ENDPOINT}/${verdict.familyId}`)
    ).data;

    const current = family.members.map((member) => ({
      productId: member.productId,
      variantLabel: member.variantLabel,
    }));

    const members =
      verdict.pendingAction === 'remove'
        ? current.filter((member) => member.productId !== verdict.productId)
        : [
            ...current,
            {
              productId: verdict.productId,
              // Blank means the base piece, which is a legitimate variant value. It is only
              // rejected downstream when the family already has one, and the uniqueness index is
              // the right place for that answer rather than a guess here.
              variantLabel: variantLabel?.trim() ? variantLabel.trim() : null,
            },
          ];

    await apiClient.put(`${FAMILIES_ENDPOINT}/${verdict.familyId}/members`, { members });
  },

  /**
   * The human-review figures the delivery checklist asks for.
   *
   * Read from the server rather than tallied here: an average kept in component state is gone the
   * moment the tab closes, which is how the first review session's timings were lost.
   */
  getMetrics: async (signal?: AbortSignal): Promise<FamilyReviewMetrics> => {
    const response = await apiClient.get<FamilyReviewMetrics>(METRICS_ENDPOINT, { signal });
    return response.data;
  },

  /** Reads one family with its members, so a label can be corrected in place. */
  getFamily: async (familyId: string, signal?: AbortSignal): Promise<FamilyDetail> => {
    const response = await apiClient.get<FamilyDetail>(`${FAMILIES_ENDPOINT}/${familyId}`, {
      signal,
    });
    return response.data;
  },

  /**
   * Rewrites one member's variant label, leaving the rest of the family alone.
   *
   * A label is a property of the membership, so correcting it is a membership declaration — the
   * whole list again, with one entry changed. There is no narrower endpoint and there should not
   * be: a partial declaration cannot express positions, which is exactly what C07's contract
   * exists to prevent.
   */
  relabelMember: async (
    familyId: string,
    productId: string,
    variantLabel: string | null,
  ): Promise<void> => {
    const family = (await apiClient.get<FamilyDetail>(`${FAMILIES_ENDPOINT}/${familyId}`)).data;

    const members = family.members.map((member) => ({
      productId: member.productId,
      variantLabel:
        member.productId === productId
          ? variantLabel?.trim()
            ? variantLabel.trim()
            : null
          : member.variantLabel,
    }));

    await apiClient.put(`${FAMILIES_ENDPOINT}/${familyId}/members`, { members });
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
