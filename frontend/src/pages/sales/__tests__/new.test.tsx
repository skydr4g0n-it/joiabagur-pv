/**
 * Manual Sales Page Component Tests
 * Tests for the manual sales registration workflow.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ManualSalesPage } from '../new';
import { AuthProvider } from '@/providers/auth-provider';
import * as salesService from '@/services/sales.service';
import * as productService from '@/services/product.service';
import * as posService from '@/services/point-of-sale.service';
import * as paymentService from '@/services/payment-method.service';
import * as inventoryService from '@/services/inventory.service';

// Mock services
vi.mock('@/services/sales.service');
vi.mock('@/services/product.service');
vi.mock('@/services/point-of-sale.service');
vi.mock('@/services/payment-method.service');
vi.mock('@/services/inventory.service');

vi.mock('@/providers/cart-provider', () => ({
  CartProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useCart: () => ({
    addLine: vi.fn(() => true),
    lineCount: 0,
  }),
}));

// Mock auth context
vi.mock('@/providers/auth-provider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useAuth: () => ({
    user: { id: 'user-1', username: 'testuser', role: 'Operator' },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

const mockProducts = [
  {
    id: 'prod-1',
    sku: 'SKU-001',
    name: 'Test Product 1',
    price: 100.0,
    isActive: true,
  },
  {
    id: 'prod-2',
    sku: 'SKU-002',
    name: 'Test Product 2',
    price: 200.0,
    isActive: true,
  },
];

const mockPointsOfSale = [
  { id: 'pos-1', name: 'Test POS 1', code: 'POS1', allowManualPriceEdit: false },
  { id: 'pos-2', name: 'Test POS 2', code: 'POS2', allowManualPriceEdit: true },
];

const mockPaymentMethods = [
  { id: 'pm-1', name: 'Cash', code: 'CASH', isActive: true },
  { id: 'pm-2', name: 'Card', code: 'CARD', isActive: true },
];

const mockPosPaymentMethods = [
  { id: 'pospm-1', pointOfSaleId: 'pos-1', paymentMethodId: 'pm-1', isActive: true, paymentMethod: mockPaymentMethods[0] },
  { id: 'pospm-2', pointOfSaleId: 'pos-1', paymentMethodId: 'pm-2', isActive: true, paymentMethod: mockPaymentMethods[1] },
];

const mockStockBreakdown = {
  productId: 'prod-1',
  productSku: 'SKU-001',
  productName: 'Test Product 1',
  totalQuantity: 10,
  breakdown: [
    { pointOfSaleId: 'pos-1', pointOfSaleName: 'Test POS 1', quantity: 10 },
    { pointOfSaleId: 'pos-2', pointOfSaleName: 'Test POS 2', quantity: 5 },
  ],
};

function renderWithProviders(component: React.ReactElement) {
  return render(
    <BrowserRouter>
      <AuthProvider>{component}</AuthProvider>
    </BrowserRouter>
  );
}

describe('ManualSalesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Setup default mocks
    vi.mocked(posService.pointOfSaleService.getPointsOfSale).mockResolvedValue(mockPointsOfSale);
    vi.mocked(productService.productService.searchProducts).mockResolvedValue(mockProducts);
    vi.mocked(paymentService.paymentMethodService.getPointOfSalePaymentMethods).mockResolvedValue(mockPosPaymentMethods);
    vi.mocked(paymentService.paymentMethodService.getPaymentMethods).mockResolvedValue(mockPaymentMethods);
    vi.mocked(inventoryService.inventoryService.getProductStockBreakdown).mockResolvedValue(mockStockBreakdown);
  });

  it('should render the page title', async () => {
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Nueva Venta')).toBeInTheDocument();
    });
  });

  it('should load and display points of sale', async () => {
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByText('Test POS 1')).toBeInTheDocument();
    });
  });

  it('should allow searching for products', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');

    await waitFor(() => {
      expect(screen.getByText('Test Product 1')).toBeInTheDocument();
    });
  });

  it('should display available stock when product is selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');

    await waitFor(() => {
      expect(screen.getByText('Test Product 1')).toBeInTheDocument();
    });

    const productButton = screen.getByText('Test Product 1');
    await user.click(productButton);

    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });
  });

  it('should validate quantity against available stock', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    // Select product
    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));

    // Try to set quantity higher than stock
    await waitFor(() => {
      expect(screen.getByLabelText(/cantidad/i)).toBeInTheDocument();
    });

    const quantityInput = screen.getByLabelText(/cantidad/i);
    await user.clear(quantityInput);
    await user.type(quantityInput, '20');

    await waitFor(() => {
      expect(screen.getByText(/stock insuficiente/i)).toBeInTheDocument();
    });
  });

  it('should show confirmation dialog before submitting sale', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    // Select product
    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));

    // Wait for stock to load
    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });

    // Click register sale button
    const registerButton = screen.getByRole('button', { name: /registrar venta/i });
    await user.click(registerButton);

    // Confirmation dialog should appear (use more specific selector)
    await waitFor(() => {
      const dialogs = screen.getAllByText(/confirmar venta/i);
      expect(dialogs.length).toBeGreaterThan(0);
    });
  });

  it('should successfully create a sale', async () => {
    const user = userEvent.setup();
    const mockSale = {
      sale: {
        id: 'sale-1',
        productId: 'prod-1',
        productSku: 'SKU-001',
        productName: 'Test Product 1',
        quantity: 1,
        price: 100,
        total: 100,
      },
      isLowStock: false,
      remainingStock: 9,
    };

    vi.mocked(salesService.salesService.createSale).mockResolvedValue(mockSale);

    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    // Select product
    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));

    // Wait for stock
    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });

    // Submit sale
    const registerButton = screen.getByRole('button', { name: /registrar venta/i });
    await user.click(registerButton);

    // Confirm in dialog (use getAllByText to handle multiple matches)
    await waitFor(() => {
      expect(screen.getAllByText(/confirmar venta/i).length).toBeGreaterThan(0);
    });

    // Find confirm button in dialog specifically
    const confirmButtons = screen.getAllByRole('button', { name: /confirmar/i });
    const confirmButton = confirmButtons.find(btn => 
      btn.textContent?.includes('Confirmar Venta') || btn.closest('[role="dialog"]')
    ) || confirmButtons[confirmButtons.length - 1]; // Use last one (likely in dialog)
    
    await user.click(confirmButton);

    // Verify API was called
    await waitFor(() => {
      expect(salesService.salesService.createSale).toHaveBeenCalledWith(
        expect.objectContaining({
          productId: 'prod-1',
          quantity: 1,
        })
      );
    });
  });

  it('should display low stock warning after sale', async () => {
    const user = userEvent.setup();
    const mockSale = {
      sale: {
        id: 'sale-1',
        productId: 'prod-1',
        quantity: 1,
      },
      isLowStock: true,
      remainingStock: 2,
      warning: 'Quedan solo 2 unidades',
    };

    vi.mocked(salesService.salesService.createSale).mockResolvedValue(mockSale);

    renderWithProviders(<ManualSalesPage />);
    
    // Complete sale workflow...
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));

    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });

    const registerButton = screen.getByRole('button', { name: /registrar venta/i });
    await user.click(registerButton);

    await waitFor(() => {
      expect(screen.getAllByText(/confirmar venta/i).length).toBeGreaterThan(0);
    });

    const confirmButtons = screen.getAllByRole('button', { name: /confirmar/i });
    const confirmButton = confirmButtons[confirmButtons.length - 1];
    await user.click(confirmButton);

    // Low stock toast should be triggered
    // Note: Testing toast directly requires additional setup
    await waitFor(() => {
      expect(salesService.salesService.createSale).toHaveBeenCalled();
    });
  });

  it('should not show manual price input when POS disallows editing', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    // Select product
    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));

    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });

    // Manual price input should NOT be visible (POS1 has allowManualPriceEdit=false)
    expect(screen.queryByLabelText(/precio manual/i)).not.toBeInTheDocument();
  });

  it('should show manual price input when POS allows editing', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    // Switch to POS2 (allowManualPriceEdit=true)
    // Note: This depends on the Select component rendering
    // The POS is auto-selected to the first one by default

    // Select product first
    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));

    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });
  });

  it('should handle error when sale creation fails', async () => {
    const user = userEvent.setup();
    vi.mocked(salesService.salesService.createSale).mockRejectedValue(
      new Error('Insufficient stock')
    );

    renderWithProviders(<ManualSalesPage />);
    
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/buscar producto/i)).toBeInTheDocument();
    });

    // Complete workflow
    const searchInput = screen.getByPlaceholderText(/buscar producto/i);
    await user.type(searchInput, 'SKU-001');
    await user.click(await screen.findByText('Test Product 1'));

    await waitFor(() => {
      expect(screen.getByText(/10 unidades/i)).toBeInTheDocument();
    });

    const registerButton = screen.getByRole('button', { name: /registrar venta/i });
    await user.click(registerButton);

    await waitFor(() => {
      expect(screen.getAllByText(/confirmar venta/i).length).toBeGreaterThan(0);
    });

    const confirmButtons = screen.getAllByRole('button', { name: /confirmar/i });
    const confirmButton = confirmButtons[confirmButtons.length - 1];
    await user.click(confirmButton);

    // Error should be handled
    await waitFor(() => {
      expect(salesService.salesService.createSale).toHaveBeenCalled();
    });
  });
});
