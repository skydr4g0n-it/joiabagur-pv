/**
 * Gift card issue page tests
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { GiftCardIssuePage } from '../issue';

vi.mock('@/services/gift-card.service', () => ({
  giftCardService: {
    issue: vi.fn(),
    getQrCodeSvg: vi.fn().mockResolvedValue('<svg></svg>'),
  },
}));

vi.mock('@/services/point-of-sale.service', () => ({
  pointOfSaleService: {
    getPointsOfSale: vi.fn().mockResolvedValue([
      { id: 'pos-1', name: 'Tienda', code: 'T1', isActive: true },
    ]),
  },
}));

vi.mock('@/services/payment-method.service', () => ({
  paymentMethodService: {
    getPointOfSalePaymentMethods: vi.fn().mockResolvedValue([
      {
        id: 'a1',
        isActive: true,
        paymentMethod: {
          id: 'pm-cash',
          code: 'CASH',
          name: 'Efectivo',
          isActive: true,
        },
      },
    ]),
  },
}));

vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({ user: { role: 'Operator' } }),
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { giftCardService } from '@/services/gift-card.service';

describe('GiftCardIssuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show nominal and code when issuance succeeds', async () => {
    vi.mocked(giftCardService.issue).mockResolvedValue({
      success: true,
      card: {
        id: 'card-1',
        code: 'GC-TESTCODE1',
        pointOfSaleId: 'pos-1',
        pointOfSaleName: 'Tienda',
        issuanceSalePointOfSaleId: 'pos-1',
        issuanceSalePointOfSaleName: 'Tienda',
        nominalAmount: 100,
        spendableBalance: 100,
        accountedRemainder: 100,
        expiryDate: '2027-01-01',
        issuanceSaleId: 'sale-1',
        issuanceSaleDate: '2026-10-27T10:00:00Z',
        linkedProducts: [],
        operations: [],
      },
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GiftCardIssuePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /emitir tarjeta/i })).toBeEnabled();
    });

    await user.click(screen.getByRole('button', { name: /emitir tarjeta/i }));

    await waitFor(() => {
      expect(giftCardService.issue).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByText('Tarjeta emitida')).toBeInTheDocument();
    });
    expect(screen.getAllByText(/GC-TESTCODE1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/100,00/).length).toBeGreaterThan(0);
  });
});
