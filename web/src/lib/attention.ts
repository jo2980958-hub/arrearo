import type { Invoice } from '../api/types';

export interface AttentionItem {
  invoice: Invoice;
  kind: 'confirm' | 'lba' | 'chase' | 'dispute';
  title: string;
  detail: string;
  cta: string;
}

const order = { lba: 0, dispute: 1, chase: 2, confirm: 3 } as const;

/** What the owner needs to do next, most serious first. */
export function attentionItems(invoices: Invoice[]): AttentionItem[] {
  const out: AttentionItem[] = [];
  for (const inv of invoices) {
    if (inv.status === 'paid') continue;
    const drafts = (inv.drafts ?? []).filter((d) => d.status === 'pending');
    const lba = drafts.find((d) => d.kind === 'lba');
    const chase = drafts.find((d) => d.kind !== 'lba');
    if (inv.status === 'extracted') {
      out.push({
        invoice: inv,
        kind: 'confirm',
        title: `Confirm the invoice for ${inv.debtorName}`,
        detail: 'Read from your WhatsApp photo. Check the amount and due date.',
        cta: 'Review',
      });
    }
    if (lba) {
      out.push({
        invoice: inv,
        kind: 'lba',
        title: `Letter Before Action ready for ${inv.debtorName}`,
        detail: `${inv.daysLate} days late. Drafted by Arrearo and waiting for your approval.`,
        cta: 'Review letter',
      });
    } else if (chase) {
      out.push({
        invoice: inv,
        kind: 'chase',
        title: `Approve the chase to ${inv.debtorName}`,
        detail: inv.daysLate > 0 ? `${inv.daysLate} days late. WhatsApp message drafted.` : 'Due today. First reminder drafted.',
        cta: 'Review message',
      });
    }
    if (inv.status === 'disputed') {
      out.push({
        invoice: inv,
        kind: 'dispute',
        title: `${inv.debtorName} disputes this invoice`,
        detail: 'Automatic chasing is paused. Resolve it, then resume.',
        cta: 'Open',
      });
    }
  }
  return out.sort((a, b) => order[a.kind] - order[b.kind]);
}
