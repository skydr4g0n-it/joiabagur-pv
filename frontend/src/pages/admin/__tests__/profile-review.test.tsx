/**
 * Profile review screen (EP13 / C28).
 *
 * The service is mocked rather than intercepted. MSW does not fail an unhandled request in this
 * project — `src/test/setup.ts` starts it with `onUnhandledRequest: 'warn'` — so a test that
 * forgot a handler would print a warning, receive nothing, and pass having asserted nothing at
 * all. Declaring the boundary with `vi.mock` makes the absence of a stub a failure instead of a
 * line of output nobody reads.
 *
 * Every value below is a fixture. None of them is a measurement: the correction rate and the
 * average review time this change delivers come from a real session over a real batch.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ProfileReviewPage from '../profile-review';
import { profileReviewService } from '@/services/profile-review.service';
import type {
  ProfileReviewItem,
  ProfileReviewMetrics,
  ProfileReviewQueue,
  RejectedProfiles,
} from '@/types/profile-review.types';

vi.mock('@/services/profile-review.service');

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const mocked = vi.mocked(profileReviewService);

const PRODUCT_ID = '11111111-1111-1111-1111-111111111111';

/**
 * A profile in the stratum where every value has a phrase behind it, so the question asked is
 * about what is missing. Individual tests spoil exactly one thing.
 */
const anItem = (overrides: Partial<ProfileReviewItem> = {}): ProfileReviewItem => ({
  productId: PRODUCT_ID,
  sku: 'SKU610',
  name: 'Anillo erizo de mar talla M',
  description: 'Anillo en plata de ley con baño de oro y acabado pulido.',
  hasDescription: true,
  stratum: 'C',
  stratumDecidingField: 'materials',
  question: '¿Falta algo?',
  reviewStatus: 'Approved',
  reviewOrigin: 'AutoBulk',
  promptVersion: 'enrichment/v1',
  fields: [
    {
      field: 'piece_type',
      isList: false,
      value: 'anillo',
      values: [],
      proposedValue: 'anillo',
      proposedValues: [],
      confidence: 0.85,
      source: 'inferred',
      sensitive: true,
      pendingReview: true,
      alreadyCorrected: false,
    },
    {
      field: 'materials',
      isList: true,
      value: null,
      values: ['plata'],
      proposedValue: null,
      proposedValues: ['plata'],
      confidence: 0.85,
      source: 'inferred',
      sensitive: true,
      pendingReview: true,
      alreadyCorrected: false,
    },
    {
      field: 'size_label',
      isList: false,
      value: 'M',
      values: [],
      proposedValue: 'M',
      proposedValues: [],
      confidence: 1,
      // The only field the extractor ever produces from a deterministic rule, and therefore the
      // only sensitive one a person does not have to vouch for.
      source: 'rule',
      sensitive: true,
      pendingReview: false,
      alreadyCorrected: false,
    },
    {
      field: 'color_tags',
      isList: true,
      value: null,
      values: ['dorado'],
      proposedValue: null,
      proposedValues: ['dorado'],
      confidence: 0.85,
      source: 'inferred',
      sensitive: false,
      pendingReview: false,
      alreadyCorrected: false,
    },
  ],
  ...overrides,
});

const aQueue = (items: ProfileReviewItem[] = [anItem()]): ProfileReviewQueue => ({
  seed: 'c28-profile-review',
  strata: [
    {
      stratum: 'A',
      label: 'Ausencia de evidencia',
      question: '¿Es correcto?',
      corpusSize: 122,
      quota: 60,
      drawn: 60,
      exhausted: false,
    },
    {
      stratum: 'B',
      label: 'Afirmado sin frase en el texto',
      question: '¿Es correcto?',
      corpusSize: 285,
      quota: 60,
      drawn: 60,
      exhausted: false,
    },
    {
      stratum: 'C',
      label: 'Afirmado con frase en el texto',
      question: '¿Falta algo?',
      corpusSize: 761,
      quota: 60,
      drawn: 60,
      exhausted: false,
    },
  ],
  items,
  totalCount: items.length,
  page: 1,
  pageSize: 50,
});

