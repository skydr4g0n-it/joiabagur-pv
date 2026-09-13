/**
 * Family review screen (EP13 / C18b).
 *
 * The tests that matter most are the three about **three states**. A list that was computed and
 * came back empty and one that could not be computed look identical once only the rows are drawn,
 * and on a screen whose subject is catalogue quality "nothing to review" reads as "nothing is
 * wrong" — the conclusion this change exists to establish with evidence. It is the exact shape in
 * which the C17 risk materialised, so it is pinned here rather than trusted to review.
 *
 * The service is mocked rather than intercepted: MSW does not fail an unhandled request in this
 * project (`onUnhandledRequest: 'warn'`), so a test could pass having asserted nothing at all.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import FamilyReviewPage from '../family-review';
import { familyReviewService } from '@/services/family-review.service';
import { productService } from '@/services/product.service';
import type {
  FamilyAudit,
  FamilyDetail,
  FamilyReviewMetrics,
  PaginatedFamilies,
  RecordedVerdict,
} from '@/types/family-review.types';

vi.mock('@/services/family-review.service');
vi.mock('@/services/product.service');

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const mocked = vi.mocked(familyReviewService);
const mockedProducts = vi.mocked(productService);

const FAMILY_ID = '11111111-1111-1111-1111-111111111111';
const PRODUCT_ID = '22222222-2222-2222-2222-222222222222';
const CHAIN_ONE = '88888888-8888-8888-8888-888888888881';
const CHAIN_TWO = '88888888-8888-8888-8888-888888888882';

const emptyAudit: FamilyAudit = {
  flaggedMembers: [],
  orphanCandidates: [],
  rejectedGroups: [],
  excludedProducts: [],
  familiesReviewedCount: 156,
  membersExaminedCount: 486,
};

const populatedAudit: FamilyAudit = {
  ...emptyAudit,
  flaggedMembers: [
    {
      productId: PRODUCT_ID,
      sku: 'SKU610',
      name: 'Colgante Estrella de Mar',
      variantLabel: null,
      familyId: FAMILY_ID,
      familyName: 'Colgante estrella de mar',
      margin: 0.147,
      strangerFamilyId: '33333333-3333-3333-3333-333333333333',
      reason: 'closer_to_another_family',
    },
  ],
  orphanCandidates: [
    {
      productId: '44444444-4444-4444-4444-444444444444',
      sku: 'SKU25',
      name: 'Pendientes botón erizo de mar S dorado',
      pieceType: 'pendientes',
      dataOrigin: 'real',
      familyId: FAMILY_ID,
      familyName: 'Pendientes boton erizo de mar',
      similarity: 0.951,
      worstSibling: 0.842,
      margin: 0.109,
      purity: 4,
    },
  ],
  rejectedGroups: [
    {
      root: 'alianzas',
      pieceType: 'anillo',
      reason: 'root_too_short',
      productNames: ['Alianzas Plata', 'Alianzas oro'],
    },
  ],
};

const onePage: PaginatedFamilies = {
  items: [
    {
      id: FAMILY_ID,
      name: 'Colgante estrella de mar',
      description: null,
      origin: 'AiApproved',
      memberCount: 8,
      approvedByUserId: null,
      approvedAt: '2026-08-31T10:00:00Z',
      reviewedMemberCount: 0,
      rejectedMemberCount: 0,
    },
  ],
  totalCount: 156,
  totalPages: 4,
  currentPage: 1,
  pageSize: 50,
};

/** One judgement the catalogue has not acted on: a candidate confirmed but never added. */
const pendingAddition: RecordedVerdict = {
  productId: '55555555-5555-5555-5555-555555555555',
  sku: 'SKU25',
  productName: 'Pendientes botón erizo de mar S dorado',
  familyId: FAMILY_ID,
  familyName: 'Pendientes boton erizo de mar',
  outcome: 'Confirmed',
  isCurrentMember: false,
  pendingAction: 'add',
  marginAtReview: 0.109,
  reviewedAt: '2026-08-31T21:25:31Z',
};

