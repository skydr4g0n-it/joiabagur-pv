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
  /**
   * Replaces `should highlight inferred sensitive fields pending review`, which the plan card
   * named and the corpus refuted.
   *
   * That mark was **constant in six of the seven fields** across the 1.114 queued profiles —
   * always on for piece type, materials and stone type, always off for the three commercial tags
   * — so it distinguished nothing. What varies, and what a reviewer actually reads, is the
   * provenance of each field.
   */
  it('should distinguish a rule from an inference in the provenance of each field', async () => {
    render(<ProfileReviewPage />);

    const size = await screen.findByRole('row', { name: /Talla/ });
    expect(within(size).getByText('regla')).toBeInTheDocument();

    expect(
      within(screen.getByRole('row', { name: /Materiales/ })).getByText('inferido'),
    ).toBeInTheDocument();

    // The mark itself is gone: a signal that never varies is not a signal.
    expect(screen.queryByText('pendiente de revisión')).not.toBeInTheDocument();
  });

  it('should report a field the extractor never proposed as absent rather than inferred', async () => {
    // Measured on the corpus: 613 of the 1.114 queued profiles carry no size label at all.
    // Reporting those as inferred at 0,20 reads as "the model asserted this with no evidence"
    // about a field the model never spoke to — and with the per-field mark gone, this column and
    // the confidence beside it are the whole signal, so they cannot say something untrue.
    mocked.getQueue.mockResolvedValue({
      state: 'loaded',
      queue: aQueue([
        anItem({
          fields: [
            {
              field: 'size_label',
              isList: false,
              value: null,
              values: [],
              proposedValue: null,
              proposedValues: [],
              confidence: 0.2,
              source: 'absent',
              sensitive: true,
              pendingReview: false,
              alreadyCorrected: false,
            },
          ],
        }),
      ]),
    });

    render(<ProfileReviewPage />);

    const size = await screen.findByRole('row', { name: /Talla/ });
    expect(within(size).getByText('ausente')).toBeInTheDocument();
    expect(within(size).queryByText('inferido')).not.toBeInTheDocument();
  });

  it('should record correction when material list is edited', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    // Chosen from the closed vocabulary rather than typed. A material outside it is not merely
    // wrong: `materials && ARRAY[…]` is how the retriever filters, and the search offers the
    // same closed list, so no query could ever name it again.
    await user.click(await screen.findByRole('button', { name: 'Materiales' }));
    await user.click(screen.getByRole('button', { name: 'Oro' }));

    await user.click(screen.getByRole('button', { name: /Aprobar y siguiente/ }));

    await waitFor(() => expect(mocked.recordReview).toHaveBeenCalledTimes(1));

    const sent = mocked.recordReview.mock.calls[0][0];
    expect(sent.materials).toEqual(['plata', 'oro']);
    expect(sent.productId).toBe(PRODUCT_ID);
    expect(sent.verdict).toBe('approved');
  });

  it('should offer only the closed vocabulary for a governed field', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    await user.click(await screen.findByRole('button', { name: 'Materiales' }));

    // The nine canonical terms, and no way to type a tenth.
    expect(screen.getByRole('button', { name: 'Plata' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Baño de oro' })).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Materiales' })).not.toBeInTheDocument();
  });

  it('should keep a free text field for the size label', async () => {
    render(<ProfileReviewPage />);

    // The one field the extractor produces from a deterministic rule, and the rule emits ring
    // sizes and chain lengths the vocabulary never contained — twenty distinct labels in the
    // corpus against twelve terms. A closed list would make a size of 17 unrecordable.
    expect(await screen.findByRole('textbox', { name: 'Talla' })).toBeInTheDocument();
  });

  it('should record a vocabulary gap as a finding and not as a correction', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    const materialsRow = await screen.findByRole('row', { name: /Materiales/ });
    await user.click(
      within(materialsRow).getByRole('button', { name: /no está en la lista/ }),
    );
    await user.type(
      screen.getByLabelText(/Término que falta en el vocabulario de Materiales/),
      'platino',
    );
    await user.click(screen.getByRole('button', { name: 'Anotar' }));

    // It is recorded as a finding...
    await user.click(screen.getByRole('tab', { name: /Huecos de vocabulario \(1\)/ }));
    expect(await screen.findByText('platino')).toBeInTheDocument();

    // ...and it does not become a value in force, which is what keeps it out of the rate: the
    // extractor could not have produced a term its vocabulary does not contain.
    await user.click(screen.getByRole('tab', { name: /^Cola/ }));
    await user.click(await screen.findByRole('button', { name: /Aprobar y siguiente/ }));

    await waitFor(() => expect(mocked.recordReview).toHaveBeenCalledTimes(1));
    expect(mocked.recordReview.mock.calls[0][0].materials).toEqual(['plata']);
  });

  it('should show a recorded gap in its own field without making it a value in force', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    const materialsRow = await screen.findByRole('row', { name: /Materiales/ });
    await user.click(
      within(materialsRow).getByRole('button', { name: /no está en la lista/ }),
    );
    await user.type(
      screen.getByLabelText(/Término que falta en el vocabulario de Materiales/),
      'platino',
    );
    await user.click(screen.getByRole('button', { name: 'Anotar' }));

    // Visible in the field, so the reviewer can tell an item they have finished from one they
    // have not touched, and does not record the same term twice.
    const gap = await within(materialsRow).findByText(/platino · fuera de vocabulario/);
    expect(gap.closest('[data-vocabulary-gap]')).not.toBeNull();

    // And still not a value in force. "In force" is not a visual label: it is what travels to
    // the catalogue, where the term would match no filter, and into the correction rate, where
    // it would report the vocabulary's coverage as the extractor's error.
    await user.click(screen.getByRole('button', { name: /Aprobar y siguiente/ }));
    await waitFor(() => expect(mocked.recordReview).toHaveBeenCalledTimes(1));
    expect(mocked.recordReview.mock.calls[0][0].materials).toEqual(['plata']);
  });

  it('should let a gap recorded by mistake be withdrawn', async () => {
    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    const materialsRow = await screen.findByRole('row', { name: /Materiales/ });
    await user.click(
      within(materialsRow).getByRole('button', { name: /no está en la lista/ }),
    );
    await user.type(
      screen.getByLabelText(/Término que falta en el vocabulario de Materiales/),
      'platino',
    );
    await user.click(screen.getByRole('button', { name: 'Anotar' }));
    await within(materialsRow).findByText(/platino · fuera de vocabulario/);

    await user.click(
      within(materialsRow).getByRole('button', { name: /Quitar el hueco platino/ }),
    );

    await waitFor(() =>
      expect(
        within(materialsRow).queryByText(/platino · fuera de vocabulario/),
      ).not.toBeInTheDocument(),
    );
  });

  it('should drop a judged profile from the page and move on to the next', async () => {
    // Reviewing moves the profile's origin to human, so the server stops offering it. Leaving it
    // on screen shows a queue that no longer exists — and once the page ran out, the screen
    // looked like the end of the batch with hundreds of items still to review.
    mocked.getQueue.mockResolvedValue({
      state: 'loaded',
      queue: aQueue([
        anItem(),
        anItem({ productId: '33333333-3333-3333-3333-333333333333', sku: 'SKU611', name: 'Pulsera onda' }),
      ]),
    });

    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    expect(await screen.findByText('Anillo erizo de mar talla M')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Aprobar y siguiente/ }));

    await waitFor(() => expect(screen.getByText('Pulsera onda')).toBeInTheDocument());
    expect(screen.queryByText('Anillo erizo de mar talla M')).not.toBeInTheDocument();
  });

  it('should fetch the next page when the current one is spent', async () => {
    mocked.getQueue.mockResolvedValue({ state: 'loaded', queue: aQueue([anItem()]) });

    const user = userEvent.setup();
    render(<ProfileReviewPage />);

    await screen.findByText('Anillo erizo de mar talla M');
    expect(mocked.getQueue).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: /Aprobar y siguiente/ }));

    // The batch is 180 and a page is 50, so running out of a page is not running out of work.
    await waitFor(() => expect(mocked.getQueue).toHaveBeenCalledTimes(2));
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

    // The size label is the field that stays free text, so it is the one that can still swallow
    // a shortcut. "ara" carries the approve key twice and the reject key is one letter away;
    // every one of them would fire on a screen whose shortcuts were not inert inside a field.
    const size = await screen.findByRole('textbox', { name: 'Talla' });
    await user.clear(size);
    await user.type(size, 'ara');

    expect(size).toHaveValue('ara');
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
