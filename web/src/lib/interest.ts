import { FALLBACK_BASE_RATE_PCT, STATUTORY_ADDON_PCT } from '../config';
import type { Invoice } from '../api/types';

export interface InterestBasis {
  basePct: number;
  addonPct: number;
  ratePct: number;
  /** Pence per day, fractional. */
  dailyPence: number;
  /** Pence per second, fractional (what the live ticker adds). */
  perSecondPence: number;
}

/** The rate and daily accrual for an invoice, using the API's figures when present. */
export function interestBasis(inv: Invoice): InterestBasis {
  const ratePct =
    inv.statutoryRatePct ??
    (inv.baseRatePct != null ? inv.baseRatePct + STATUTORY_ADDON_PCT : FALLBACK_BASE_RATE_PCT + STATUTORY_ADDON_PCT);
  const basePct = inv.baseRatePct ?? ratePct - STATUTORY_ADDON_PCT;
  const dailyPence = inv.dailyInterestPence ?? (inv.amountPence * (ratePct / 100)) / 365;
  return {
    basePct,
    addonPct: STATUTORY_ADDON_PCT,
    ratePct,
    dailyPence,
    perSecondPence: dailyPence / 86400,
  };
}

export const isOpen = (inv: Invoice) => inv.status !== 'paid';
export const isLate = (inv: Invoice) => isOpen(inv) && inv.daysLate > 0;
/** Interest accrues on any confirmed, unpaid debt past its legally-late date. */
export const isAccruing = (inv: Invoice) => isLate(inv) && inv.status !== 'extracted';

export function pct(n: number): string {
  return `${Number.isInteger(n) ? n : n.toFixed(2).replace(/0$/, '')}%`;
}
