export type InventoryMovementOutputModel = 'summary' | 'detail';

export interface InventoryMovementReportFilter {
  outputModel?: InventoryMovementOutputModel;
  startDate?: string;
  endDate?: string;
  pointOfSaleId?: string;
  productSearch?: string;
  page?: number;
  pageSize?: number;
  sortBy?: string;
  sortDirection?: string;
}

export interface InventoryMovementSummaryRow {
  productId: string;
  productName: string;
  productSku: string;
  additions: number;
  subtractions: number;
  difference: number;
}

export interface InventoryMovementDetailRow {
  id: string;
  inventoryId: string;
  productId: string;
  productName: string;
  productSku: string;
  pointOfSaleId: string;
  pointOfSaleName: string;
  movementType: number;
  movementTypeName: string;
  quantityChange: number;
  quantityBefore: number;
  quantityAfter: number;
  userId: string;
  userName: string;
  reason?: string | null;
  movementDate: string;
  saleId?: string | null;
  returnId?: string | null;
}

export type InventoryMovementReportRow = InventoryMovementSummaryRow | InventoryMovementDetailRow;

export interface InventoryMovementReportResponse {
  items: InventoryMovementReportRow[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
}
