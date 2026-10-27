export interface SalesReportFilterRequest {
  startDate?: string;
  endDate?: string;
  pointOfSaleId?: string;
  productId?: string;
  userId?: string;
  paymentMethodId?: string;
  search?: string;
  amountMin?: number;
  amountMax?: number;
  hasPhoto?: boolean;
  priceWasOverridden?: boolean;
  page?: number;
  pageSize?: number;
}

export interface SalesReportItem {
  id: string;
  saleDate: string;
  productName: string;
  productSku: string;
  collectionName: string | null;
  pointOfSaleName: string;
  quantity: number;
  price: number;
  total: number;
  originalProductPrice: number | null;
  priceWasOverridden: boolean;
  paymentMethodName: string;
  operatorName: string;
  notes: string | null;
  hasPhoto: boolean;
  hasReturn: boolean;
}

export interface SalesReportPosAggregate {
  pointOfSaleId: string;
  totalAmount: number;
  totalCommission: number;
  totalAmountNet: number;
}

export interface SalesReportResponse {
  items: SalesReportItem[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
  totalSalesCount: number;
  totalQuantity: number;
  totalAmount: number;
  totalCommission: number;
  totalAmountNet: number;
  aggregatesByPointOfSale?: SalesReportPosAggregate[] | null;
}
