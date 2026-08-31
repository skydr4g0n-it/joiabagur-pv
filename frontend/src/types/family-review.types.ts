/**
 * Types for the family review screen (EP13 / C18b).
 *
 * The browser never talks to jbg-ai — it is private by design — so these are the shapes the .NET
 * API serves. Two of them describe the same question read from opposite sides of the membership
 * line: a member of a family the vectors do not support, and a product belonging to nothing that
 * looks like it belongs somewhere.
 */

/** `Manual` was created by hand; `AiApproved` came from an assisted suggestion. */
export type FamilyOrigin = 'Manual' | 'AiApproved';

/** What a person decided about a product and a family. */
export type FamilyReviewOutcome = 'Confirmed' | 'Rejected';

/** Where a product came from. Carried because the two populations behave very differently. */
export type DataOrigin = 'real' | 'synthetic';

/**
 * The three states a list can be in, which the screen must never collapse into two.
 *
 * `unavailable` and `loaded` with nothing in it look identical if only the rows are drawn, and on
 * a screen whose subject is catalogue quality "nothing to review" reads as "nothing is wrong" —
 * the conclusion this whole change exists to establish with evidence rather than assert by
 * accident. It is the shape in which the C17 risk actually materialised.
 */
export type ListState = 'loading' | 'loaded' | 'unavailable';

/** A family as it appears in the listing: enough to triage without opening it. */
export interface FamilyListItem {
  id: string;
  name: string;
  description: string | null;
  origin: FamilyOrigin;
  memberCount: number;
  approvedByUserId: string | null;
  approvedAt: string | null;
  /** How many of its members carry a human verdict. */
  reviewedMemberCount: number;
  /** How many of those verdicts rejected the membership. */
  rejectedMemberCount: number;
}

/** One page of families, with the total that matched before paging. */
export interface PaginatedFamilies {
  items: FamilyListItem[];
  totalCount: number;
  totalPages: number;
  currentPage: number;
  pageSize: number;
}

/** Narrowing for the listing. Every field optional: an empty query lists everything. */
export interface FamilyListQuery {
  page?: number;
  pageSize?: number;
  origin?: FamilyOrigin;
  pieceType?: string;
  hasRejectedMembers?: boolean;
}

/** A member of an existing family that the vectors do not support. */
export interface FlaggedMember {
  productId: string;
  sku: string;
  name: string;
  /** Null is the base piece — a legitimate variant value, not a gap. */
  variantLabel: string | null;
  familyId: string;
  familyName: string | null;
  /** How far the nearest stranger beat this member's own worst sibling. */
  margin: number;
  strangerFamilyId: string | null;
  reason: string;
}

/** A product belonging to no family that looks like it belongs to one. */
export interface OrphanCandidate {
  productId: string;
  sku: string;
  name: string;
  pieceType: string;
  dataOrigin: DataOrigin;
  familyId: string;
  familyName: string | null;
  similarity: number;
  /** Lowest similarity observed inside the target family. */
  worstSibling: number;
  /** `similarity - worstSibling`. This is the nomination criterion. */
  margin: number;
  /**
   * Of the five nearest neighbours of the same piece type, how many belong to this family.
   *
   * **Shown, never filtered on.** Measured over this corpus, purity nominates 55 synthetic
   * products against 19 real ones, because the deliberate `vN` families it cannot separate from a
   * missing member are synthetic by construction. It earns its place ranking a list the margin
   * already chose.
   */
  purity: number;
}

/** A group a guard refused to propose, reported so a person can look at it. */
export interface RejectedGroup {
  root: string;
  pieceType: string | null;
  reason: string;
  productNames: string[];
}

/** A product the piece-type gate removed before grouping. */
export interface ExcludedProduct {
  productId: string;
  sku: string;
  name: string;
  reason: string;
}

/** Everything one audit produced: both sides of the line, and both refusals. */
export interface FamilyAudit {
  flaggedMembers: FlaggedMember[];
  orphanCandidates: OrphanCandidate[];
  rejectedGroups: RejectedGroup[];
  excludedProducts: ExcludedProduct[];
  /** Families examined, so an empty flag list is readable rather than ambiguous. */
  familiesReviewedCount: number;
  /** Memberships examined, for the same reason. */
  membersExaminedCount: number;
}

/** One judgement a person made. */
export interface FamilyVerdict {
  productId: string;
  familyId: string;
  outcome: FamilyReviewOutcome;
  /** The margin the audit reported at the moment of the decision, when it came from one. */
  marginAtReview?: number;
  note?: string;
}

/** How a batch of judgements landed. */
export interface RecordVerdictsResult {
  created: number;
  /** Judgements that replaced an existing one for the same pair — a person changing their mind. */
  updated: number;
}

/**
 * The audit, or the reason there is none.
 *
 * A discriminated result rather than `FamilyAudit | null`, so that a caller cannot reach an empty
 * list without having passed through the state that says whether it was computed.
 */
export type AuditOutcome =
  | { state: 'loaded'; audit: FamilyAudit }
  | { state: 'unavailable'; reason: string };