/** A judgement the catalogue already reflects, so it must not appear as pending. */
const settled: RecordedVerdict = {
  ...pendingAddition,
  productId: '66666666-6666-6666-6666-666666666666',
  sku: 'SKU82',
  productName: 'Colgante estrella de mar M oro',
  isCurrentMember: true,
  pendingAction: 'none',
};

const metrics: FamilyReviewMetrics = {
  totalJudged: 58,
  membersJudged: 18,
  membersConfirmed: 17,
  candidatesJudged: 40,
  candidatesConfirmed: 6,
  memberConfirmationRate: 94.4,
  candidateAcceptanceRate: 15,
  timedJudgements: 58,
  averageReviewSeconds: 12.4,
  pendingActions: 1,
};

const familyDetail: FamilyDetail = {
  id: FAMILY_ID,
  name: 'Colgante estrella de mar',
  description: null,
  origin: 'AiApproved',
  members: [
    {
      productId: PRODUCT_ID,
      sku: 'SKU610',
      name: 'Colgante Estrella de Mar',
      variantLabel: null,
      sortOrder: 0,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.getAudit.mockResolvedValue({ state: 'loaded', audit: populatedAudit });
  mocked.listFamilies.mockResolvedValue(onePage);
  mocked.recordVerdicts.mockResolvedValue({ created: 1, updated: 0 });
  mocked.dissolveFamily.mockResolvedValue(undefined);
  mocked.listVerdicts.mockResolvedValue([pendingAddition, settled]);
  mocked.applyVerdict.mockResolvedValue(undefined);
  mocked.getMetrics.mockResolvedValue(metrics);
  mocked.getFamily.mockResolvedValue(familyDetail);
  mocked.relabelMember.mockResolvedValue(undefined);
  mocked.createFamily.mockResolvedValue({
    id: '77777777-7777-7777-7777-777777777777',
    name: 'Cadena de plata',
    description: null,
    origin: 'Manual',
    members: [],
  });
  // Declared explicitly, like every other boundary here. An auto-mocked method returns
  // undefined, and a screen that then calls `.map` on it fails with a render error rather than
  // an assertion — which is a slower way to learn that a stub was missing.
  mockedProducts.searchProducts.mockResolvedValue([
    { id: CHAIN_ONE, sku: 'SKU-CAD-1', name: 'Cadena de plata 45 cm' },
    { id: CHAIN_TWO, sku: 'SKU-CAD-2', name: 'Cadena de plata 50 cm' },
  ] as never);
});

describe('family review screen', () => {
  it('should list families a page at a time when the screen opens', async () => {
    render(<FamilyReviewPage />);

    expect(await screen.findByText('Colgante estrella de mar')).toBeInTheDocument();
    expect(screen.getByText('156 familia(s)')).toBeInTheDocument();
    expect(mocked.listFamilies).toHaveBeenCalledWith({ page: 1 }, expect.anything());
  });

  it('should show why a group was rejected when the audit reports a refusal', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Incidencias/ }));

    expect(await screen.findByText('root_too_short')).toBeInTheDocument();
    expect(screen.getByText(/Alianzas Plata/)).toBeInTheDocument();
  });

  /**
   * The audit failed, and the screen has to say so.
   *
   * Without this the lists render empty and a reviewer concludes the catalogue is clean — which
   * is exactly the failure C17 produced and the reason D20 was put back into scope.
   */
  it('should show the audit as unavailable when the ai service does not answer', async () => {
    mocked.getAudit.mockResolvedValue({
      state: 'unavailable',
      reason: 'El servicio de IA no respondió.',
    });
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));

    expect(await screen.findByText('No se ha podido calcular')).toBeInTheDocument();
    expect(screen.getByText(/significa que no se sabe/)).toBeInTheDocument();
    expect(screen.queryByText('Sin hallazgos')).not.toBeInTheDocument();
  });

  it('should show an empty audit as computed and empty, not as unavailable', async () => {
    mocked.getAudit.mockResolvedValue({ state: 'loaded', audit: emptyAudit });
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));

    expect(await screen.findByText('Sin hallazgos')).toBeInTheDocument();
    expect(screen.getByText(/486 pertenencias/)).toBeInTheDocument();
    expect(screen.queryByText('No se ha podido calcular')).not.toBeInTheDocument();
  });

  /**
   * Availability is tracked per list, not per page. Reviewing the families needs no vectors, so a
   * failed audit must not take the rest of the screen down with it.
   */
  it('should keep family review usable when the audit is unavailable', async () => {
    mocked.getAudit.mockResolvedValue({
      state: 'unavailable',
      reason: 'El servicio de IA no respondió.',
    });
    render(<FamilyReviewPage />);

    expect(await screen.findByText('Colgante estrella de mar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disolver/ })).toBeInTheDocument();
  });

  it('should record the reviewer decision when a flagged member is confirmed', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));
    await user.click(await screen.findByRole('button', { name: 'Confirmar pertenencia' }));
    await user.click(screen.getByRole('button', { name: /Guardar/ }));

    // `objectContaining` rather than a literal: the judgement also carries the seconds the
    // reviewer spent, and pinning an exact shape here would make the timing a breaking change
    // for a test that is about the decision.
    await waitFor(() =>
      expect(mocked.recordVerdicts).toHaveBeenCalledWith([
        expect.objectContaining({
          productId: PRODUCT_ID,
          familyId: FAMILY_ID,
          outcome: 'Confirmed',
          marginAtReview: 0.147,
        }),
      ]),
    );
  });

  /**
   * A dismissed candidate is remembered by the server, and the screen's part of that contract is
   * to recompute after saving rather than keep showing what it just judged.
   */
  it('should keep a dismissed suggestion out of the next run', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Huérfanos/ }));
    await user.click(await screen.findByRole('button', { name: 'Rechazar pertenencia' }));
    await user.click(screen.getByRole('button', { name: /Guardar/ }));

    await waitFor(() => expect(mocked.recordVerdicts).toHaveBeenCalled());
    expect(mocked.recordVerdicts.mock.calls[0][0][0].outcome).toBe('Rejected');
    // Recomputed after saving: the judged pair travels with the next audit, so what the screen
    // shows has to come from the server rather than from local bookkeeping.
    await waitFor(() => expect(mocked.getAudit).toHaveBeenCalledTimes(2));
  });

  /**
   * Confirming and dismissing have to look different.
   *
   * The first version highlighted on "has a verdict" rather than on the verdict, so dismissing a
   * row lit the *Confirmar* button exactly as confirming did. On a queue of 156 that is how a
   * mis-click becomes permanent without anybody noticing — the reviewer has no way to see what
   * they just answered.
   */
  it('should mark only the answer that was given when a member is dismissed', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));
    await user.click(await screen.findByRole('button', { name: 'Rechazar pertenencia' }));

    expect(screen.getByRole('button', { name: 'Rechazar pertenencia' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Confirmar pertenencia' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('should mark only the answer that was given when a member is confirmed', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));
    await user.click(await screen.findByRole('button', { name: 'Confirmar pertenencia' }));

    expect(screen.getByRole('button', { name: 'Confirmar pertenencia' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Rechazar pertenencia' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('should move the mark when the reviewer changes their mind', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));
    await user.click(await screen.findByRole('button', { name: 'Confirmar pertenencia' }));
    await user.click(screen.getByRole('button', { name: 'Rechazar pertenencia' }));

    expect(screen.getByRole('button', { name: 'Rechazar pertenencia' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Confirmar pertenencia' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  /**
   * A verdict is not a membership, and the screen has to say which decisions are still only that.
   *
   * The first version recorded judgements and stopped there, so a reviewer could finish 58 items
   * and leave the catalogue untouched without any surface telling them. The audit cannot show it
   * either — it omits judged pairs, which is what makes a dismissal stick — so an unapplied
   * decision disappeared from every list and read as work already finished.
   */
  it('should list only the judgements the catalogue has not acted on', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Aplicar/ }));

    expect(
      await screen.findByText('Pendientes botón erizo de mar S dorado'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Colgante estrella de mar M oro')).not.toBeInTheDocument();
  });

  it('should count the pending changes on its tab', async () => {
    render(<FamilyReviewPage />);

    expect(await screen.findByRole('tab', { name: 'Aplicar (1)' })).toBeInTheDocument();
  });

  it('should enact a pending addition with the variant label the reviewer typed', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Aplicar/ }));
    await user.type(
      await screen.findByLabelText(/Etiqueta de variante para Pendientes botón erizo/),
      'S baño de oro',
    );
    await user.click(screen.getByRole('button', { name: 'Aplicar' }));

    await waitFor(() =>
      expect(mocked.applyVerdict).toHaveBeenCalledWith(pendingAddition, 'S baño de oro'),
    );
    // Reloaded afterwards: the pending list is the server's answer, not local bookkeeping.
    await waitFor(() => expect(mocked.listVerdicts).toHaveBeenCalledTimes(2));
  });

  it('should say nothing is pending only when every decision is reflected', async () => {
    mocked.listVerdicts.mockResolvedValue([settled]);
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Aplicar/ }));

    expect(await screen.findByText('Sin hallazgos')).toBeInTheDocument();
    expect(screen.getByText(/1 decisiones registradas ya están reflejadas/)).toBeInTheDocument();
  });

  /**
   * The stopwatch has to leave the browser.
   *
   * The first review session's timings were lost because the average lived only in component
   * state: the tab closed and half of the metric the delivery checklist asks for went with it.
   * Sending seconds per judgement is what makes it survive.
   */
  it('should send the seconds spent with each judgement', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));
    await user.click(await screen.findByRole('button', { name: 'Confirmar pertenencia' }));
    await user.click(screen.getByRole('button', { name: /Guardar/ }));

    await waitFor(() => expect(mocked.recordVerdicts).toHaveBeenCalled());
    const sent = mocked.recordVerdicts.mock.calls[0][0][0];
    expect(sent.reviewSeconds).toBeGreaterThanOrEqual(0);
    expect(typeof sent.reviewSeconds).toBe('number');
  });

  it('should show the average review time from the server, not from this session', async () => {
    render(<FamilyReviewPage />);

    expect(await screen.findByText(/58 juzgado\(s\) · 12.4 s de media/)).toBeInTheDocument();
  });

  it('should say when nothing was timed rather than showing a zero average', async () => {
    mocked.getMetrics.mockResolvedValue({
      ...metrics,
      timedJudgements: 0,
      averageReviewSeconds: null,
    });
    render(<FamilyReviewPage />);

    expect(await screen.findByText(/sin tiempos medidos/)).toBeInTheDocument();
  });

  /**
   * Correcting a label was the one thing the screen could not do.
   *
   * A member already inside a family had no edit affordance, so the first session's mistakes —
   * a variant left blank, a material written non-canonically — had to be fixed through the API
   * by hand.
   */
  it('should let the reviewer correct the variant label of a member', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(
      await screen.findByRole('button', { name: /Editar etiquetas de Colgante estrella de mar/ }),
    );
    const input = await screen.findByLabelText(/Etiqueta de Colgante Estrella de Mar/);
    await user.type(input, 'S baño de oro');
    await user.click(screen.getByRole('button', { name: 'Guardar etiqueta' }));

    await waitFor(() =>
      expect(mocked.relabelMember).toHaveBeenCalledWith(FAMILY_ID, PRODUCT_ID, 'S baño de oro'),
    );
  });

  /**
   * Pins which row a keystroke judges, which is the part of the keyboard wiring that is specific
   * to this screen and has no coverage anywhere else.
   *
   * The hook's own behaviour — inert inside a text field, fires outside one — is tested once, on
   * the profile review screen, and repeating it here would assert the same code twice. What is
   * only here is the cursor over the audit tabs: if it pointed at the wrong row, a keystroke
   * would record a judgement about a different product, silently and straight into the metric.
   */
  it('should judge the row under the cursor when a shortcut is used', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Marcados/ }));
    await screen.findByText('Colgante Estrella de Mar');

    // Away from any field, so the shortcut is live.
    await user.click(document.body);
    await user.keyboard('a');

    await user.click(screen.getByRole('button', { name: /^Guardar/ }));

    await waitFor(() => expect(mocked.recordVerdicts).toHaveBeenCalledTimes(1));
    const sent = mocked.recordVerdicts.mock.calls[0][0];
    expect(sent).toHaveLength(1);
    expect(sent[0].productId).toBe(PRODUCT_ID);
    expect(sent[0].familyId).toBe(FAMILY_ID);
    expect(sent[0].outcome).toBe('Confirmed');
    // And the stopwatch travelled with it, exactly as a mouse judgement does.
    expect(sent[0].reviewSeconds).toEqual(expect.any(Number));
  });

  it('should leave the shortcuts inert on a tab that holds no queue', async () => {
    // The families listing is not a review queue. A stray keystroke there must not judge a row
    // on a tab the reviewer is not looking at.
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await screen.findByText('Colgante estrella de mar');
    await user.click(document.body);
    await user.keyboard('a');

    await user.click(screen.getByRole('button', { name: /^Guardar/ }));

    expect(mocked.recordVerdicts).not.toHaveBeenCalled();
  });

  it('should create a family with its members from the review screen', async () => {
    // The gap this closes is structural, not a threshold. The audit nominates an unassigned
    // product by its margin **relative to a target family**, so a product whose piece type has
    // no family at all cannot be nominated: there is nothing to compute a margin against. The
    // seven chains and the two plain wedding bands sit in exactly that position.
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.type(
      await screen.findByLabelText('Nombre de la familia'),
      'Cadena de plata',
    );
    await user.type(screen.getByLabelText('Buscar productos'), 'cadena');
    await user.click(screen.getByRole('button', { name: 'Buscar' }));

    const first = await screen.findByRole('row', { name: /Cadena de plata 45 cm/ });
    await user.click(within(first).getByRole('button', { name: 'Añadir' }));

    const second = screen.getByRole('row', { name: /Cadena de plata 50 cm/ });
    await user.click(within(second).getByRole('button', { name: 'Añadir' }));

    await user.type(
      screen.getByLabelText('Etiqueta de variante de Cadena de plata 45 cm'),
      '45 cm',
    );
    await user.type(
      screen.getByLabelText('Etiqueta de variante de Cadena de plata 50 cm'),
      '50 cm',
    );

    await user.click(screen.getByRole('button', { name: /Crear con 2 miembro\(s\)/ }));

    await waitFor(() =>
      expect(mocked.createFamily).toHaveBeenCalledWith('Cadena de plata', [
        { productId: CHAIN_ONE, variantLabel: '45 cm' },
        { productId: CHAIN_TWO, variantLabel: '50 cm' },
      ]),
    );
  });

  it('should report purity without ever filtering on it', async () => {
    const user = userEvent.setup();
    render(<FamilyReviewPage />);

    await user.click(await screen.findByRole('tab', { name: /Huérfanos/ }));

    // Shown, so a reviewer can rank; the candidate is present because of its margin, and a
    // purity of 4 accompanies it rather than selecting it.
    expect(await screen.findByText('4/5')).toBeInTheDocument();
    expect(screen.getByText('0,109')).toBeInTheDocument();
  });
});
