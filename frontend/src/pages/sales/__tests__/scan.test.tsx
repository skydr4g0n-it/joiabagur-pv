import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '@/providers/auth-provider';

vi.mock('@/providers/auth-provider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useAuth: () => ({
    user: { id: 'user-1', username: 'testuser', role: 'Operator' },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

vi.mock('@/services/barcode-scanning.service', () => ({
  BarcodeScanningService: vi.fn().mockImplementation(() => ({
    isCompatible: () => true,
    startCamera: vi.fn(),
    stopCamera: vi.fn(),
    continuousScan: vi.fn(),
    stopContinuousScan: vi.fn(),
    toggleFlash: vi.fn(),
    resetDecodeHistory: vi.fn(),
  })),
}));

vi.mock('@/services/product.service', () => ({
  productService: {
    searchProducts: vi.fn(),
  },
}));

function renderWithProviders(component: React.ReactElement) {
  return render(
    <BrowserRouter>
      <AuthProvider>{component}</AuthProvider>
    </BrowserRouter>,
  );
}

describe('ScanningPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render loading state initially', async () => {
    const { default: ScanningPage } = await import('../scan');
    renderWithProviders(<ScanningPage />);

    expect(screen.getByText('Iniciando cámara...')).toBeInTheDocument();
  });

  it('should show manual SKU input fallback after initialization', async () => {
    const { default: ScanningPage } = await import('../scan');
    renderWithProviders(<ScanningPage />);

    const manualInput = screen.getByPlaceholderText('Ingresa SKU manualmente...');
    expect(manualInput).toBeInTheDocument();
  });
});
