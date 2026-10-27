/**
 * Sales Service (EP3)
 * Handles sales registration and history.
 */

import apiClient from './api.service';
import type {
  CreateSaleRequest,
  CreateSaleResponse,
  CreateBulkSalesRequest,
  CreateBulkSalesResponse,
  Sale,
  SalesHistoryFilterRequest,
  SalesHistoryResponse,
} from '@/types/sales.types';

const SALES_ENDPOINT = '/sales';

/**
 * Sales API operations.
 */
export const salesService = {
  /**
   * Creates a new sale.
   */
  createSale: async (request: CreateSaleRequest): Promise<CreateSaleResponse> => {
    const response = await apiClient.post<CreateSaleResponse>(SALES_ENDPOINT, request);
    return response.data;
  },

  /**
   * Gets a sale by ID.
   */
  getSaleById: async (id: string): Promise<Sale> => {
    const response = await apiClient.get<Sale>(`${SALES_ENDPOINT}/${id}`);
    return response.data;
  },

  /**
   * Gets sales history with filters.
   */
  getSalesHistory: async (filters: SalesHistoryFilterRequest): Promise<SalesHistoryResponse> => {
    const params = new URLSearchParams();
    
    if (filters.startDate) params.append('startDate', filters.startDate);
    if (filters.endDate) params.append('endDate', filters.endDate);
    if (filters.pointOfSaleId) params.append('pointOfSaleId', filters.pointOfSaleId);
    if (filters.productId) params.append('productId', filters.productId);
    if (filters.userId) params.append('userId', filters.userId);
    if (filters.paymentMethodId) params.append('paymentMethodId', filters.paymentMethodId);
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.pageSize) params.append('pageSize', filters.pageSize.toString());

    const response = await apiClient.get<SalesHistoryResponse>(`${SALES_ENDPOINT}?${params.toString()}`);
    return response.data;
  },

  /**
   * Gets the photo URL for a sale.
   */
  getSalePhotoUrl: (saleId: string): string => {
    return `${apiClient.defaults.baseURL}${SALES_ENDPOINT}/${saleId}/photo/file`;
  },

  /**
   * Creates bulk sales from cart lines.
   */
  createBulkSales: async (
    request: CreateBulkSalesRequest,
    idempotencyKey?: string,
  ): Promise<CreateBulkSalesResponse> => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    const response = await apiClient.post<CreateBulkSalesResponse>(
      `${SALES_ENDPOINT}/bulk`,
      request,
      { headers },
    );
    return response.data;
  },
};

export default salesService;
