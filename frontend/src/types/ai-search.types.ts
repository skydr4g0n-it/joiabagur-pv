/**
 * Assisted Search Types (EP14 / C16)
 * Mirror of the backend contract for `POST /api/ai/search` and
 * `POST /api/ai/search-events/{id}/selection`.
 *
 * The browser never talks to the AI service: .NET proposes nothing and decides everything about
 * price, stock and availability, so every field below that describes a product is catalog truth.
 */

/** What the browser sends to run an assisted search. */
export interface AssistedSearchRequest {
  /** Natural-language query typed by the operator. */
  query: string;
  /** Point of sale the search is served for. Always required — never inferred by the server. */
  pointOfSaleId: string;
  /** How many results to display. The server falls back to its configured default. */
  pageSize?: number;
  /**
   * Groups the reformulations of one visit to the panel, so a rephrasing is not counted as an
   * abandoned query. Generated when the panel mounts, not per search.
   */
  searchSessionId?: string;
  /** Canonical material terms selected in the quick filters. */
  materials?: string[];
  /** Optional piece category. */
  category?: string;
}

/** One result as the operator sees it. */
export interface AssistedSearchResult {
  productId: string;
  sku: string;
  name: string;
  /** Current catalog price, in EUR. */
  price: number;
  /** Units at the point of sale of the search, not the sum across points of sale. */
  quantityAtPointOfSale: number;
  /**
   * False when the product is carried by this shop but has run out. Such a result is kept on
   * purpose: "we carry it, we are out of it" is an answer that can still save a sale.
   */
  hasStock: boolean;
  primaryPhotoUrl?: string | null;
  collectionName?: string | null;
  /** Relevance score from the retriever, or null on the degraded path. */
  score?: number | null;
  /**
   * Which branches of the retriever produced this result — `vector`, `lexical`, or both since
   * C21 fused them. Empty on the degraded path, where no retriever ran and the .NET side's own
   * text search answered.
   *
   * The raw values are still **not rendered**: they are engineering vocabulary. The row
   * translates them into one origin badge per result, which is what lets a search served after
   * an embedding-provider failure say so instead of claiming a semantic match.
   */
  matchReasons: string[];
  /**
   * Materials the retriever recognised. Index signals, not hydrated truth — they explain the
   * match and close the loop with the quick filters. Empty on the degraded path.
   */
  materials: string[];
  familyId?: string | null;
  /**
   * Variant label within the family — the size. Populated by C18, so it is null everywhere
   * today and must be rendered conditionally rather than substituted.
   */
  variantLabel?: string | null;
}

/**
 * The answer to an assisted search.
 *
 * `aiAvailable` and `lowConfidence` are what separate the ways a search can return nothing.
 * They cannot separate "switched off for this shop" from "the AI service is down": both arrive
 * as `aiAvailable: false`. Telemetry distinguishes them server-side; the API does not.
 *
 * `lowConfidence` carries the retriever's cross-branch disagreement signal only when more than
 * one branch ran; when a single branch answered it means what it meant before C21 — nothing was
 * returned. Either way it is only ever read here alongside an empty result list.
 */
export interface AssistedSearchResponse {
  /** Results in the order the retriever ranked them. Never re-sorted on the client. */
  results: AssistedSearchResult[];
  /**
   * Identifier of the recorded search event, so a selection can be attributed to this search.
   * Null when telemetry could not persist, which never fails the search.
   */
  searchEventId?: string | null;
  aiAvailable: boolean;
  lowConfidence: boolean;
  pointOfSaleId: string;
  /** Candidates the retriever produced. Zero on the degraded and disabled paths. */
  candidatesReturned: number;
  /** Candidates that survived hydration at this point of sale. */
  survivedHydration: number;
}

/**
 * How a search attempt ended, from the panel's point of view.
 *
 * The rate-limit case is a member of its own because the endpoint's contract requires it to stay
 * distinguishable from the AI service being unavailable: one is a fault, the other is the system
 * protecting itself, and they have opposite remedies.
 */
export type AssistedSearchOutcome =
  | { kind: 'ok'; response: AssistedSearchResponse }
  | { kind: 'rate-limited' }
  | { kind: 'forbidden' }
  | { kind: 'invalid'; errors: string[] }
  | { kind: 'error'; message: string };

/** The four ways the panel can end up with nothing to show, plus the normal one. */
export type AssistedSearchDisplayState =
  | 'results'
  | 'abstained'
  | 'no-assortment'
  | 'degraded'
  | 'rate-limited';
