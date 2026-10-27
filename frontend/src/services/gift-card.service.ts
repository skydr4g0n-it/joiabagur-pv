/**
 * Gift card API service
 */

import apiClient from './api.service';
import type {
  GiftCardByCode,
  GiftCardDetail,
  GiftCardListResponse,
  IssueGiftCardRequest,
  IssueGiftCardResponse,
  ReassignGiftCardRequest,
  ExchangeGiftCardRequest,
  ExchangeGiftCardResponse,
} from '@/types/gift-card.types';

const ENDPOINT = '/gift-cards';

export const giftCardService = {
  list: async (page = 1, pageSize = 50): Promise<GiftCardListResponse> => {
    const response = await apiClient.get<GiftCardListResponse>(
      `${ENDPOINT}?page=${page}&pageSize=${pageSize}`,
    );
    return response.data;
  },

  getById: async (id: string): Promise<GiftCardDetail> => {
    const response = await apiClient.get<GiftCardDetail>(`${ENDPOINT}/${id}`);
    return response.data;
  },

  getByCode: async (code: string, pointOfSaleId: string): Promise<GiftCardByCode> => {
    const response = await apiClient.get<GiftCardByCode>(
      `${ENDPOINT}/by-code/${encodeURIComponent(code)}?pointOfSaleId=${pointOfSaleId}`,
    );
    return response.data;
  },

  issue: async (
    request: IssueGiftCardRequest,
    idempotencyKey?: string,
  ): Promise<IssueGiftCardResponse> => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    const response = await apiClient.post<IssueGiftCardResponse>(ENDPOINT, request, { headers });
    return response.data;
  },

  reassign: async (id: string, request: ReassignGiftCardRequest): Promise<GiftCardDetail> => {
    const response = await apiClient.post<{ card: GiftCardDetail }>(
      `${ENDPOINT}/${id}/reassign`,
      request,
    );
    return response.data.card;
  },

  getQrCodeSvg: async (id: string): Promise<string> => {
    const response = await apiClient.get(`${ENDPOINT}/${id}/qrcode`, {
      responseType: 'text',
    });
    return response.data as string;
  },

  exchange: async (
    id: string,
    request: ExchangeGiftCardRequest,
    idempotencyKey?: string,
  ): Promise<ExchangeGiftCardResponse> => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    const response = await apiClient.post<ExchangeGiftCardResponse>(
      `${ENDPOINT}/${id}/exchanges`,
      request,
      { headers },
    );
    return response.data;
  },
};
