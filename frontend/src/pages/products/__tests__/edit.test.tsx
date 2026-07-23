import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ROUTES } from '@/routing/routes';

vi.mock('@/services/product.service', () => ({
  productService: {
    getProduct: vi.fn(),
    getCollections: vi.fn().mockResolvedValue([]),
    updateProduct: vi.fn(),
  },
}));

vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({
    user: { id: 'user-1', username: 'testadmin', role: 'Administrator' },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock('@/services/api.service', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('@/components/ui/sonner', () => ({
  Toaster: () => null,
}));

function renderEditPage(productId: string = 'test-id') {
  const { ProductEditPage } = vi.requireActual<typeof import('../edit')>('../edit');
  return render(
    <MemoryRouter initialEntries={[`/products/${productId}/edit`]}>
      <Routes>
        <Route path="/products/:productId/edit" element={<ProductEditPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProductEditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show loading state initially', () => {
    const { productService } = vi.importActual<typeof import('@/services/product.service')>('@/services/product.service');
    vi.mocked(productService.getProduct).mockReturnValue(new Promise(() => {}));

    renderEditPage();
    expect(screen.getByText('Cargando producto...')).toBeInTheDocument();
  });

  it('should render QR code section for product with SKU', async () => {
    const { productService } = vi.importActual<typeof import('@/services/product.service')>('@/services/product.service');
    vi.mocked(productService.getProduct).mockResolvedValue({
      id: 'test-id',
      sku: 'TEST-SKU-001',
      name: 'Test Product',
      description: 'A test product',
      price: 100,
      collectionId: undefined,
      collectionName: undefined,
      isActive: true,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-01T00:00:00Z',
      photos: [],
    });

    const apiClient = vi.importActual<typeof import('@/services/api.service')>('@/services/api.service');
    vi.mocked(apiClient.default.get).mockResolvedValue({ data: '<svg xmlns="http://www.w3.org/2000/svg"><rect width="150" height="150"/></svg>' });

    renderEditPage();

    await waitFor(() => {
      expect(screen.getByText('Código QR')).toBeInTheDocument();
      expect(screen.getByText('Código de Barras')).toBeInTheDocument();
    });
  });

  it('should render Code128 barcode section for product with SKU', async () => {
    const { productService } = vi.importActual<typeof import('@/services/product.service')>('@/services/product.service');
    vi.mocked(productService.getProduct).mockResolvedValue({
      id: 'test-id',
      sku: 'TEST-SKU-001',
      name: 'Test Product',
      description: 'A test product',
      price: 100,
      collectionId: undefined,
      collectionName: undefined,
      isActive: true,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-01T00:00:00Z',
      photos: [],
    });

    const apiClient = vi.importActual<typeof import('@/services/api.service')>('@/services/api.service');
    vi.mocked(apiClient.default.get).mockResolvedValue({ data: '<svg xmlns="http://www.w3.org/2000/svg"><rect width="150" height="150"/></svg>' });

    renderEditPage();

    await waitFor(() => {
      expect(screen.getByText('Código de Barras')).toBeInTheDocument();
      expect(screen.getByText('Descargar código de barras')).toBeInTheDocument();
    });
  });

  it('should show placeholder when product has no SKU', async () => {
    const { productService } = vi.importActual<typeof import('@/services/product.service')>('@/services/product.service');
    vi.mocked(productService.getProduct).mockResolvedValue({
      id: 'test-id',
      sku: '',
      name: 'No SKU Product',
      description: '',
      price: 50,
      collectionId: undefined,
      collectionName: undefined,
      isActive: true,
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-01T00:00:00Z',
      photos: [],
    });

    renderEditPage();

    await waitFor(() => {
      expect(screen.getByText('Genere un SKU para ver los códigos')).toBeInTheDocument();
    });
  });
});
