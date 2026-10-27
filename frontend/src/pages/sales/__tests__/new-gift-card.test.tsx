/**
 * Gift card attachment on manual sales registration
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ManualSalesPage } from '../new';

vi.mock('@/services/sales.service');
vi.mock('@/services/product.service');
vi.mock('@/services/point-of-sale.service');
vi.mock('@/services/payment-method.service');
vi.mock('@/services/inventory.service');
vi.mock('@/services/gift-card.service');

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock('@/providers/cart-provider', () => ({
  CartProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useCart: () => ({
    addLine: vi.fn(() => true),
    lineCount: 0,
  }),
}));

vi.mock('@/providers/auth-provider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useAuth: () => ({
    user: { id: 'user-1', username: 'testuser', role: 'Operator' },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

function renderPage() {
  return render(
    <BrowserRouter>
      <ManualSalesPage />
    </BrowserRouter>,
  );
}

describe('ManualSalesPage gift cards', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const posService = await import('@/services/point-of-sale.service');
    const paymentService = await import('@/services/payment-method.service');
    const productService = await import('@/services/product.service');
    const inventoryService = await import('@/services/inventory.service');

    vi.mocked(posService.pointOfSaleService.getPointsOfSale).mockResolvedValue([
      { id: 'pos-1', name: 'Test POS 1', code: 'POS1', allowManualPriceEdit: false } as never,
    ]);
    vi.mocked(paymentService.paymentMethodService.getPointOfSalePaymentMethods).mockResolvedValue([
      {
        id: 'pospm-1',
        pointOfSaleId: 'pos-1',
        paymentMethodId: 'pm-1',
        isActive: true,
        paymentMethod: { id: 'pm-1', name: 'Cash', code: 'CASH', isActive: true },
      },
      {
        id: 'pospm-gc',
        pointOfSaleId: 'pos-1',
        paymentMethodId: 'pm-gc',
        isActive: true,
        paymentMethod: { id: 'pm-gc', name: 'Tarjeta regalo', code: 'GIFT_CARD', isActive: true },
      },
    ] as never);
    vi.mocked(productService.productService.searchProducts).mockResolvedValue([
      {
        id: 'prod-1',
        sku: 'SKU-001',
        name: 'Test Product 1',
        price: 150,
        isActive: true,
      },
    ] as never);
    vi.mocked(inventoryService.inventoryService.getProductStockBreakdown).mockResolvedValue({
      productId: 'prod-1',
      productSku: 'SKU-001',
      productName: 'Test Product 1',
      totalQuantity: 10,
      breakdown: [{ pointOfSaleId: 'pos-1', pointOfSaleName: 'Test POS 1', quantity: 10 }],
    } as never);
  });

  it('should add the card when the scanner decodes a GC code', async () => {
    const user = userEvent.setup();
    const { giftCardService } = await import('@/services/gift-card.service');
    vi.mocked(giftCardService.getByCode).mockResolvedValue({
      id: 'gc-1',
      code: 'GC-TEST1234',
      nominalAmount: 100,
      spendableBalance: 100,
      expiryDate: '2030-12-31',
      pointOfSaleId: 'pos-1',
    });

    renderPage();
    const input = await screen.findByPlaceholderText('GC-...');
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
    vi.mocked(giftCardService.getByCode).mockRejectedValue({
      response: { data: { message: 'La tarjeta regalo ha caducado.' } },
    });

    renderPage();
    const input = await screen.findByPlaceholderText('GC-...');
    await user.type(input, 'GC-EXPIRED1{Enter}');

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('La tarjeta regalo ha caducado.');
    });
  });

  it('should show remaining cash due when a 100 EUR card covers a 150 EUR product', async () => {
    const user = userEvent.setup();
    const { giftCardService } = await import('@/services/gift-card.service');
    vi.mocked(giftCardService.getByCode).mockResolvedValue({
      id: 'gc-1',
      code: 'GC-E2E100',
      nominalAmount: 100,
      spendableBalance: 100,
      expiryDate: '2030-12-31',
      pointOfSaleId: 'pos-1',
    });

    renderPage();
    const searchInput = await screen.findByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));
    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });

    const cardInput = screen.getByPlaceholderText('GC-...');
    await user.type(cardInput, 'GC-E2E100{Enter}');
    await waitFor(() => {
      expect(screen.getByText('GC-E2E100')).toBeInTheDocument();
    });

    expect(screen.getByText(/50,00\s*€/)).toBeInTheDocument();
  });
});
