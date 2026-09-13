/**
 * Types for the profile review screen (EP13 / C28).
 *
 * Mirrors the DTOs the .NET API serves. The browser never talks to jbg-ai — it is private by
 * design and publishes no port — and in any case the human review and its metrics are business,
 * which lives on the .NET side.
 */

import type { ListState } from './family-review.types';

export type { ListState };

/**
 * The evidence stratum a profile belongs to.
 *
 * Not a confidence band. The extraction service never copies the model's own score; it emits a
 * four-value staircase describing **what kind of evidence** stands behind a value — a rule
 * produced it, its vocabulary phrase is literally in the source text, the model asserted it with
 * no such phrase, or it is absent. That is why the strata ask different questions.
 */
export type EvidenceStratumCode = 'A' | 'B' | 'C';

/**
 * Which way a reviewer moved a field.
 *
 * `addition` means an omission was caught — the extractor missed something the text stated.
 * `removal` means a hallucination was caught — it asserted something the text does not support.
 * Reporting only "corrected: yes" would merge two different defects with different remedies.
 */
export type CorrectionDirection = 'confirmation' | 'addition' | 'removal' | 'substitution';

/** Field names, exactly as the provenance documents key them. */
export type ProfileFieldName =
  | 'piece_type'
  | 'materials'
  | 'stone_type'
  | 'size_label'
  | 'color_tags'
  | 'style_tags'
  | 'occasion_tags';

/** One field as the screen has to show it: value, proposal, confidence and provenance. */
export interface ProfileReviewField {
  field: ProfileFieldName;
  isList: boolean;
  value: string | null;
  values: string[];
  proposedValue: string | null;
  proposedValues: string[];
  confidence: number;
  /** `rule` or `inferred`. */
  source: string;
  /** Whether an error in this field reaches a customer. */
  sensitive: boolean;
  /** Sensitive **and** inferred: the hybrid policy needs a person to vouch for it. */
  pendingReview: boolean;
  /** Whether the value in force already differs from the proposal. */
  alreadyCorrected: boolean;
}

/** One profile, with the source text it is judged against. */
export interface ProfileReviewItem {
  productId: string;
  sku: string;
  name: string;
  description: string | null;
  /**
   * Whether the product has a description at all.
   *
   * Carried so the screen can *state* the absence rather than render a blank. A gap where the
   * evidence should be reads as "nothing worth saying", when what it means is that the reviewer
   * has less to judge against than usual.
   */
  hasDescription: boolean;
  stratum: EvidenceStratumCode;
  stratumDecidingField: ProfileFieldName;
  question: string;
  fields: ProfileReviewField[];
  reviewStatus: string;
  reviewOrigin: string;
  promptVersion: string | null;
}

/** What one stratum contributed to the batch, and what it holds in the corpus. */
export interface ProfileReviewStratum {
  stratum: EvidenceStratumCode;
  label: string;
  question: string;
  corpusSize: number;
  quota: number;
  drawn: number;
  exhausted: boolean;
}

/** The stratified batch, with the seed that produced it. */
export interface ProfileReviewQueue {
  seed: string;
  strata: ProfileReviewStratum[];
  items: ProfileReviewItem[];
  totalCount: number;
  page: number;
  pageSize: number;
}

/**
 * One reviewer's judgement.
 *
 * A **full declaration** of what the catalog should claim afterwards, not a patch: a field left
 * out of a patch and a field the reviewer deliberately cleared are indistinguishable, and telling
 * those two apart is exactly what the removal direction measures.
 */
export interface RecordProfileReviewRequest {
  productId: string;
  verdict: 'approved' | 'rejected';
  /**
   * The measured duration, in milliseconds.
   *
   * Required, and it travels **in this request**. The first review capability recorded
   * sixty-four judgements and six timings because its stopwatch lived in component state and
   * died with the tab, and the average its delivery needed does not exist for that session.
   */
  reviewDurationMs: number;
  pieceType: string | null;
  materials: string[];
  stoneType: string | null;
  sizeLabel: string | null;
  colorTags: string[];
  styleTags: string[];
  occasionTags: string[];
}

