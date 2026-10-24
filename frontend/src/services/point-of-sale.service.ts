/**
 * Point of Sale Service - EP8
 * API service for point of sale management operations
 */

import { apiClient } from './api.service';
import type {
  PointOfSale,
  CreatePointOfSaleRequest,
  UpdatePointOfSaleRequest,
  UserPointOfSale,
} from '@/types/point-of-sale.types';
import type { PointOfSalePaymentMethod } from '@/types/payment-method.types';
import type { CommissionTier, CommissionTierInput } from '@/types/commission-tier.types';

/**
 * Get all points of sale
 * Admins get all, operators get only their assigned ones
 */
export async function getPointsOfSale(): Promise<PointOfSale[]> {
  const response = await apiClient.get<PointOfSale[]>('/point-of-sales');
  return response.data;
}

/**
 * Get point of sale by ID
 */
export async function getPointOfSale(id: string): Promise<PointOfSale> {
  const response = await apiClient.get<PointOfSale>(`/point-of-sales/${id}`);
  return response.data;
}

/**
 * Create a new point of sale
 */
export async function createPointOfSale(
  request: CreatePointOfSaleRequest
): Promise<PointOfSale> {
  const response = await apiClient.post<PointOfSale>('/point-of-sales', request);
  return response.data;
}

/**
 * Update an existing point of sale
 */
export async function updatePointOfSale(
  id: string,
  request: UpdatePointOfSaleRequest
): Promise<PointOfSale> {
  const response = await apiClient.put<PointOfSale>(`/point-of-sales/${id}`, request);
  return response.data;
}

/**
 * Change point of sale status (activate/deactivate)
 */
export async function changePointOfSaleStatus(
  id: string,
  isActive: boolean
): Promise<PointOfSale> {
  const response = await apiClient.patch<PointOfSale>(
    `/point-of-sales/${id}/status`,
    { isActive }
  );
  return response.data;
}

/**
 * Get operators assigned to a point of sale
 */
export async function getPointOfSaleOperators(
  pointOfSaleId: string
): Promise<UserPointOfSale[]> {
  const response = await apiClient.get<UserPointOfSale[]>(
    `/point-of-sales/${pointOfSaleId}/operators`
  );
  return response.data;
}

/**
 * Assign operator to point of sale
 */
export async function assignOperatorToPointOfSale(
  pointOfSaleId: string,
  userId: string
): Promise<UserPointOfSale> {
  const response = await apiClient.post<UserPointOfSale>(
    `/point-of-sales/${pointOfSaleId}/operators/${userId}`
  );
  return response.data;
}

/**
 * Unassign operator from point of sale
 */
export async function unassignOperatorFromPointOfSale(
  pointOfSaleId: string,
  userId: string
): Promise<void> {
  await apiClient.delete(`/point-of-sales/${pointOfSaleId}/operators/${userId}`);
}

/**
 * Get payment methods assigned to a point of sale
 */
export async function getPointOfSalePaymentMethods(
  pointOfSaleId: string,
  includeInactive = false
): Promise<PointOfSalePaymentMethod[]> {
  const response = await apiClient.get<PointOfSalePaymentMethod[]>(
    `/point-of-sales/${pointOfSaleId}/payment-methods?includeInactive=${includeInactive}`
  );
  return response.data;
}

/**
 * Assign payment method to point of sale
 */
export async function assignPaymentMethodToPointOfSale(
  pointOfSaleId: string,
  paymentMethodId: string
): Promise<PointOfSalePaymentMethod> {
  const response = await apiClient.post<PointOfSalePaymentMethod>(
    `/point-of-sales/${pointOfSaleId}/payment-methods/${paymentMethodId}`
  );
  return response.data;
}

/**
 * Unassign payment method from point of sale
 */
export async function unassignPaymentMethodFromPointOfSale(
  pointOfSaleId: string,
  paymentMethodId: string
): Promise<void> {
  await apiClient.delete(
    `/point-of-sales/${pointOfSaleId}/payment-methods/${paymentMethodId}`
  );
}

/**
 * Change payment method assignment status
 */
export async function changePaymentMethodAssignmentStatus(
  pointOfSaleId: string,
  paymentMethodId: string,
  isActive: boolean
): Promise<PointOfSalePaymentMethod> {
  const response = await apiClient.patch<PointOfSalePaymentMethod>(
    `/point-of-sales/${pointOfSaleId}/payment-methods/${paymentMethodId}/status`,
    { isActive }
  );
  return response.data;
}

export async function getCommissionTiers(pointOfSaleId: string): Promise<CommissionTier[]> {
  const response = await apiClient.get<CommissionTier[]>(
    `/point-of-sales/${pointOfSaleId}/commission-tiers`
  );
  return response.data;
}

export async function replaceCommissionTiers(
  pointOfSaleId: string,
  tiers: CommissionTierInput[]
): Promise<CommissionTier[]> {
  const response = await apiClient.put<CommissionTier[]>(
    `/point-of-sales/${pointOfSaleId}/commission-tiers`,
    { tiers }
  );
  return response.data;
}

export const pointOfSaleService = {
  getPointsOfSale,
  getPointOfSale,
  createPointOfSale,
  updatePointOfSale,
  changePointOfSaleStatus,
  getPointOfSaleOperators,
  assignOperatorToPointOfSale,
  unassignOperatorFromPointOfSale,
  getPointOfSalePaymentMethods,
  assignPaymentMethodToPointOfSale,
  unassignPaymentMethodFromPointOfSale,
  changePaymentMethodAssignmentStatus,
  getCommissionTiers,
  replaceCommissionTiers,
};
