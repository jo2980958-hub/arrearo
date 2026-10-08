const gbp = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' });
const gbpWhole = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  maximumFractionDigits: 0,
});

/** Integer pence -> "£1,234.56". */
export function pounds(pence: number): string {
  return gbp.format(Math.round(pence) / 100);
}

/** Compact whole-pound form for dense charts: "£12,750". */
export function poundsWhole(pence: number): string {
  return gbpWhole.format(Math.round(pence) / 100);
}

/** Split a (possibly fractional) pence value into display parts for the live ticker. */
export function splitTicker(pence: number): { main: string; fine: string } {
  const pounds = pence / 100;
  const fixed = pounds.toFixed(4);
  const [whole, frac] = fixed.split('.');
  const wholeFmt = Number(whole).toLocaleString('en-GB');
  return { main: `£${wholeFmt}.${frac.slice(0, 2)}`, fine: frac.slice(2) };
}

/** "12.50" / "£12.50" / "1,200" -> integer pence, or null if unparseable. */
export function parsePence(input: string): number | null {
  const cleaned = input.replace(/[£,\s]/g, '');
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  return Math.round(parseFloat(cleaned) * 100);
}

export function penceToInput(pence: number): string {
  return (pence / 100).toFixed(2);
}
