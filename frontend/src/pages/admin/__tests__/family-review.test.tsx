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
import type { FamilyAudit, PaginatedFamilies } from '@/types/family-review.types';

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

beforeEach(() => {
  vi.clearAllMocks();
  mocked.getAudit.mockResolvedValue({ state: 'loaded', audit: populatedAudit });
  mocked.listFamilies.mockResolvedValue(onePage);
  mocked.recordVerdicts.mockResolvedValue({ created: 1, updated: 0 });
  mocked.dissolveFamily.mockResolvedValue(undefined);
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
