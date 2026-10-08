import type { DebtorType, Invoice } from './types';
import { FALLBACK_BASE_RATE_PCT, STATUTORY_ADDON_PCT } from '../config';

const DAY = 86_400_000;

function parseDay(iso: string): number {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}

function addDays(iso: string, n: number): string {
  return new Date(parseDay(iso) + n * DAY).toISOString().slice(0, 10);
}

/**
 * Mirror of services/legal/engine.py, used ONLY for demo data and as a
 * fallback if the API omits a derived field. The API is authoritative.
 */
export function legallyLateDate(
  invoiceDate: string,
  deliveryDate: string | null | undefined,
  agreedDueDate: string | null | undefined,
  _debtorType: DebtorType,
): string {
  // Due date: agreed date wins, else 30 days from the later of invoice/delivery.
  // Legally late (interest starts) the day after.
  let due = agreedDueDate;
  if (!due) {
    const later = deliveryDate && deliveryDate > invoiceDate ? deliveryDate : invoiceDate;
    due = addDays(later, 30);
  }
  return addDays(due, 1);
}

export function fixedRecoverySum(amountPence: number): number {
  if (amountPence < 100_000) return 4000;
  if (amountPence < 1_000_000) return 7000;
  return 10_000;
}

export function deriveMoney(
  base: Pick<Invoice, 'amountPence' | 'invoiceDate' | 'deliveryDate' | 'agreedDueDate' | 'debtorType' | 'paidAt'>,
  today = new Date(),
) {
  const lateOn = legallyLateDate(base.invoiceDate, base.deliveryDate, base.agreedDueDate, base.debtorType);
  const endMs = base.paidAt ? parseDay(base.paidAt) : Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const daysLate = endMs >= parseDay(lateOn) ? Math.round((endMs - parseDay(lateOn)) / DAY) + 1 : 0;
  const ratePct = FALLBACK_BASE_RATE_PCT + STATUTORY_ADDON_PCT;
  const interestAccruedPence = Math.round(((base.amountPence * ratePct) / 100 / 365) * daysLate);
  const fixedRecoverySumPence = daysLate > 0 ? fixedRecoverySum(base.amountPence) : 0;
  return {
    legallyLateDate: lateOn,
    daysLate,
    interestAccruedPence,
    fixedRecoverySumPence,
    totalOwedPence: base.amountPence + interestAccruedPence + fixedRecoverySumPence,
    statutoryRatePct: ratePct,
    baseRatePct: FALLBACK_BASE_RATE_PCT,
  };
}
