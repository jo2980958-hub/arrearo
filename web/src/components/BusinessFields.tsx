import type { Business } from '../api/types';
import { Field } from './ui';

export type BizDraft = Pick<
  Business,
  'name' | 'ownerName' | 'email' | 'whatsappNumber' | 'sector' | 'defaultTermsDays' | 'bankName' | 'bankSortCode' | 'bankAccount'
>;
export type Errors = Partial<Record<keyof BizDraft, string>>;

export const SECTORS = [
  'Construction & trades', 'Professional services', 'Creative & marketing', 'Manufacturing', 'Wholesale & distribution',
  'IT & software', 'Hospitality & events', 'Health & care', 'Transport & logistics', 'Other',
];

export function toDraft(b?: Partial<Business>): BizDraft {
  return {
    name: b?.name ?? '',
    ownerName: b?.ownerName ?? '',
    email: b?.email ?? '',
    whatsappNumber: b?.whatsappNumber ?? '',
    sector: b?.sector ?? '',
    defaultTermsDays: b?.defaultTermsDays ?? 30,
    bankName: b?.bankName ?? '',
    bankSortCode: b?.bankSortCode ?? '',
    bankAccount: b?.bankAccount ?? '',
  };
}

export function formatSort(v: string): string {
  const d = v.replace(/\D/g, '').slice(0, 6);
  return d.replace(/(\d{2})(?=\d)/g, '$1-');
}

export function validate(d: BizDraft, parts: ('business' | 'bank' | 'terms')[]): Errors {
  const e: Errors = {};
  if (parts.includes('business')) {
    if (!d.name.trim()) e.name = 'Enter your business name.';
    if (!d.ownerName.trim()) e.ownerName = 'Enter your name.';
    if (!/^\S+@\S+\.\S+$/.test(d.email)) e.email = 'Enter a valid email address.';
    if (!/^\+\d{8,15}$/.test(d.whatsappNumber.replace(/\s/g, ''))) e.whatsappNumber = 'Use international format, like +447700900123.';
  }
  if (parts.includes('terms')) {
    if (!(d.defaultTermsDays >= 1 && d.defaultTermsDays <= 120)) e.defaultTermsDays = 'Choose between 1 and 120 days.';
  }
  if (parts.includes('bank')) {
    if (!d.bankName?.trim()) e.bankName = 'Enter the name on the account.';
    if (!/^\d{2}-\d{2}-\d{2}$/.test(d.bankSortCode ?? '')) e.bankSortCode = 'A sort code has 6 digits, like 20-45-67.';
    if (!/^\d{8}$/.test(d.bankAccount ?? '')) e.bankAccount = 'A UK account number has 8 digits.';
  }
  return e;
}

interface P { value: BizDraft; onChange: (v: BizDraft) => void; errors: Errors; prefix?: string }

const set = (p: P, k: keyof BizDraft, v: string | number) => p.onChange({ ...p.value, [k]: v });

export function BusinessSection(p: P) {
  const id = (k: string) => `${p.prefix ?? 'b'}-${k}`;
  const inv = (k: keyof BizDraft) => ({ 'aria-invalid': !!p.errors[k], 'aria-describedby': p.errors[k] ? `${id(k)}-err` : undefined });
  return (
    <div className="form-grid">
      <Field label="Business name" htmlFor={id('name')} error={p.errors.name} full>
        <input id={id('name')} className="input" autoComplete="organization" value={p.value.name} onChange={(e) => set(p, 'name', e.target.value)} {...inv('name')} />
      </Field>
      <Field label="Your name" htmlFor={id('owner')} error={p.errors.ownerName}>
        <input id={id('owner')} className="input" autoComplete="name" value={p.value.ownerName} onChange={(e) => set(p, 'ownerName', e.target.value)} {...inv('ownerName')} />
      </Field>
      <Field label="Work email" htmlFor={id('email')} error={p.errors.email} hint="Where Arrearo sends your morning digest.">
        <input id={id('email')} className="input" type="email" autoComplete="email" value={p.value.email} onChange={(e) => set(p, 'email', e.target.value)} {...inv('email')} />
      </Field>
      <Field label="Your WhatsApp number" htmlFor={id('wa')} error={p.errors.whatsappNumber} hint="Send invoice photos from this number.">
        <input id={id('wa')} className="input" type="tel" inputMode="tel" autoComplete="tel" placeholder="+447700900123" value={p.value.whatsappNumber} onChange={(e) => set(p, 'whatsappNumber', e.target.value)} {...inv('whatsappNumber')} />
      </Field>
      <Field label="What do you do?" htmlFor={id('sector')}>
        <select id={id('sector')} className="select" value={p.value.sector ?? ''} onChange={(e) => set(p, 'sector', e.target.value)}>
          <option value="">Choose a sector</option>
          {SECTORS.map((s) => <option key={s}>{s}</option>)}
        </select>
      </Field>
    </div>
  );
}

export function TermsSection(p: P) {
  const days = [7, 14, 30, 45, 60];
  return (
    <div className="stack">
      <div className="field">
        <span className="label" id={`${p.prefix}-terms-l`}>Your usual payment terms</span>
        <div className="terms" role="group" aria-labelledby={`${p.prefix}-terms-l`}>
          {days.map((d) => (
            <button type="button" key={d} aria-pressed={p.value.defaultTermsDays === d} onClick={() => set(p, 'defaultTermsDays', d)}>
              {d} days
            </button>
          ))}
        </div>
        {p.errors.defaultTermsDays && <span className="err" role="alert">{p.errors.defaultTermsDays}</span>}
        <span className="hint">Used when an invoice has no due date. With no agreed terms, the law treats an invoice as due 30 days after it is issued or the goods are delivered, whichever is later.</span>
      </div>
    </div>
  );
}

export function BankSection(p: P) {
  const id = (k: string) => `${p.prefix ?? 'b'}-${k}`;
  const inv = (k: keyof BizDraft) => ({ 'aria-invalid': !!p.errors[k], 'aria-describedby': p.errors[k] ? `${id(k)}-err` : undefined });
  return (
    <div className="form-grid">
      <Field label="Name on the account" htmlFor={id('bank')} error={p.errors.bankName} full>
        <input id={id('bank')} className="input" autoComplete="off" value={p.value.bankName ?? ''} onChange={(e) => set(p, 'bankName', e.target.value)} {...inv('bankName')} />
      </Field>
      <Field label="Sort code" htmlFor={id('sort')} error={p.errors.bankSortCode}>
        <input id={id('sort')} className="input mono" inputMode="numeric" autoComplete="off" placeholder="20-45-67" value={p.value.bankSortCode ?? ''} onChange={(e) => set(p, 'bankSortCode', formatSort(e.target.value))} {...inv('bankSortCode')} />
      </Field>
      <Field label="Account number" htmlFor={id('acc')} error={p.errors.bankAccount}>
        <input id={id('acc')} className="input mono" inputMode="numeric" autoComplete="off" maxLength={8} placeholder="12345678" value={p.value.bankAccount ?? ''} onChange={(e) => set(p, 'bankAccount', e.target.value.replace(/\D/g, ''))} {...inv('bankAccount')} />
      </Field>
    </div>
  );
}
