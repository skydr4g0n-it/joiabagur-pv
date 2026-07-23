import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SalesPage } from '../index';

vi.mock('@/providers/cart-provider', () => ({
  useCart: () => ({ lineCount: 0 }),
}));

vi.mock('@/providers/auth-provider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useAuth: () => ({
    user: { id: 'user-1', username: 'testuser', role: 'Operator' },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

function renderWithProviders(component: React.ReactElement) {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>,
  );
}

describe('SalesPage', () => {
  it('should show "Escanear Código" tile', () => {
    renderWithProviders(<SalesPage />);
    expect(screen.getByText('Escanear Código')).toBeInTheDocument();
  });

  it('should show "Registro Manual" tile', () => {
    renderWithProviders(<SalesPage />);
    expect(screen.getByText('Registro Manual')).toBeInTheDocument();
  });

  it('should NOT show "Reconocimiento de Imagen"', () => {
    renderWithProviders(<SalesPage />);
    expect(screen.queryByText('Reconocimiento de Imagen')).not.toBeInTheDocument();
  });
});
