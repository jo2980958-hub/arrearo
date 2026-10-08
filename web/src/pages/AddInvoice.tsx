import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import { useCreateInvoice } from '../api/hooks';
import type { Business, DebtorType, NewInvoiceInput } from '../api/types';
import { parsePence, pounds } from '../lib/money';
import { isoDate, todayIso } from '../lib/dates';
import { Icon } from '../components/icons';
import { Button, Field, useToast, usePageTitle } from '../components/ui';
import { WHATSAPP_SENDER } from '../config';

const TYPES: { id: DebtorType; label: string }[] = [
  { id: 'company', label: 'Limited company or LLP' },
  { id: 'sole_trader', label: 'Sole trader or partnership' },
  { id: 'public_authority', label: 'Public authority' },
  { id: 'individual', label: 'Individual' },
];

function addDays(iso: string, n: number) {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return isoDate(d);
}

export default function AddInvoice() {
  usePageTitle('Add invoice');
  const { business } = useOutletContext<{ business: Business }>();
  const nav = useNavigate();
  const toast = useToast();
  const create = useCreateInvoice();
  const [f, setF] = useState({
    debtorName: '', debtorType: 'company' as DebtorType, debtorCompanyNumber: '', debtorEmail: '', debtorWhatsapp: '',
    amount: '', invoiceDate: todayIso(), agreedDueDate: '', reference: '', description: '',
  });
  const [err, setErr] = useState<Record<string, string>>({});
  const set = (k: keyof typeof f, v: string) => setF((x) => ({ ...x, [k]: v }));
  const suggestedDue = addDays(f.invoiceDate || todayIso(), business.defaultTermsDays || 30);
  const amountPence = parsePence(f.amount);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const x: Record<string, string> = {};
    if (!f.debtorName.trim()) x.debtorName = 'Who owes you the money?';
    if (amountPence == null || amountPence <= 0) x.amount = 'Enter pounds and pence, like 1250.00';
    if (!f.reference.trim()) x.reference = 'Add the invoice number.';
    if (!f.invoiceDate) x.invoiceDate = 'Choose the invoice date.';
    if (f.debtorEmail && !/^\S+@\S+\.\S+$/.test(f.debtorEmail)) x.debtorEmail = 'That email doesn’t look right.';
    if (f.debtorWhatsapp && !/^\+\d{8,15}$/.test(f.debtorWhatsapp.replace(/\s/g, ''))) x.debtorWhatsapp = 'Use international format, like +447700900123.';
    setErr(x);
    if (Object.keys(x).length) return;

    const body: NewInvoiceInput = {
      debtorName: f.debtorName.trim(),
      debtorType: f.debtorType,
      debtorCompanyNumber: f.debtorCompanyNumber.trim() || undefined,
      debtorEmail: f.debtorEmail.trim() || undefined,
      debtorWhatsapp: f.debtorWhatsapp.replace(/\s/g, '') || undefined,
      amountPence: amountPence as number,
      invoiceDate: f.invoiceDate,
      agreedDueDate: f.agreedDueDate || suggestedDue,
      reference: f.reference.trim(),
      description: f.description.trim() || undefined,
    };
    try {
      const inv = await create.mutateAsync(body);
      toast(`Added ${inv.reference}. Arrearo is tracking it.`);
      nav(`/invoices/${inv.invoiceId}`);
    } catch (e2) {
      toast(e2 instanceof Error ? e2.message : 'Could not add the invoice', 'err');
    }
  }

  const inv = (k: string) => ({ 'aria-invalid': !!err[k], 'aria-describedby': err[k] ? `a-${k}-err` : undefined });

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <Link to="/invoices" className="crumb"><Icon name="arrowLeft" />All invoices</Link>
      <div className="page-head">
        <div>
          <h1>Add an invoice</h1>
          <p className="sub">Prefer WhatsApp? Send a photo of the invoice to {WHATSAPP_SENDER} and Arrearo reads it for you.</p>
        </div>
      </div>

      <form className="stack" onSubmit={submit} noValidate>
        <section className="card card-pad stack" aria-labelledby="a1">
          <h2 className="card-title" id="a1">Who owes you</h2>
          <div className="form-grid">
            <Field label="Customer name" htmlFor="a-debtorName" error={err.debtorName} full>
              <input id="a-debtorName" className="input" value={f.debtorName} onChange={(e) => set('debtorName', e.target.value)} {...inv('debtorName')} />
            </Field>
            <Field label="They are a" htmlFor="a-type">
              <select id="a-type" className="select" value={f.debtorType} onChange={(e) => set('debtorType', e.target.value)}>
                {TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </Field>
            <Field label="Companies House number" htmlFor="a-co" hint="Optional. Lets Arrearo check how they pay.">
              <input id="a-co" className="input mono" value={f.debtorCompanyNumber} onChange={(e) => set('debtorCompanyNumber', e.target.value)} />
            </Field>
            <Field label="Their WhatsApp number" htmlFor="a-debtorWhatsapp" error={err.debtorWhatsapp} hint="Chases go here.">
              <input id="a-debtorWhatsapp" className="input" type="tel" inputMode="tel" placeholder="+447700900123" value={f.debtorWhatsapp} onChange={(e) => set('debtorWhatsapp', e.target.value)} {...inv('debtorWhatsapp')} />
            </Field>
            <Field label="Their accounts email" htmlFor="a-debtorEmail" error={err.debtorEmail} hint="Used for any Letter Before Action.">
              <input id="a-debtorEmail" className="input" type="email" value={f.debtorEmail} onChange={(e) => set('debtorEmail', e.target.value)} {...inv('debtorEmail')} />
            </Field>
          </div>
        </section>

        <section className="card card-pad stack" aria-labelledby="a2">
          <h2 className="card-title" id="a2">The invoice</h2>
          <div className="form-grid">
            <Field label="Invoice number" htmlFor="a-reference" error={err.reference}>
              <input id="a-reference" className="input mono" value={f.reference} onChange={(e) => set('reference', e.target.value)} {...inv('reference')} />
            </Field>
            <Field label="Amount" htmlFor="a-amount" error={err.amount} hint={amountPence ? `Arrearo will track ${pounds(amountPence)}.` : 'Including VAT, as invoiced.'}>
              <div className="input-affix"><span>£</span><input id="a-amount" className="input num" inputMode="decimal" placeholder="0.00" value={f.amount} onChange={(e) => set('amount', e.target.value)} {...inv('amount')} /></div>
            </Field>
            <Field label="Invoice date" htmlFor="a-invoiceDate" error={err.invoiceDate}>
              <input id="a-invoiceDate" className="input" type="date" value={f.invoiceDate} max={todayIso()} onChange={(e) => set('invoiceDate', e.target.value)} {...inv('invoiceDate')} />
            </Field>
            <Field label="Due date" htmlFor="a-due" hint={f.agreedDueDate ? undefined : `Leave blank to use your ${business.defaultTermsDays}-day terms.`}>
              <input id="a-due" className="input" type="date" value={f.agreedDueDate} placeholder={suggestedDue} onChange={(e) => set('agreedDueDate', e.target.value)} />
            </Field>
            <Field label="What it was for" htmlFor="a-desc" full>
              <input id="a-desc" className="input" value={f.description} onChange={(e) => set('description', e.target.value)} />
            </Field>
          </div>
        </section>

        <div className="actions">
          <Button variant="primary" type="submit" loading={create.isPending} icon="check">Add and start tracking</Button>
          <Link to="/invoices" className="btn ghost">Cancel</Link>
        </div>
      </form>
    </div>
  );
}