const noMetrics: ProfileReviewMetrics = {
  profilesTotal: 1200,
  profilesReviewedByHuman: 0,
  profilesAutoBulk: 1200,
  reviewedShare: 0,
  timedReviews: 0,
  bulkApprovedReviews: 0,
  averageReviewSeconds: null,
  minReviewSeconds: null,
  maxReviewSeconds: null,
  fieldsReviewed: 0,
  fieldsCorrected: 0,
  sampleCorrectionRate: null,
  weightedCorrectionRate: null,
  fields: [],
  strata: [],
  profilesByPromptVersion: { 'enrichment/v1': 1200 },
  seed: 'c28-profile-review',
};

const noRejected: RejectedProfiles = {
  items: [],
  totalCount: 0,
  page: 1,
  pageSize: 50,
  question: '¿Hay algún rechazo incorrecto?',
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.getQueue.mockResolvedValue({ state: 'loaded', queue: aQueue() });
  mocked.getRejected.mockResolvedValue({ state: 'loaded', rejected: noRejected });
  mocked.getMetrics.mockResolvedValue({ state: 'loaded', metrics: noMetrics });
  mocked.recordReview.mockResolvedValue({
    productId: PRODUCT_ID,
    reviewStatus: 'Approved',
    stratum: 'C',
    directions: [{ field: 'materials', direction: 'addition' }],
    correctedFields: 1,
    reviewDurationMs: 1000,
  });
});

