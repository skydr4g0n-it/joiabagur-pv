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

  it('should show "Buscar con Ayuda" tile linking to the assisted search panel', () => {
    renderWithProviders(<SalesPage />);

    // Queried as a link rather than by text: each tile repeats its name in the title and in its
    // button, so a plain text query matches twice. The destination is also the half that matters
    // — a tile that renders but leads nowhere is the failure worth catching.
    const tile = screen.getByRole('link', { name: /Buscar con Ayuda/i });

    expect(tile).toBeInTheDocument();
    expect(tile).toHaveAttribute('href', '/sales/new/assisted');
  });

  it('should keep "Escanear Código" as the first entry option', () => {
    renderWithProviders(<SalesPage />);

    const tiles = screen
      .getAllByRole('link')
      .map((link) => link.getAttribute('href'))
      .filter((href) => href?.startsWith('/sales/new'));

    // The spec of sales-management pins scanning as the primary option, and adding a third tile
    // is exactly the kind of change that quietly reorders them.
    expect(tiles[0]).toBe('/sales/new/scan');
  });
});
