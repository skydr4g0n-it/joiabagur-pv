/**
 * Gift card attachment on sales cart
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { SalesCartPage } from '../cart';

vi.mock('@/services/sales.service');
vi.mock('@/services/inventory.service');
vi.mock('@/services/gift-card.service');
vi.mock('@/services/payment-method.service', () => ({
  paymentMethodService: {
    getPointOfSalePaymentMethods: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

const mockCartState = {
  lines: [
    {
      id: 'line-1',
      productId: 'prod-1',
      productSku: 'SKU-150',
      productName: 'Product 150',
      productPrice: 150,
      quantity: 1,
      pointOfSaleId: 'pos-1',
      pointOfSaleName: 'POS',
      paymentMethodId: 'pm-1',
      paymentMethodName: 'Cash',
      addedAt: new Date().toISOString(),
    },
  ],
  lineCount: 1,
  total: 150,
  pointOfSaleId: 'pos-1',
  pointOfSaleName: 'POS',
  paymentMethodId: 'pm-1',
  paymentMethodName: 'Cash',
  addLine: vi.fn(),
  removeLine: vi.fn(),
  clearCart: vi.fn(),
};

vi.mock('@/providers/cart-provider', () => ({
  CartProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useCart: () => mockCartState,
}));

function renderPage() {
  return render(
    <BrowserRouter>
      <SalesCartPage />
    </BrowserRouter>,
  );
}

describe('SalesCartPage gift cards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should add the card when the scanner decodes a GC code', async () => {
    const user = userEvent.setup();
    const { giftCardService } = await import('@/services/gift-card.service');
    const { inventoryService } = await import('@/services/inventory.service');
    vi.mocked(inventoryService.getProductStockBreakdown).mockResolvedValue({
      productId: 'prod-1',
      productSku: 'SKU-150',
      productName: 'Product 150',
      totalQuantity: 5,
      breakdown: [{ pointOfSaleId: 'pos-1', pointOfSaleName: 'POS', quantity: 5 }],
    });
    vi.mocked(giftCardService.getByCode).mockResolvedValue({
      id: 'gc-1',
      code: 'GC-TEST1234',
      nominalAmount: 100,
      spendableBalance: 100,
      expiryDate: '2030-12-31',
      pointOfSaleId: 'pos-1',
    });

    renderPage();
    const input = screen.getByPlaceholderText('GC-...');
    await user.type(input, 'GC-TEST1234{Enter}');

    await waitFor(() => {
      expect(giftCardService.getByCode).toHaveBeenCalledWith('GC-TEST1234', 'pos-1');
      expect(screen.getByText('GC-TEST1234')).toBeInTheDocument();
    });
  });

  it('should show an error when the scanner decodes an expired GC code', async () => {
    const user = userEvent.setup();
    const { giftCardService } = await import('@/services/gift-card.service');
    const { toast } = await import('sonner');
    const { inventoryService } = await import('@/services/inventory.service');
    vi.mocked(inventoryService.getProductStockBreakdown).mockResolvedValue({
      productId: 'prod-1',
      productSku: 'SKU-150',
      productName: 'Product 150',
      totalQuantity: 5,
      breakdown: [{ pointOfSaleId: 'pos-1', pointOfSaleName: 'POS', quantity: 5 }],
    });
    vi.mocked(giftCardService.getByCode).mockRejectedValue({
      response: { data: { message: 'La tarjeta regalo ha caducado.' } },
    });

    renderPage();
    const input = screen.getByPlaceholderText('GC-...');
    await user.type(input, 'GC-EXPIRED1{Enter}');

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('La tarjeta regalo ha caducado.');
    });
  });
});
