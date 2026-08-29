/**
 * Assisted Search Panel Tests (EP14 / C16)
 *
 * The panel's substance is not "does it render a list": it is that a search costs money, that
 * four different kinds of nothing must say four different things, and that the attribution has
 * to survive all the way to the till. Those are what these tests hold.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import { AssistedSalesSearchPage } from '../assisted';
import { aiSearchService } from '@/services/ai-search.service';
import * as pointOfSaleService from '@/services/point-of-sale.service';
import type {
  AssistedSearchOutcome,
  AssistedSearchResponse,
  AssistedSearchResult,
} from '@/types/ai-search.types';

vi.mock('@/services/ai-search.service', () => ({
  aiSearchService: {
    search: vi.fn(),
    reportSelection: vi.fn(),
  },
}));

vi.mock('@/services/point-of-sale.service', () => ({
  getPointsOfSale: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

const navigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

let role = 'Operator';
vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({ user: { userId: 'u-1', role } }),
}));

const POS_ONE = { id: 'pos-1', name: 'Ciutadella Centre', isActive: true } as never;
const POS_TWO = { id: 'pos-2', name: 'Fornells', isActive: true } as never;
const POS_INACTIVE = { id: 'pos-3', name: 'Cerrada', isActive: false } as never;

function result(overrides: Partial<AssistedSearchResult> = {}): AssistedSearchResult {
  return {
    productId: 'prod-1',
    sku: 'SKU-001',
    name: 'Anillo de plata',
    price: 39.9,
    quantityAtPointOfSale: 3,
    hasStock: true,
    primaryPhotoUrl: null,
    collectionName: null,
    score: 0.8,
    matchReasons: ['vector'],
    materials: ['plata'],
    familyId: null,
    variantLabel: null,
    ...overrides,
  };
}

function response(overrides: Partial<AssistedSearchResponse> = {}): AssistedSearchResponse {
  return {
    results: [result()],
    searchEventId: 'event-1',
    aiAvailable: true,
    lowConfidence: false,
    pointOfSaleId: 'pos-1',
    candidatesReturned: 12,
    survivedHydration: 1,
    ...overrides,
  };
}

function answers(payload: AssistedSearchResponse) {
  vi.mocked(aiSearchService.search).mockResolvedValue({ kind: 'ok', response: payload });
}

function answersWith(outcome: AssistedSearchOutcome) {
  vi.mocked(aiSearchService.search).mockResolvedValue(outcome);
}

function renderPanel() {
  return render(
    <BrowserRouter>
      <AssistedSalesSearchPage />
    </BrowserRouter>,
  );
}

async function ready() {
  await waitFor(() => expect(pointOfSaleService.getPointsOfSale).toHaveBeenCalled());
}

beforeEach(() => {
  vi.clearAllMocks();
  role = 'Operator';
  vi.mocked(pointOfSaleService.getPointsOfSale).mockResolvedValue([POS_ONE]);
  vi.mocked(aiSearchService.reportSelection).mockResolvedValue(undefined);
  answers(response());
});

describe('AssistedSalesSearchPage — cost of a search', () => {
  it('should not issue a search request when the operator types without submitting', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo de plata');

    // The candidate cache is keyed on the whole query string, so no prefix can ever hit it: a
    // debounced field would charge one embedding per pause and read at most one of them.
    expect(aiSearchService.search).not.toHaveBeenCalled();
  });

  it('should issue exactly one search request when the operator submits', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo de plata');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    await waitFor(() => expect(aiSearchService.search).toHaveBeenCalledTimes(1));
    expect(vi.mocked(aiSearchService.search).mock.calls[0][0]).toMatchObject({
      query: 'anillo de plata',
      pointOfSaleId: 'pos-1',
    });
  });

  it('should fill the field and search when an example query is activated', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.click(screen.getByRole('button', { name: /un anillo de plata para regalar/ }));

    await waitFor(() => expect(aiSearchService.search).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('¿Qué busca el cliente?')).toHaveValue(
      'un anillo de plata para regalar',
    );
  });

  it('should not issue a search request when a quick filter is toggled', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.click(screen.getByRole('button', { name: 'Plata' }));
    await user.click(screen.getByRole('button', { name: 'Perla' }));

    expect(aiSearchService.search).not.toHaveBeenCalled();
  });

  it('should allow selecting multiple materials in quick filters', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.click(screen.getByRole('button', { name: 'Plata' }));
    await user.click(screen.getByRole('button', { name: 'Perla' }));

    expect(screen.getByRole('button', { name: 'Plata' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Perla' })).toHaveAttribute('aria-pressed', 'true');

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'algo bonito');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    await waitFor(() => expect(aiSearchService.search).toHaveBeenCalled());
    // Canonical terms, not the displayed labels: a label would match nothing in the index.
    expect(vi.mocked(aiSearchService.search).mock.calls[0][0].materials).toEqual([
      'plata',
      'perla',
    ]);
  });

  it('should clear every active filter when the clear action is used', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.click(screen.getByRole('button', { name: 'Plata' }));
    await user.click(screen.getByRole('button', { name: 'Quitar filtros' }));

    expect(screen.getByRole('button', { name: 'Plata' })).toHaveAttribute('aria-pressed', 'false');
  });
});

describe('AssistedSalesSearchPage — results', () => {
  it('should render results with reason when search succeeds', async () => {
    const user = userEvent.setup();
    answers(response({ results: [result({ materials: ['plata', 'perla'] })] }));
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    const row = await screen.findByTestId('assisted-search-result');
    expect(within(row).getByText('Anillo de plata')).toBeInTheDocument();
    expect(within(row).getByText('SKU-001')).toBeInTheDocument();
    expect(within(row).getByText('Coincidencia semántica')).toBeInTheDocument();
    expect(within(row).getByText('plata')).toBeInTheDocument();
    expect(within(row).getByText('perla')).toBeInTheDocument();
    // The raw retriever signal is never shown: it is the constant "vector" for every result.
    expect(within(row).queryByText('vector')).not.toBeInTheDocument();
  });

  it('should render results in the order received', async () => {
    const user = userEvent.setup();
    // Deliberately a set whose order by price and by name both differ from the order of arrival,
    // so that a client-side sort could not pass this test by coincidence.
    answers(
      response({
        results: [
          result({ productId: 'p-1', sku: 'SKU-C', name: 'Zafiro', price: 90 }),
          result({ productId: 'p-2', sku: 'SKU-A', name: 'Alianza', price: 10 }),
          result({ productId: 'p-3', sku: 'SKU-B', name: 'Medalla', price: 50 }),
        ],
      }),
    );
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'algo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    const rows = await screen.findAllByTestId('assisted-search-result');
    expect(rows.map((r) => within(r).getByText(/Zafiro|Alianza|Medalla/).textContent)).toEqual([
      'Zafiro',
      'Alianza',
      'Medalla',
    ]);
  });

  it('should mark a result as out of stock when it has none', async () => {
    const user = userEvent.setup();
    answers(response({ results: [result({ hasStock: false, quantityAtPointOfSale: 0 })] }));
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    const row = await screen.findByTestId('assisted-search-result');
    // Kept and marked, never hidden: "we carry it, we are out of it" can still save a sale.
    expect(within(row).getByText('Sin existencias')).toBeInTheDocument();
  });

  it('should not render a size when the variant label is absent', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    await screen.findByTestId('assisted-search-result');
    expect(screen.queryByText(/^Talla /)).not.toBeInTheDocument();
  });

  it('should declare a short page when fewer results survive than requested', async () => {
    const user = userEvent.setup();
    answers(response({ results: [result()], candidatesReturned: 18, survivedHydration: 1 }));
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    const note = await screen.findByTestId('assisted-search-short-page');
    expect(note).toHaveTextContent('1 resultados');
    expect(note).toHaveTextContent('18 candidatos');
  });
});

describe('AssistedSalesSearchPage — the four ways of showing nothing', () => {
  async function searchWith(payload: AssistedSearchResponse) {
    const user = userEvent.setup();
    answers(payload);
    renderPanel();
    await ready();
    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'algo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));
  }

  it('should distinguish abstention from empty assortment', async () => {
    await searchWith(
      response({ results: [], lowConfidence: true, candidatesReturned: 0, survivedHydration: 0 }),
    );

    expect(await screen.findByText('No he encontrado nada que encaje')).toBeInTheDocument();
    expect(screen.queryByText('Nada de esto está en tu tienda')).not.toBeInTheDocument();
  });

  it('should say the shop carries none of it when candidates did not survive hydration', async () => {
    await searchWith(
      response({ results: [], lowConfidence: false, candidatesReturned: 24, survivedHydration: 0 }),
    );

    expect(await screen.findByText('Nada de esto está en tu tienda')).toBeInTheDocument();
    expect(screen.getByText(/24 piezas parecidas/)).toBeInTheDocument();
  });

  it('should show legacy results banner when ai is unavailable', async () => {
    await searchWith(response({ aiAvailable: false, candidatesReturned: 0, survivedHydration: 1 }));

    expect(await screen.findByText('Búsqueda asistida no disponible')).toBeInTheDocument();
    expect(
      screen.getByText('Estos resultados vienen de la búsqueda por texto.'),
    ).toBeInTheDocument();

    // The row states the same origin, so the operator can tell a degraded result from an
    // assisted one without scrolling back to the banner.
    const row = screen.getByTestId('assisted-search-result');
    expect(within(row).getByText('Búsqueda por texto')).toBeInTheDocument();
  });

  it('should show a rate limit message when the server answers 429', async () => {
    const user = userEvent.setup();
    answersWith({ kind: 'rate-limited' });
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'algo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    expect(await screen.findByText('Demasiadas búsquedas seguidas')).toBeInTheDocument();
    // A quota is the system protecting itself, not an outage. Saying the opposite would send the
    // operator looking for a fault that does not exist.
    expect(screen.queryByText('Búsqueda asistida no disponible')).not.toBeInTheDocument();
  });

  it('should report a forbidden point of sale as an access problem', async () => {
    const user = userEvent.setup();
    answersWith({ kind: 'forbidden' });
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'algo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    expect(await screen.findByText('No tienes acceso a esta tienda')).toBeInTheDocument();
  });
});

describe('AssistedSalesSearchPage — episode, selection and attribution', () => {
  it('should keep the search session id across reformulations in one panel visit', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    const field = screen.getByLabelText('¿Qué busca el cliente?');
    const button = screen.getByRole('button', { name: /^Buscar$/ });

    await user.type(field, 'anillo');
    await user.click(button);
    await waitFor(() => expect(aiSearchService.search).toHaveBeenCalledTimes(1));

    await user.clear(field);
    await user.type(field, 'anillo de plata');
    await user.click(button);
    await waitFor(() => expect(aiSearchService.search).toHaveBeenCalledTimes(2));

    const calls = vi.mocked(aiSearchService.search).mock.calls;
    expect(calls[0][0].searchSessionId).toBeTruthy();
    // One episode per visit: without this, every rephrasing counts as an abandoned query.
    expect(calls[1][0].searchSessionId).toBe(calls[0][0].searchSessionId);
  });

  it('should emit search event when a result is selected', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));
    await user.click(await screen.findByRole('button', { name: 'Seleccionar para venta' }));

    expect(aiSearchService.reportSelection).toHaveBeenCalledWith('event-1', 'prod-1');
  });

  it('should carry the search event id into the sale flow when a result is selected', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));
    await user.click(await screen.findByRole('button', { name: 'Seleccionar para venta' }));

    expect(navigate).toHaveBeenCalledWith('/sales/new', {
      state: { productId: 'prod-1', searchEventId: 'event-1' },
    });
  });

  it('should not block navigation when reporting the selection fails', async () => {
    const user = userEvent.setup();
    vi.mocked(aiSearchService.reportSelection).mockRejectedValue(new Error('telemetry down'));
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));
    await user.click(await screen.findByRole('button', { name: 'Seleccionar para venta' }));

    // The server stamps the moment, so the call leaves at the click and its outcome is nobody's
    // business but telemetry's.
    expect(navigate).toHaveBeenCalled();
  });

  it('should skip the selection report when no search event id was returned', async () => {
    const user = userEvent.setup();
    answers(response({ searchEventId: null }));
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));
    await user.click(await screen.findByRole('button', { name: 'Seleccionar para venta' }));

    expect(aiSearchService.reportSelection).not.toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith('/sales/new', {
      state: { productId: 'prod-1', searchEventId: undefined },
    });
  });
});

describe('AssistedSalesSearchPage — point of sale and role', () => {
  it('should hide the point of sale selector when the operator has a single assignment', async () => {
    renderPanel();
    await ready();

    await waitFor(() =>
      expect(screen.queryByLabelText('Punto de venta')).not.toBeInTheDocument(),
    );
  });

  it('should offer only active points of sale when several are available', async () => {
    vi.mocked(pointOfSaleService.getPointsOfSale).mockResolvedValue([
      POS_ONE,
      POS_TWO,
      POS_INACTIVE,
    ]);
    renderPanel();
    await ready();

    const selector = await screen.findByLabelText('Punto de venta');
    expect(selector).toBeInTheDocument();
    // An inactive shop is refused by the endpoint for every role, so offering it would be
    // offering a guaranteed error.
    expect(screen.queryByText('Cerrada')).not.toBeInTheDocument();
  });

  it('should show the funnel block to an administrator', async () => {
    const user = userEvent.setup();
    role = 'Administrator';
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    const funnel = await screen.findByTestId('assisted-search-funnel');
    await user.click(within(funnel).getByRole('button'));
    expect(within(funnel).getByText('Candidatos: 12')).toBeInTheDocument();
    expect(within(funnel).getByText('Supervivientes: 1')).toBeInTheDocument();
  });

  it('should clear the results when the point of sale changes', async () => {
    const user = userEvent.setup();
    vi.mocked(pointOfSaleService.getPointsOfSale).mockResolvedValue([POS_ONE, POS_TWO]);
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));
    await screen.findByTestId('assisted-search-result');

    await user.click(screen.getByLabelText('Punto de venta'));
    await user.click(await screen.findByRole('option', { name: 'Fornells' }));

    // Another shop is another assortment. Re-running here would charge an embedding the operator
    // never asked for, so the list is cleared and the next search is theirs to trigger.
    await waitFor(() =>
      expect(screen.queryByTestId('assisted-search-result')).not.toBeInTheDocument(),
    );
    expect(aiSearchService.search).toHaveBeenCalledTimes(1);
  });

  it('should ignore a stale response when the point of sale changed', async () => {
    const user = userEvent.setup();
    vi.mocked(pointOfSaleService.getPointsOfSale).mockResolvedValue([POS_ONE, POS_TWO]);

    // The first search resolves last, which is exactly the order that would let it overwrite the
    // second one's results if the panel did not guard against it.
    let releaseFirst: (value: AssistedSearchOutcome) => void = () => {};
    vi.mocked(aiSearchService.search)
      .mockImplementationOnce(
        () => new Promise<AssistedSearchOutcome>((resolve) => (releaseFirst = resolve)),
      )
      .mockResolvedValueOnce({
        kind: 'ok',
        response: response({
          results: [result({ productId: 'p-fornells', name: 'Collar de Fornells' })],
        }),
      });

    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    await user.click(screen.getByLabelText('Punto de venta'));
    await user.click(await screen.findByRole('option', { name: 'Fornells' }));

    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));
    expect(await screen.findByText('Collar de Fornells')).toBeInTheDocument();

    releaseFirst({
      kind: 'ok',
      response: response({ results: [result({ productId: 'p-stale', name: 'Resultado viejo' })] }),
    });

    await waitFor(() => expect(screen.queryByText('Resultado viejo')).not.toBeInTheDocument());
    expect(screen.getByText('Collar de Fornells')).toBeInTheDocument();
  });

  it('should hide the funnel block from an operator', async () => {
    const user = userEvent.setup();
    renderPanel();
    await ready();

    await user.type(screen.getByLabelText('¿Qué busca el cliente?'), 'anillo');
    await user.click(screen.getByRole('button', { name: /^Buscar$/ }));

    await screen.findByTestId('assisted-search-result');
    expect(screen.queryByTestId('assisted-search-funnel')).not.toBeInTheDocument();
  });
});
