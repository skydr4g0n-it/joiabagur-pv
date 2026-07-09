import { describe, expect, it, vi, beforeEach } from 'vitest';
import apiClient from './api.service';
import { inventoryMovementReportService } from './inventory-movement-report.service';

vi.mock('./api.service', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    warning: vi.fn(),
  },
}));

const mockedGet = vi.mocked(apiClient.get);

describe('inventoryMovementReportService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should include output model and product search when requesting report', async () => {
    mockedGet.mockResolvedValueOnce({ data: { items: [], totalCount: 0, page: 1, pageSize: 20, totalPages: 0 } });

    await inventoryMovementReportService.getReport({
      outputModel: 'detail',
      startDate: '2025-01-01',
      endDate: '2025-01-31',
      productSearch: 'JOY-001',
      page: 1,
      pageSize: 20,
    });

    expect(mockedGet).toHaveBeenCalledWith('/reports/inventory-movements', {
      params: {
        outputModel: 'detail',
        startDate: '2025-01-01',
        endDate: '2025-01-31',
        productSearch: 'JOY-001',
        page: 1,
        pageSize: 20,
      },
    });
  });

  it('should include selected output model and product search when exporting', async () => {
    const blob = new Blob();
    mockedGet.mockResolvedValueOnce({ data: blob });

    const result = await inventoryMovementReportService.exportReport({
      outputModel: 'summary',
      startDate: '2025-01-01',
      endDate: '2025-01-31',
      pointOfSaleId: 'pos-1',
      productSearch: 'ring',
      sortBy: 'difference',
      sortDirection: 'desc',
    });

    expect(result).toBe(blob);
    expect(mockedGet).toHaveBeenCalledWith('/reports/inventory-movements/export', {
      params: {
        outputModel: 'summary',
        startDate: '2025-01-01',
        endDate: '2025-01-31',
        pointOfSaleId: 'pos-1',
        productSearch: 'ring',
        sortBy: 'difference',
        sortDirection: 'desc',
      },
      responseType: 'blob',
    });
  });
});
