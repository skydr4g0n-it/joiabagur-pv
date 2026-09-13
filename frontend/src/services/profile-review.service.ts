/**
 * Profile review (EP13 / C28).
 *
 * The browser cannot reach jbg-ai — it is private by design and publishes no port — so the .NET
 * API serves everything here. Routes are relative: `VITE_API_BASE_URL` already carries `/api`.
 *
 * Reads return a **discriminated outcome** and writes throw, exactly as the family review service
 * does, and for the same reason: a queue that could not be computed is a *state of the review*
 * the screen has to keep showing, whereas a save that failed is an ordinary error the caller
 * must surface.
 */

import apiClient from './api.service';
import type {
  BulkApproveProfilesRequest,
  BulkApproveProfilesResult,
  EvidenceStratumCode,
  MetricsOutcome,
  ProfileReviewMetrics,
  ProfileReviewQueue,
  QueueOutcome,
  RecordProfileReviewRequest,
  RecordProfileReviewResult,
  RejectedOutcome,
  RejectedProfiles,
} from '@/types/profile-review.types';
import type { ApiError } from '@/types/api.types';

const QUEUE_ENDPOINT = '/ai/catalog/profile-review-queue';
const REVIEWS_ENDPOINT = '/ai/catalog/profile-reviews';
const BULK_ENDPOINT = '/ai/catalog/profile-reviews/bulk';
const REJECTED_ENDPOINT = '/ai/catalog/profile-reviews/rejected';
const RESTORE_ENDPOINT = '/ai/catalog/profile-reviews/restore';
const METRICS_ENDPOINT = '/ai/catalog/profile-review-metrics';

export interface QueueQuery {
  stratum?: EvidenceStratumCode;
  page?: number;
  pageSize?: number;
  seed?: string;
}

const reasonOf = (error: unknown, fallback: string): string =>
  (error as ApiError)?.message ?? fallback;

export const profileReviewService = {
  /**
   * Asks for the stratified batch, and reports **why** there is none when there is none.
   *
   * A caller cannot reach the items without passing through the state, which is what makes
   * showing an empty table in place of a failure awkward rather than merely discouraged.
   */
  getQueue: async (query: QueueQuery = {}, signal?: AbortSignal): Promise<QueueOutcome> => {
    try {
      const response = await apiClient.get<ProfileReviewQueue>(QUEUE_ENDPOINT, {
        params: query,
        signal,
      });
      return { state: 'loaded', queue: response.data };
    } catch (error) {
      return {
        state: 'unavailable',
        reason: reasonOf(error, 'No se ha podido calcular la cola de revisión.'),
      };
    }
  },

  /**
   * Records one judgement with the time it took.
   *
   * One request per item rather than a batch, unlike the family verdicts: the duration is a
   * property of *this* item and batching would either lose it or invite a shared one across the
   * batch — which is the shape that produces an average flattering the process.
   */
  recordReview: async (
    request: RecordProfileReviewRequest,
  ): Promise<RecordProfileReviewResult> => {
    const response = await apiClient.post<RecordProfileReviewResult>(REVIEWS_ENDPOINT, request);
    return response.data;
  },

  /**
   * Approves one field across many profiles of one stratum.
   *
   * The server refuses a selection that names more than one field or spans more than one
   * stratum. The screen declares both so the refusal is a confirmation of what the reviewer
   * asked for, not a discovery about what they happened to select.
   */
  bulkApprove: async (
    request: BulkApproveProfilesRequest,
  ): Promise<BulkApproveProfilesResult> => {
    const response = await apiClient.post<BulkApproveProfilesResult>(BULK_ENDPOINT, request);
    return response.data;
  },

  /** The rejected profiles, to be asked the inverted question. They consume no stratum quota. */
  getRejected: async (
    page = 1,
    pageSize = 50,
    signal?: AbortSignal,
  ): Promise<RejectedOutcome> => {
    try {
      const response = await apiClient.get<RejectedProfiles>(REJECTED_ENDPOINT, {
        params: { page, pageSize },
        signal,
      });
      return { state: 'loaded', rejected: response.data };
    } catch (error) {
      return {
        state: 'unavailable',
        reason: reasonOf(error, 'No se ha podido leer la lista de perfiles rechazados.'),
      };
    }
  },

  /** Returns a wrongly rejected profile to approved, with its reviewer recorded by the server. */
  restoreRejected: async (
    productId: string,
    reviewDurationMs?: number,
  ): Promise<RecordProfileReviewResult> => {
    const response = await apiClient.post<RecordProfileReviewResult>(RESTORE_ENDPOINT, {
      productId,
      reviewDurationMs: reviewDurationMs ?? null,
    });
    return response.data;
  },

  /**
   * The correction rate and the review times.
   *
   * Read from the server rather than tallied here: the rate is the difference between the raw
   * proposal and the values in force, and a figure kept in component state is gone the moment
   * the tab closes.
   */
  getMetrics: async (signal?: AbortSignal): Promise<MetricsOutcome> => {
    try {
      const response = await apiClient.get<ProfileReviewMetrics>(METRICS_ENDPOINT, { signal });
      return { state: 'loaded', metrics: response.data };
    } catch (error) {
      return {
        state: 'unavailable',
        reason: reasonOf(error, 'No se han podido calcular las métricas de revisión.'),
      };
    }
  },
};

export default profileReviewService;