describe('ProfileReviewPage', () => {
  it('should highlight inferred sensitive fields pending review', async () => {
    render(<ProfileReviewPage />);

    const pieceType = await screen.findByRole('row', { name: /Tipo de pieza/ });
    expect(pieceType).toHaveAttribute('data-pending-review', 'true');

    expect(screen.getByRole('row', { name: /Materiales/ })).toHaveAttribute(
      'data-pending-review',
      'true',
    );

    // The size came from a deterministic rule. Marking it would spend a reviewer's attention on
    // the one sensitive field that needs none, which is the trade that makes reviewing a catalog
    // of this size conceivable at all.
    expect(screen.getByRole('row', { name: /Talla/ })).not.toHaveAttribute('data-pending-review');

    // And a commercial tag is not sensitive, however it was produced.
    expect(screen.getByRole('row', { name: /Color/ })).not.toHaveAttribute('data-pending-review');
  });

  it('should record correction when material list is edited', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    const materials = await screen.findByLabelText('Materiales');
    await user.clear(materials);
    await user.type(materials, 'plata, oro');

    await user.click(screen.getByRole('button', { name: /Aprobar y siguiente/ }));

    await waitFor(() => expect(mocked.recordReview).toHaveBeenCalledTimes(1));

    const sent = mocked.recordReview.mock.calls[0][0];
    expect(sent.materials).toEqual(['plata', 'oro']);
    expect(sent.productId).toBe(PRODUCT_ID);
    expect(sent.verdict).toBe('approved');
  });

  it('should send the measured duration when an individual review is saved', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    await screen.findByLabelText('Materiales');
    await user.click(screen.getByRole('button', { name: /Aprobar y siguiente/ }));

    await waitFor(() => expect(mocked.recordReview).toHaveBeenCalledTimes(1));

    // It travels in the request that records the judgement, and it is a real measurement rather
    // than a placeholder. The previous review capability recorded sixty-four judgements and six
    // durations because this number lived in component state and died with the tab.
    const sent = mocked.recordReview.mock.calls[0][0];
    expect(sent.reviewDurationMs).toEqual(expect.any(Number));
    expect(sent.reviewDurationMs).toBeGreaterThan(0);
  });

  it('should report that the queue could not be computed when the read fails', async () => {
    mocked.getQueue.mockResolvedValue({
      state: 'unavailable',
      reason: 'El servicio no respondió.',
    });

    render(<ProfileReviewPage />);

    // Not an empty table. On a screen whose subject is catalogue quality, "nothing to review"
    // reads as "nothing is wrong" — the conclusion this capability exists to establish with
    // evidence rather than imply by failure.
    expect(await screen.findByText(/No se ha podido calcular/)).toBeInTheDocument();
    expect(screen.getByText(/El servicio no respondió/)).toBeInTheDocument();
    expect(screen.queryByText(/No queda ningún perfil sin revisar/)).not.toBeInTheDocument();
  });

  it('should not trigger a shortcut when typing inside a text field', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    const materials = await screen.findByLabelText('Materiales');
    await user.clear(materials);

    // "aro" carries the approve key, the reject key is one letter away, and every one of them
    // would fire on a screen whose shortcuts were not inert inside a field.
    await user.type(materials, 'aro');

    expect(materials).toHaveValue('aro');
    expect(mocked.recordReview).not.toHaveBeenCalled();
  });

  it('should approve with the keyboard when focus is outside a text field', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    await screen.findByLabelText('Materiales');
    await user.click(document.body);
    await user.keyboard('a');

    await waitFor(() => expect(mocked.recordReview).toHaveBeenCalledTimes(1));
    expect(mocked.recordReview.mock.calls[0][0].verdict).toBe('approved');
  });

  it('should show the product description beside the proposed values', async () => {
    render(<ProfileReviewPage />);

    // The criterion is fidelity to the source text, so the text is the evidence rather than
    // context — it has to be on screen with the values, not behind a link.
    expect(
      await screen.findByText(/Anillo en plata de ley con baño de oro/),
    ).toBeInTheDocument();
    expect(screen.getByText('Anillo erizo de mar talla M')).toBeInTheDocument();
  });

  it('should state the absence of a description when a product has none', async () => {
    mocked.getQueue.mockResolvedValue({
      state: 'loaded',
      queue: aQueue([anItem({ description: null, hasDescription: false })]),
    });

    render(<ProfileReviewPage />);

    expect(await screen.findByText(/no tiene descripción/)).toBeInTheDocument();
  });

  it('should ask what is missing when the stratum already has a textual span', async () => {
    render(<ProfileReviewPage />);

    expect(await screen.findByText('¿Falta algo?')).toBeInTheDocument();
  });

  it('should ask whether it is correct when the stratum lacks a textual span', async () => {
    mocked.getQueue.mockResolvedValue({
      state: 'loaded',
      queue: aQueue([anItem({ stratum: 'B', question: '¿Es correcto?' })]),
    });

    render(<ProfileReviewPage />);

    expect(await screen.findByText('¿Es correcto?')).toBeInTheDocument();
  });

  it('should refuse bulk approval until a single stratum is chosen', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    // The bound lives in the interface as well as on the server: without it the whole batch gets
    // approved at once and the correction rate stops saying anything about the extractor.
    expect(
      await screen.findByText(/Elige un estrato arriba para poder aprobar en masa/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^C · / }));

    await waitFor(() =>
      expect(
        screen.queryByText(/Elige un estrato arriba para poder aprobar en masa/),
      ).not.toBeInTheDocument(),
    );
  });

  it('should say nothing was timed rather than showing a zero average', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Métricas/ }));

    // A zero would assert an instantaneous review, which is a claim. An absence reports that
    // nothing was measured, which is what happened.
    const timed = await screen.findByText('Revisadas con cronómetro');
    expect(within(timed.closest('div')!.parentElement!).getByText(/sin tiempos medidos/))
      .toBeInTheDocument();
  });

  it('should show the sampling seed so the batch can be reconstructed', async () => {
    render(<ProfileReviewPage />);

    expect(await screen.findByText(/semilla: c28-profile-review/)).toBeInTheDocument();
  });
});
