/**
 * Types for the jbg-ai status card on the administrator dashboard (EP11 / C17).
 *
 * The browser cannot ask the AI service directly — it is private by design and publishes no
 * port — so this is the shape the .NET API serves on from `GET /api/ai/health`.
 *
 * Every value here is a state, never a secret: no connection string, no database hostname, no
 * fragment of a credential. `provider` in particular reports whether the embedding key is
 * *configured*, never whether the provider is reachable, which nothing in this system asks.
 */

/** `ok` when the AI service can reach its database; `not_configured` when it has none. */
export type AiHealthDatabaseStatus = 'ok' | 'unavailable' | 'not_configured';

/**
 * `model_mismatch` is the condition worth reading carefully: the service is configured to embed
 * queries with a model other than the one that produced the indexed vectors. Two vector spaces
 * are being compared as if they were one, and the result is noise returned with a 200.
 */
export type AiHealthIndexStatus = 'ok' | 'model_mismatch' | 'unavailable';

/** Presence of the credential. Never its value, and never provider reachability. */
export type AiHealthProviderStatus = 'configured' | 'missing';

export interface AiHealthIndex {
  /** Documents currently indexed. Zero means an empty environment, not a broken one. */
  documents: number;
  /** Model recorded on the index rows, or null when the index is empty. */
  model: string | null;
  /** Model the service is configured to query with. */
  configuredModel: string | null;
  status: AiHealthIndexStatus;
}

export interface AiHealthReport {
  status: 'OK' | 'degraded' | string;
  version: string;
  database: AiHealthDatabaseStatus | string;
  index: AiHealthIndex;
  provider: AiHealthProviderStatus | string;
}

/**
 * What the card renders.
 *
 * `unreachable` is a first-class outcome rather than a thrown error: the AI service being down
 * must show as a line on one card, never as a failed dashboard. Everything else on that page —
 * sales, revenue, stock — has nothing to do with the AI and must keep rendering.
 */
export type AiHealthOutcome =
  | { kind: 'ok'; report: AiHealthReport }
  | { kind: 'unreachable'; message: string };
