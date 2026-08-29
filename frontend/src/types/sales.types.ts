/**
 * Sales Module Types (EP3)
 */

/**
 * Request to create a new sale.
 */
export interface CreateSaleRequest {
  productId: string;
  pointOfSaleId: string;
  paymentMethodId: string;
  quantity: number;
  price?: number;
  notes?: string;
  photoBase64?: string;
  photoFileName?: string;
  /**
   * Assisted search this sale originated from, when it did.
   * Absent for scanning, SKU search and image recognition. An identifier the server cannot
   * resolve degrades to no attribution — it never fails the sale.
   */
  searchEventId?: string;
}

/**
 * Response from creating a sale.
 */
export interface CreateSaleResponse {
  sale: Sale;
  warning?: string;
  isLowStock: boolean;
  remainingStock?: number;
}

/**
 * Sale details.
 */
export interface Sale {
  id: string;
  productId: string;
  productSku: string;
  productName: string;
  pointOfSaleId: string;
  pointOfSaleName: string;
  userId: string;
  userName: string;
  paymentMethodId: string;
  paymentMethodName: string;
  price: number;
  quantity: number;
  total: number;
  priceWasOverridden: boolean;
  originalProductPrice?: number;
  notes?: string;
  hasPhoto: boolean;
  hasReturn: boolean;
  saleDate: string;
  createdAt: string;
}

/**
 * Request for sales history with filters.
 */
export interface SalesHistoryFilterRequest {
  startDate?: string;
  endDate?: string;
  pointOfSaleId?: string;
  productId?: string;
  userId?: string;
  paymentMethodId?: string;
  page?: number;
  pageSize?: number;
}

/**
 * Paginated sales history response.
 */
export interface SalesHistoryResponse {
  sales: Sale[];
  totalCount: number;
  page: number;
  pageSize: number;
  totalPages: number;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
}

/**
 * Image Recognition Model Metadata.
 */
export interface ModelMetadata {
  version: string;
  trainedAt: string;
  modelPath: string;
  accuracyMetrics?: string;
  totalPhotosUsed: number;
  totalProductsUsed: number;
  isActive: boolean;
}

/**
 * Model health metrics for admin dashboard.
 */
export interface ModelHealth {
  alertLevel: 'OK' | 'RECOMMENDED' | 'HIGH' | 'CRITICAL';
  alertMessage: string;
  currentVersion?: string;
  lastTrainedAt?: string;
  daysSinceTraining?: number;
  catalogMetrics: {
    totalProducts: number;
    productsWithPhotos: number;
    productsWithoutPhotos: number;
    newProductsSinceTraining: number;
    newProductsPercentage: number;
  };
  photoMetrics: {
    totalPhotos: number;
    photosAddedSinceTraining: number;
    photosDeletedSinceTraining: number;
    netChangePercentage: number;
  };
  precisionMetrics?: {
    top1Accuracy?: number;
    top3Accuracy?: number;
    averageInferenceTimeMs?: number;
    fallbackRate?: number;
  };
}

/**
 * Training dataset for browser-based training.
 */
export interface TrainingDataset {
  photos: TrainingPhoto[];
  totalPhotos: number;
  totalProducts: number;
  classLabels: string[];
}

/**
 * Individual photo in training dataset.
 */
export interface TrainingPhoto {
  productId: string;
  productSku: string;
  productName: string;
  photoId: string;
  photoUrl: string;
}

/**
 * Product label mapping for inference (maps class label to product details).
 */
export interface ProductLabelMapping {
  productId: string;
  productSku: string;
  productName: string;
  photoUrl: string;
}

/**
 * Class labels response for inference (accessible to all authenticated users).
 */
export interface ClassLabelsResponse {
  classLabels: string[];
  productMappings: Record<string, ProductLabelMapping>;
}

/**
 * Request to upload a browser-trained model.
 */
export interface UploadTrainedModelRequest {
  version: string;
  modelTopologyJson: string;
  trainingAccuracy: number;
  validationAccuracy: number;
  totalPhotosUsed: number;
  totalProductsUsed: number;
  trainingDurationSeconds: number;
  weightFiles: File[];
}

/**
 * Result of model upload.
 */
export interface UploadTrainedModelResult {
  success: boolean;
  errorMessage?: string;
  version?: string;
  metadata?: ModelMetadata;
}

/**
 * Single embedding entry in the embeddings index.
 */
export interface EmbeddingDto {
  photoId: string;
  productId: string;
  sku: string;
  vector: number[];
}

/**
 * Full embeddings index response for client-side similarity search.
 */
export interface EmbeddingsIndexResponse {
  embeddings: EmbeddingDto[];
  lastUpdated: string | null;
  count: number;
}

/**
 * Lightweight response for staleness checks.
 */
export interface EmbeddingsStatusResponse {
  count: number;
  lastUpdated: string | null;
}

/**
 * Product suggestion from image recognition.
 */
export interface ProductSuggestion {
  productId: string;
  productSku: string;
  productName: string;
  confidence: number;
  photoUrl: string;
}

/**
 * A line item in the sales cart.
 */
export interface CartLine {
  id: string;
  productId: string;
  productSku: string;
  productName: string;
  productPrice: number;
  quantity: number;
  price?: number;
  pointOfSaleId: string;
  pointOfSaleName: string;
  paymentMethodId: string;
  paymentMethodName: string;
  photoBase64?: string;
  photoFileName?: string;
  addedAt: string;
  /**
   * Assisted search this line originated from, carried through the cart so the attribution
   * survives until checkout. The cart persists for ten hours; an identifier from nine hours ago
   * still attributes the sale, and that is correct — it is what happened.
   */
  searchEventId?: string;
}

/**
 * Request to create bulk sales.
 */
export interface CreateBulkSalesRequest {
  pointOfSaleId: string;
  paymentMethodId: string;
  notes?: string;
  lines: BulkSaleLineRequest[];
}

/**
 * Individual line in a bulk sale request.
 */
export interface BulkSaleLineRequest {
  productId: string;
  quantity: number;
  price?: number;
  photoBase64?: string;
  photoFileName?: string;
  /**
   * Assisted search this line originated from. Per line rather than per checkout: each line may
   * come from a different search, or from none.
   */
  searchEventId?: string;
}

/**
 * Response from bulk sale creation.
 */
export interface CreateBulkSalesResponse {
  success: boolean;
  bulkOperationId?: string;
  sales: Sale[];
  errorMessage?: string;
  warnings: BulkSaleLineWarning[];
}

/**
 * Warning for a specific line in bulk sale.
 */
export interface BulkSaleLineWarning {
  lineIndex: number;
  productName: string;
  message: string;
  isLowStock: boolean;
  remainingStock: number;
}
