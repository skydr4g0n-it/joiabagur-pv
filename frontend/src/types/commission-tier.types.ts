export interface CommissionTier {
  id: string;
  minAmountInclusive: number;
  maxAmountInclusive: number | null;
  commissionPercent: number;
}

export interface CommissionTierInput {
  minAmountInclusive: number;
  maxAmountInclusive: number | null;
  commissionPercent: number;
}
