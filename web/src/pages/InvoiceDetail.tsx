import { useMemo, useState, type FormEvent } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useChase, useDebtor, useEvents, useInvoice, usePatchInvoice, useSendLba } from '../api/hooks';
import { threadFromEvents } from '../api/client';
import type { Invoice } from '../api/types';
import { isOpen } from '../lib/interest';
import { parsePence, penceToInput, pounds } from '../lib/money';
import { fmtDate } from '../lib/dates';
import { Icon } from '../components/icons';
import { Button, Dialog, ErrorState, Field, Skeleton, StatusPill, useToast, usePageTitle } from '../components/ui';
import { DraftCard, EventList, OwedCard, RiskPanel, Stepper, Thread } from '../components/InvoiceParts';

type Confirm = null | 'paid' | 'dispute' | 'chase' | 'lba' | 'resume';

const TYPE_LABEL = { company: 'Limited company', sole_trader: 'Sole trader', individual: 'Individual', public_authority: 'Public authority' } as const;

function ConfirmCard({ inv }: { inv: Invoice }) {
  const patch = usePatchInvoice(inv.invoiceId);
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(inv.debtorName);
  const [amount, setAmount] = useState(penceToInput(inv.amountPence));
  const [ref, setRef] = useState(inv.reference);
  const [invDate, setInvDate] = useState(inv.invoiceDate);
  const [due, setDue] = useState(inv.agreedDueDate ?? '');
  const conf = Math.round((inv.extractionConfidence ?? 1) * 100);

  async function save(e?: FormEvent) {
    e?.preventDefault();
    const p = parsePence(amount);
    if (p == null || p <= 0) {
      toast('Enter the amount as pounds and pence, like 1250.00', 'err');
      return;
    }
    try {
      await patch.mutateAsync({ debtorName: name.trim(), amountPence: p, reference: ref.trim(), invoiceDate: invDate, agreedDueDate: due || null, status: 'confirmed' });
      toast('Invoice confirmed. Arrearo is tracking it.');
      setEditing(false);
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not confirm the invoice', 'err');
    }
  }

  return (
    <section className="card confirm-card" aria-labelledby="confirm-h">
      <div className="risk-top">
        <h2 className="card-title" id="confirm-h">Check what Arrearo read</h2>
        <span className="pill s-due">Awaiting you</span>
      </div>
      <p className="muted" style={{ fontSize: 14, margin: '6px 0 14px' }}>
        This came from your WhatsApp photo. Nothing is chased until you confirm it.
      </p>
      <label className="eyebrow" htmlFor="meter" style={{ display: 'block' }}>Reading confidence {conf}%</label>
      <div className="conf-meter" id="meter" role="meter" aria-valuenow={conf} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${conf}%` }} /></div>

      {editing ? (
        <form onSubmit={save} className="form-grid" style={{ marginTop: 18 }}>
          <Field label="Debtor" htmlFor="c-name" full><input id="c-name" className="input" value={name} onChange={(e) => setName(e.target.value)} required /></Field>
          <Field label="Amount" htmlFor="c-amt"><div className="input-affix"><span>£</span><input id="c-amt" className="input num" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required /></div></Field>
          <Field label="Reference" htmlFor="c-ref"><input id="c-ref" className="input" value={ref} onChange={(e) => setRef(e.target.value)} required /></Field>
          <Field label="Invoice date" htmlFor="c-date"><input id="c-date" className="input" type="date" value={invDate} onChange={(e) => setInvDate(e.target.value)} required /></Field>
          <Field label="Due date" htmlFor="c-due"><input id="c-due" className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} /></Field>
          <div className="full actions">
            <Button variant="primary" type="submit" loading={patch.isPending}>Save and confirm</Button>
            <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </form>
      ) : (
        <>
          <dl className="kv" style={{ marginTop: 16 }}>
            <dt>Debtor</dt><dd>{inv.debtorName}</dd>
            <dt>Amount</dt><dd className="num">{pounds(inv.amountPence)}</dd>
            <dt>Reference</dt><dd className="mono">{inv.reference}</dd>
            <dt>Due date</dt><dd>{fmtDate(inv.agreedDueDate)}</dd>
          </dl>
          <div className="actions" style={{ marginTop: 18 }}>
            <Button variant="primary" icon="check" loading={patch.isPending} onClick={() => save()}>Looks right, confirm</Button>
            <Button onClick={() => setEditing(true)} icon="edit">Edit details</Button>
          </div>
        </>
      )}
    </section>
  );
}

export default function InvoiceDetail() {
  const { id = '' } = useParams();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'thread' ? 'thread' : 'overview';
  const q = useInvoice(id);
  const ev = useEvents(id);
  const inv = q.data;
  const debtorQ = useDebtor(inv?.debtorKey, !!inv && !inv.debtor);
  const patch = usePatchInvoice(id);
  const chase = useChase(id);
  const lba = useSendLba(id);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [lbaBody, setLbaBody] = useState<string | undefined>();
  usePageTitle(inv ? `${inv.debtorName} ${inv.reference}` : 'Invoice');

  const events = ev.data ?? [];
  const messages = useMemo(() => (inv?.messages?.length ? inv.messages : threadFromEvents(events)), [inv?.messages, events]);

  if (q.isError) {
    return <div className="page"><ErrorState error={q.error} retry={() => q.refetch()} /></div>;
  }
  if (!inv) {
    return (
      <div className="page">
        <Skeleton h={40} w="50%" />
        <div style={{ height: 20 }} />
        <div className="detail-grid"><Skeleton h={320} /><Skeleton h={320} /></div>
      </div>
    );
  }

  const debtor = inv.debtor ?? debtorQ.data ?? null;
  const drafts = (inv.drafts ?? []).filter((d) => d.status !== 'sent');
  const open = isOpen(inv);
  const canChase = open && inv.status !== 'extracted' && inv.status !== 'disputed' && !drafts.length;

  async function run<T>(p: Promise<T>, ok: string) {
    try {
      await p;
      toast(ok);
    } catch (err) {
      toast(err instanceof Error ? err.message : 'That did not work', 'err');
    } finally {
      setConfirm(null);
    }
  }

  const setTab = (t: 'overview' | 'thread') => setParams(t === 'thread' ? { tab: 'thread' } : {}, { replace: true });

  return (
    <div className="page">
      <Link to="/invoices" className="crumb"><Icon name="arrowLeft" />All invoices</Link>

      <div className="detail-head">
        <div>
          <h1>{inv.debtorName}</h1>
          <div className="meta">
            <StatusPill status={inv.status} />
            <span className="mono">{inv.reference}</span>
            <span>{pounds(inv.amountPence)} invoiced {fmtDate(inv.invoiceDate)}</span>
            <span>Due {fmtDate(inv.agreedDueDate)}</span>
          </div>
        </div>
        {open && (
          <div className="actions">
            {inv.status === 'disputed' ? (
              <Button icon="chat" onClick={() => setConfirm('resume')}>Resume chasing</Button>
            ) : (
              inv.status !== 'extracted' && <Button icon="pause" onClick={() => setConfirm('dispute')}>Mark disputed</Button>
            )}
            {canChase && <Button icon="send" onClick={() => setConfirm('chase')}>Chase now</Button>}
            {inv.status !== 'extracted' && <Button variant="primary" icon="check" onClick={() => setConfirm('paid')}>Mark as paid</Button>}
          </div>
        )}
      </div>

      <div className="tabs" role="tablist" aria-label="Invoice views">
        <button role="tab" id="tab-overview" aria-selected={tab === 'overview'} aria-controls="panel" onClick={() => setTab('overview')}>Overview</button>
        <button role="tab" id="tab-thread" aria-selected={tab === 'thread'} aria-controls="panel" onClick={() => setTab('thread')}>
          WhatsApp thread{messages.length ? ` (${messages.length})` : ''}
        </button>
      </div>

      <div id="panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === 'thread' ? (
          <Thread inv={inv} messages={messages} />
        ) : (
          <div className="detail-grid">
            <div className="stack">
              {inv.status === 'extracted' && <ConfirmCard inv={inv} />}
              {drafts.map((d) => (
                <DraftCard
                  key={d.draftId}
                  inv={inv}
                  draft={d}
                  busy={d.kind === 'lba' ? lba.isPending : chase.isPending}
                  onSend={(body) => (d.kind === 'lba' ? (setLbaBody(body), setConfirm('lba')) : run(chase.mutateAsync(body), 'Chase sent on WhatsApp.'))}
                />
              ))}
              {inv.status !== 'extracted' && <OwedCard inv={inv} />}
              <section className="card" aria-labelledby="tl-h">
                <div className="card-head">
                  <h2 id="tl-h">Recovery timeline</h2>
                  <span className="sub">Detect, chase, reply, letter, paid</span>
                </div>
                <Stepper inv={inv} events={events} />
                <hr className="rule" style={{ margin: '14px 24px 0' }} />
                {ev.isLoading ? <div style={{ padding: 24 }}><Skeleton h={60} /></div> : <EventList events={events} />}
              </section>
            </div>

            <div className="stack">
              <RiskPanel inv={inv} debtor={debtor} />
              <section className="card card-pad" aria-labelledby="det-h">
                <h2 className="card-title" id="det-h">Invoice details</h2>
                <dl className="kv">
                  <dt>Debtor type</dt><dd>{TYPE_LABEL[inv.debtorType]}</dd>
                  {inv.debtorCompanyNumber && (<><dt>Company no.</dt><dd className="mono"><a href={`https://find-and-update.company-information.service.gov.uk/company/${inv.debtorCompanyNumber}`} target="_blank" rel="noreferrer" style={{ textDecoration: 'underline', textUnderlineOffset: 3 }}>{inv.debtorCompanyNumber}</a></dd></>)}
                  <dt>Invoice date</dt><dd>{fmtDate(inv.invoiceDate)}</dd>
                  <dt>Due date</dt><dd>{fmtDate(inv.agreedDueDate)}</dd>
                  <dt>Legally late from</dt><dd>{fmtDate(inv.legallyLateDate)}</dd>
                  <dt>WhatsApp</dt><dd className="mono">{inv.debtorWhatsapp ?? '—'}</dd>
                  <dt>Email</dt><dd>{inv.debtorEmail ?? '—'}</dd>
                  <dt>Added via</dt><dd>{inv.sourceChannel === 'whatsapp' ? 'WhatsApp photo' : 'Dashboard'}</dd>
                  {inv.description && (<><dt>For</dt><dd>{inv.description}</dd></>)}
                </dl>
              </section>
            </div>
          </div>
        )}
      </div>

      <Dialog open={confirm === 'paid'} onClose={() => setConfirm(null)} title="Mark this invoice as paid?">
        <p className="muted">Arrearo stops chasing {inv.debtorName} and records {pounds(inv.totalOwedPence)} as recovered. Check the money has reached your account first.</p>
        <div className="acts">
          <Button variant="ghost" onClick={() => setConfirm(null)}>Not yet</Button>
          <Button variant="primary" loading={patch.isPending} onClick={() => run(patch.mutateAsync({ status: 'paid' }), 'Marked as paid. Nicely done.')}>Yes, it’s paid</Button>
        </div>
      </Dialog>

      <Dialog open={confirm === 'dispute'} onClose={() => setConfirm(null)} title="Mark as disputed?">
        <p className="muted">Arrearo pauses all automatic chasing while this is open, and any drafts waiting are withdrawn. You can resume at any time.</p>
        <div className="acts">
          <Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
          <Button loading={patch.isPending} onClick={() => run(patch.mutateAsync({ status: 'disputed' }), 'Chasing paused.')}>Pause chasing</Button>
        </div>
      </Dialog>

      <Dialog open={confirm === 'resume'} onClose={() => setConfirm(null)} title="Resume chasing?">
        <p className="muted">Arrearo will pick the chase up again on its normal schedule, with figures updated to today.</p>
        <div className="acts">
          <Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
          <Button variant="primary" loading={patch.isPending} onClick={() => run(patch.mutateAsync({ status: 'chasing' }), 'Chasing resumed.')}>Resume</Button>
        </div>
      </Dialog>

      <Dialog open={confirm === 'chase'} onClose={() => setConfirm(null)} title="Send a chase now?">
        <p className="muted">Arrearo writes a WhatsApp message to {inv.debtorName} with today’s figures ({pounds(inv.totalOwedPence)} including interest) and sends it straight away.</p>
        <div className="acts">
          <Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
          <Button variant="primary" icon="send" loading={chase.isPending} onClick={() => run(chase.mutateAsync(undefined), 'Chase sent on WhatsApp.')}>Send chase</Button>
        </div>
      </Dialog>

      <Dialog open={confirm === 'lba'} onClose={() => setConfirm(null)} title="Send the Letter Before Action?">
        <p className="muted">
          This is a formal step. The letter goes by email to {inv.debtorEmail ?? 'the debtor'} and gives them 14 days to pay {pounds(inv.totalOwedPence)} before you may issue a county court claim. You can’t unsend it.
        </p>
        <div className="acts">
          <Button variant="ghost" onClick={() => setConfirm(null)}>Review again</Button>
          <Button variant="copper" icon="send" loading={lba.isPending} onClick={() => run(lba.mutateAsync(lbaBody), 'Letter Before Action sent.')}>Send letter</Button>
        </div>
      </Dialog>
    </div>
  );
}
