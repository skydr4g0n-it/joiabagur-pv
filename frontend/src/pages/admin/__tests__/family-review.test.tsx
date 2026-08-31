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
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import FamilyReviewPage from '../family-review';
import { familyReviewService } from '@/services/family-review.service';
import type { FamilyAudit, PaginatedFamilies, RecordedVerdict } from '@/types/family-review.types';

vi.mock('@/services/family-review.service');

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const mocked = vi.mocked(familyReviewService);

const FAMILY_ID = '11111111-1111-1111-1111-111111111111';
const PRODUCT_ID = '22222222-2222-2222-2222-222222222222';

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

beforeEach(() => {
  vi.clearAllMocks();
  mocked.getAudit.mockResolvedValue({ state: 'loaded', audit: populatedAudit });
  mocked.listFamilies.mockResolvedValue(onePage);
  mocked.recordVerdicts.mockResolvedValue({ created: 1, updated: 0 });
  mocked.dissolveFamily.mockResolvedValue(undefined);
  mocked.listVerdicts.mockResolvedValue([pendingAddition, settled]);
  mocked.applyVerdict.mockResolvedValue(undefined);
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

    await waitFor(() =>
      expect(mocked.recordVerdicts).toHaveBeenCalledWith([
        {
          productId: PRODUCT_ID,
          familyId: FAMILY_ID,
          outcome: 'Confirmed',
          marginAtReview: 0.147,
        },
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
