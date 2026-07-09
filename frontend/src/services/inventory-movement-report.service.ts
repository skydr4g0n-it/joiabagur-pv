import apiClient from './api.service';
import { toast } from 'sonner';
import type {
  InventoryMovementReportFilter,
  InventoryMovementReportResponse,
} from '@/types/inventory-movement-report.types';

const ENDPOINTS = {
  REPORT: '/reports/inventory-movements',
  EXPORT: '/reports/inventory-movements/export',
} as const;

function buildParams(filters: InventoryMovementReportFilter): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  if (filters.outputModel) params.outputModel = filters.outputModel;
  if (filters.startDate) params.startDate = filters.startDate;
  if (filters.endDate) params.endDate = filters.endDate;
  if (filters.pointOfSaleId) params.pointOfSaleId = filters.pointOfSaleId;
  if (filters.productSearch) params.productSearch = filters.productSearch;
  if (filters.page) params.page = filters.page;
  if (filters.pageSize) params.pageSize = filters.pageSize;
  if (filters.sortBy) params.sortBy = filters.sortBy;
  if (filters.sortDirection) params.sortDirection = filters.sortDirection;
  return params;
}

export const inventoryMovementReportService = {
  getReport: async (filters: InventoryMovementReportFilter): Promise<InventoryMovementReportResponse> => {
    const response = await apiClient.get<InventoryMovementReportResponse>(
      ENDPOINTS.REPORT,
      { params: buildParams(filters) },
    );
    return response.data;
  },

  exportReport: async (filters: InventoryMovementReportFilter): Promise<Blob> => {
    try {
      const response = await apiClient.get(ENDPOINTS.EXPORT, {
        params: buildParams(filters),
        responseType: 'blob',
      });
      return response.data as Blob;
    } catch (error: unknown) {
      const err = error as { statusCode?: number; response?: { status?: number; data?: Blob } };
      if (err.response?.status === 409 || err.statusCode === 409) {
        const blob = err.response?.data;
        if (blob) {
          const text = await blob.text();
          try {
            const json = JSON.parse(text);
            toast.warning(json.message ?? `Hay ${json.totalCount?.toLocaleString('es-ES')} filas. Ajuste los filtros.`);
          } catch {
            toast.warning('Más de 50.000 filas en el resultado. Ajuste los filtros para exportar.');
          }
        }
        throw error;
      }
      throw error;
    }
  },
};
