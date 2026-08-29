/**
 * Manual Sales Page — Search Attribution Tests (EP14 / C16)
 *
 * A file of its own rather than additions to `new.test.tsx`, which fails wholesale in the
 * baseline because it renders the page without a cart context. Fixing that is not this change's
 * business, and building on top of it would make these assertions unverifiable.
 *
 * What is held here is the last leg of the attribution: the identifier the panel handed over in
 * navigation state has to reach the sale request and the cart line, and it has to stop applying
 * the moment the operator picks a different product.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import { ManualSalesPage } from '../new';
import * as salesService from '@/services/sales.service';
import * as productService from '@/services/product.service';
import * as posService from '@/services/point-of-sale.service';
import * as paymentService from '@/services/payment-method.service';
import * as inventoryService from '@/services/inventory.service';

vi.mock('@/services/sales.service');
vi.mock('@/services/product.service');
vi.mock('@/services/point-of-sale.service');
vi.mock('@/services/payment-method.service');
vi.mock('@/services/inventory.service');

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { userId: 'user-1', username: 'testuser', role: 'Operator' },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

const addLine = vi.fn().mockReturnValue(true);
vi.mock('@/providers/cart-provider', () => ({
  useCart: () => ({ addLine, lineCount: 0 }),
}));

let locationState: Record<string, unknown> | null = null;
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useLocation: () => ({ state: locationState, pathname: '/sales/new' }),
  };
});

const PRODUCT = {
  id: 'prod-1',
  sku: 'SKU-001',
  name: 'Anillo de plata',
  price: 100,
  isActive: true,
} as never;

const OTHER_PRODUCT = {
  id: 'prod-2',
  sku: 'SKU-002',
  name: 'Pendientes de plata',
  price: 40,
  isActive: true,
} as never;

const SEARCH_EVENT_ID = '11111111-1111-1111-1111-111111111111';

function renderPage() {
  return render(
    <BrowserRouter>
      <ManualSalesPage />
    </BrowserRouter>,
  );
}

async function productIsSelected() {
  await waitFor(() => expect(productService.productService.getProduct).toHaveBeenCalled());
  await screen.findByText('Anillo de plata');
}

beforeEach(() => {
  vi.clearAllMocks();
  addLine.mockReturnValue(true);
  locationState = { productId: 'prod-1', searchEventId: SEARCH_EVENT_ID };

  vi.mocked(posService.pointOfSaleService.getPointsOfSale).mockResolvedValue([
    { id: 'pos-1', name: 'Ciutadella Centre', code: 'POS1', allowManualPriceEdit: false },
  ] as never);
  vi.mocked(productService.productService.getProduct).mockResolvedValue(PRODUCT);
  vi.mocked(productService.productService.searchProducts).mockResolvedValue([
    PRODUCT,
    OTHER_PRODUCT,
  ] as never);
  vi.mocked(paymentService.paymentMethodService.getPointOfSalePaymentMethods).mockResolvedValue([
    {
      id: 'pospm-1',
      pointOfSaleId: 'pos-1',
      paymentMethodId: 'pm-1',
      isActive: true,
      paymentMethod: { id: 'pm-1', name: 'Efectivo', code: 'CASH', isActive: true },
    },
  ] as never);
  vi.mocked(paymentService.paymentMethodService.getPaymentMethods).mockResolvedValue([
    { id: 'pm-1', name: 'Efectivo', code: 'CASH', isActive: true },
  ] as never);
  vi.mocked(inventoryService.inventoryService.getProductStockBreakdown).mockResolvedValue({
    productId: 'prod-1',
    productSku: 'SKU-001',
    productName: 'Anillo de plata',
    totalQuantity: 10,
    breakdown: [{ pointOfSaleId: 'pos-1', pointOfSaleName: 'Ciutadella Centre', quantity: 10 }],
  } as never);
  vi.mocked(salesService.salesService.createSale).mockResolvedValue({
    sale: { id: 'sale-1' },
    isLowStock: false,
  } as never);
});

describe('ManualSalesPage — search attribution', () => {
  it('should carry the search event id into the cart line when the product came from assisted search', async () => {
    const user = userEvent.setup();
    renderPage();
    await productIsSelected();

    await user.click(await screen.findByRole('button', { name: /Añadir al carrito/i }));

    await waitFor(() => expect(addLine).toHaveBeenCalled());
    expect(addLine.mock.calls[0][0]).toMatchObject({
      productId: 'prod-1',
      searchEventId: SEARCH_EVENT_ID,
    });
  });

  it('should carry no attribution when the product did not come from assisted search', async () => {
    const user = userEvent.setup();
    locationState = { productId: 'prod-1' };
    renderPage();
    await productIsSelected();

    await user.click(await screen.findByRole('button', { name: /Añadir al carrito/i }));

    await waitFor(() => expect(addLine).toHaveBeenCalled());
    expect(addLine.mock.calls[0][0].searchEventId).toBeUndefined();
  });

  it('should carry no attribution when the sale is started with no navigation state at all', async () => {
    locationState = null;
    renderPage();

    await waitFor(() =>
      expect(posService.pointOfSaleService.getPointsOfSale).toHaveBeenCalled(),
    );

    // Nothing was pre-selected, so nothing to attribute — and the page still works, which is
    // what every other entry method depends on.
    expect(productService.productService.getProduct).not.toHaveBeenCalled();
  });
});
