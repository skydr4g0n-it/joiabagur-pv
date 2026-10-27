/**
 * Gift card types (tarjetas regalo)
 */

export interface GiftCardListItem {
  id: string;
  code: string;
  pointOfSaleId: string;
  pointOfSaleName: string;
  holderName?: string;
  nominalAmount: number;
  spendableBalance: number;
  accountedRemainder: number;
  expiryDate: string;
  createdAt: string;
}

export interface GiftCardListResponse {
  items: GiftCardListItem[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface GiftCardCoverageLink {
  saleId: string;
  productSku: string;
  productName: string;
  coverageAmount: number;
  saleDate: string;
}

export interface GiftCardOperation {
  type: string;
  occurredAt: string;
  detail?: string;
}

export interface GiftCardDetail {
  id: string;
  code: string;
  pointOfSaleId: string;
  pointOfSaleName: string;
  issuanceSalePointOfSaleId: string;
  issuanceSalePointOfSaleName: string;
  holderName?: string;
  nominalAmount: number;
  spendableBalance: number;
  accountedRemainder: number;
  expiryDate: string;
  issuanceSaleId: string;
  issuanceSaleDate: string;
  linkedProducts: GiftCardCoverageLink[];
  operations: GiftCardOperation[];
}

export interface IssueGiftCardRequest {
  pointOfSaleId: string;
  nominalAmount: number;
  expiryDate: string;
  holderName?: string;
  paymentMethodId: string;
}

export interface IssueGiftCardResponse {
  success: boolean;
  errorMessage?: string;
  isForbidden?: boolean;
  card?: GiftCardDetail;
}

export interface ReassignGiftCardRequest {
  toPointOfSaleId: string;
}

export interface GiftCardByCode {
  id: string;
  code: string;
  nominalAmount: number;
  spendableBalance: number;
  expiryDate: string;
  pointOfSaleId: string;
}

export const GIFT_CARD_PRESET_AMOUNTS = [50, 100, 150, 200] as const;

export interface ExchangeGiftCardRequest {
  pointOfSaleId: string;
  paymentMethodId: string;
  returnCategory: number;
  reason?: string;
  returnLines: { saleId: string; quantity: number }[];
  newProducts: { productId: string; quantity: number }[];
}

export interface ExchangeGiftCardResponse {
  success: boolean;
  errorMessage?: string;
  cashDue: number;
  newSaleIds: string[];
  returnIds: string[];
}
