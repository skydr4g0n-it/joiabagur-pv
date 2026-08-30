/**
 * AI service status (EP11 / C17).
 *
 * One call. The browser cannot reach jbg-ai — it is private by design, publishes no port, and
 * the demo security group opens only the two the reverse proxy serves — so the .NET API proxies
 * its health report, for administrators only.
 *
 * Routes are relative: `VITE_API_BASE_URL` already carries `/api`.
 */

import apiClient from './api.service';
import type { AiHealthOutcome, AiHealthReport } from '@/types/ai-health.types';
import type { ApiError } from '@/types/api.types';

const HEALTH_ENDPOINT = '/ai/health';

export const aiHealthService = {
  /**
   * Reads the AI service status.
   *
   * **Never throws.** A failure here means the AI service did not answer, which is information
   * the card exists to show — not a reason to take the dashboard down with it. A 403 lands here
   * too, when a non-administrator's client asks for it, and produces the same neutral outcome:
   * saying "you are not allowed to see this" on a card that is not rendered for them either way
   * would only be noise.
   */
  getHealth: async (signal?: AbortSignal): Promise<AiHealthOutcome> => {
    try {
      const response = await apiClient.get<AiHealthReport>(HEALTH_ENDPOINT, { signal });
      return { kind: 'ok', report: response.data };
    } catch (error) {
      const apiError = error as ApiError;
      return {
        kind: 'unreachable',
        message: apiError?.message ?? 'El servicio de IA no responde.',
      };
    }
  },
};

export default aiHealthService;