export interface ProfileFieldDirection {
  field: ProfileFieldName;
  direction: CorrectionDirection;
}

export interface RecordProfileReviewResult {
  productId: string;
  reviewStatus: string;
  stratum: EvidenceStratumCode;
  directions: ProfileFieldDirection[];
  correctedFields: number;
  reviewDurationMs: number | null;
}

/**
 * Approving one field across many profiles of one stratum.
 *
 * `fields` is a list so that naming more than one is expressible and can therefore be refused by
 * the server. Unbounded, bulk approval is how a batch stops containing any evidence.
 */
export interface BulkApproveProfilesRequest {
  fields: ProfileFieldName[];
  stratum: EvidenceStratumCode;
  productIds: string[];
}

export interface BulkApproveProfilesResult {
  field: ProfileFieldName;
  stratum: EvidenceStratumCode;
  approved: number;
}

/** The rejected profiles, offered with the question inverted. */
export interface RejectedProfiles {
  items: ProfileReviewItem[];
  totalCount: number;
  page: number;
  pageSize: number;
  question: string;
}

export interface ProfileFieldStratumCorrection {
  stratum: EvidenceStratumCode;
  reviewed: number;
  corrected: number;
  correctionRate: number | null;
  confirmations: number;
  additions: number;
  removals: number;
  substitutions: number;
  corpusSize: number;
}

export interface ProfileFieldCorrection {
  field: ProfileFieldName;
  reviewed: number;
  corrected: number;
  /** Over the sample, which is not the catalog. */
  sampleCorrectionRate: number | null;
  /** Weighted by the real size of each stratum in the corpus. The figure that describes it. */
  weightedCorrectionRate: number | null;
  byStratum: ProfileFieldStratumCorrection[];
}

export interface ProfileStratumCorrection {
  stratum: EvidenceStratumCode;
  label: string;
  corpusSize: number;
  profilesReviewed: number;
  profilesWithAnyCorrection: number;
  fieldsReviewed: number;
  fieldsCorrected: number;
  correctionRate: number | null;
  additions: number;
  removals: number;
  substitutions: number;
}

/** The figures the delivery cites. */
export interface ProfileReviewMetrics {
  profilesTotal: number;
  profilesReviewedByHuman: number;
  profilesAutoBulk: number;
  reviewedShare: number | null;
  timedReviews: number;
  bulkApprovedReviews: number;
  /**
   * Over the timed population only, and `null` — never `0` — when nothing was timed.
   *
   * A zero asserts an instantaneous review, which is a claim. An absence reports that nothing
   * was measured, which is the truth.
   */
  averageReviewSeconds: number | null;
  minReviewSeconds: number | null;
  maxReviewSeconds: number | null;
  fieldsReviewed: number;
  fieldsCorrected: number;
  sampleCorrectionRate: number | null;
  weightedCorrectionRate: number | null;
  fields: ProfileFieldCorrection[];
  strata: ProfileStratumCorrection[];
  profilesByPromptVersion: Record<string, number>;
  seed: string;
}

/**
 * A read that says **why** there is nothing, when there is nothing.
 *
 * Discriminated rather than throwing or returning an empty list. On a screen whose subject is
 * catalogue quality, an empty result and a service that did not answer look identical once the
 * rows are drawn, and "nothing to review" reads as "nothing is wrong" — the conclusion this
 * capability exists to establish with evidence rather than imply by failure.
 */
export type QueueOutcome =
  | { state: 'loaded'; queue: ProfileReviewQueue }
  | { state: 'unavailable'; reason: string };

export type RejectedOutcome =
  | { state: 'loaded'; rejected: RejectedProfiles }
  | { state: 'unavailable'; reason: string };

export type MetricsOutcome =
  | { state: 'loaded'; metrics: ProfileReviewMetrics }
  | { state: 'unavailable'; reason: string };
