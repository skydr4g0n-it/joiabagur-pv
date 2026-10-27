import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NewReturnPage } from '../new';

vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({ user: { role: 'Operator' } }),
}));
vi.mock('@/services/returns.service');
vi.mock('@/services/product.service');
vi.mock('@/services/point-of-sale.service', () => ({
  pointOfSaleService: {
    getPointsOfSale: vi.fn().mockResolvedValue([]),
  },
}));
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

describe('NewReturnPage gift card guard', () => {
  beforeEach(() => vi.clearAllMocks());

  it('should block the classic return action when the sale is linked to a gift card', () => {
    render(
      <BrowserRouter>
        <NewReturnPage />
      </BrowserRouter>,
    );
    expect(
      screen.getByText(/ventas cubiertas por tarjeta regalo/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/un solo uso por tarjeta/i)).toBeInTheDocument();
  });
});
