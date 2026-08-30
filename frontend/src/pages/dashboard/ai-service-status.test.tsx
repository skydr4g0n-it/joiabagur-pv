import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DashboardPage } from './page';
import type { AiHealthOutcome } from '@/types/ai-health.types';
import type { DashboardStats, PaginatedLowStockResult } from '@/types/dashboard.types';

/**
 * AI service status card on the administrator dashboard (EP11 / C17).
 *
 * Every service this page reaches is mocked with `vi.mock`, not left to the request
 * interceptor. The interceptor here runs with `onUnhandledRequest: 'warn'`, so a call with no
 * handler prints a warning and resolves to nothing — a test can pass having asserted nothing at
 * all. Mocking the module makes the absence of a call a failure instead of a silence.
 */

const mockUseAuth = vi.fn();
const mockGetHealth = vi.fn();

vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock('@/services/ai-health.service', () => ({
  aiHealthService: { getHealth: (...args: unknown[]) => mockGetHealth(...args) },
}));

const emptyStats: DashboardStats = {
  salesTodayTotal: 0,
  salesTodayCount: 0,
  monthlyRevenue: 0,
  previousYearMonthlyRevenue: 0,
  monthlyReturnsCount: 0,
  monthlyReturnsTotal: 0,
  returnCategoryDistribution: [],
} as unknown as DashboardStats;

const emptyLowStock: PaginatedLowStockResult = {
  items: [],
  totalCount: 0,
  page: 1,
  pageSize: 10,
} as unknown as PaginatedLowStockResult;

vi.mock('@/services/dashboard.service', () => ({
  dashboardService: {
    getStats: vi.fn(() => Promise.resolve(emptyStats)),
    getLowStock: vi.fn(() => Promise.resolve(emptyLowStock)),
  },
}));

vi.mock('@/services/sales.service', () => ({
  salesService: {
    getSalesHistory: vi.fn(() => Promise.resolve({ sales: [], totalCount: 0 })),
  },
}));

vi.mock('@/services/inventory.service', () => ({
  inventoryService: {
    getStockByPointOfSale: vi.fn(() => Promise.resolve([])),
  },
}));

const healthy: AiHealthOutcome = {
  kind: 'ok',
  report: {
    status: 'OK',
    version: '0.1.0',
    database: 'ok',
    provider: 'configured',
    index: {
      documents: 1200,
      model: 'openai/text-embedding-3-small',
      configuredModel: 'openai/text-embedding-3-small',
      status: 'ok',
    },
  },
};

function asAdministrator() {
  mockUseAuth.mockReturnValue({
    user: {
      userId: '1',
      username: 'admin',
      firstName: 'Admin',
      lastName: 'User',
      role: 'Administrator',
    },
    isAuthenticated: true,
    isLoading: false,
  });
}

function asOperator() {
  mockUseAuth.mockReturnValue({
    user: {
      userId: '2',
      username: 'operator',
      firstName: 'Op',
      lastName: 'User',
      role: 'Operator',
      assignedPointOfSales: [
        { pointOfSaleId: 'pos-1', name: 'Tienda 1', code: 'T1', assignedAt: '', isActive: true },
      ],
    },
    isAuthenticated: true,
    isLoading: false,
  });
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe('AI service status card', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetHealth.mockResolvedValue(healthy);
  });

  it('should show ai service status card when user is administrator', async () => {
    asAdministrator();

    renderDashboard();

    expect(await screen.findByText('Servicio de IA')).toBeInTheDocument();
    expect(await screen.findByText('Accesible')).toBeInTheDocument();
    // Regex rather than a literal: the thousands separator es-ES applies at this magnitude is
    // ICU's business, and asserting on it would make this test about number formatting.
    expect(await screen.findByText(/^1[.,\s]?200$/)).toBeInTheDocument();
    expect(await screen.findByText('Credencial configurada')).toBeInTheDocument();
  });

  it('should not show ai service status card when user is operator', async () => {
    asOperator();

    renderDashboard();

    // The report describes infrastructure — how many documents are indexed, whether a provider
    // credential is set. None of it is an operator's concern, and the endpoint behind it
    // rejects them anyway.
    expect(screen.queryByText('Servicio de IA')).not.toBeInTheDocument();
    expect(mockGetHealth).not.toHaveBeenCalled();
  });

  it('should render model mismatch as an error state', async () => {
    asAdministrator();
    mockGetHealth.mockResolvedValue({
      kind: 'ok',
      report: {
        ...healthy.kind === 'ok' ? healthy.report : {},
        status: 'degraded',
        index: {
          documents: 1200,
          model: 'openai/text-embedding-3-large',
          configuredModel: 'openai/text-embedding-3-small',
          status: 'model_mismatch',
        },
      },
    } as AiHealthOutcome);

    renderDashboard();

    // Named in text, not signalled by colour alone: a red badge tells a reader something is
    // wrong, and this condition needs them to know WHICH of the two models to change.
    const alert = await screen.findByText('Modelo de embeddings incompatible con el índice');
    expect(alert).toBeInTheDocument();
    expect(await screen.findByText('openai/text-embedding-3-large')).toBeInTheDocument();
    expect(await screen.findByText('openai/text-embedding-3-small')).toBeInTheDocument();
  });

  it('should report an unreachable ai service without breaking the rest of the dashboard', async () => {
    asAdministrator();
    mockGetHealth.mockResolvedValue({
      kind: 'unreachable',
      message: 'El servicio de IA no responde.',
    } satisfies AiHealthOutcome);

    renderDashboard();

    expect(await screen.findByText('El servicio de IA no responde')).toBeInTheDocument();
    // The rest of the page is still there. An AI outage is one card, not a blank dashboard.
    expect(screen.getByText('Ventas hoy')).toBeInTheDocument();
    expect(screen.getByText('Stock crítico')).toBeInTheDocument();
  });
});
