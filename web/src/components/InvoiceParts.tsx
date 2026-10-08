import { useState } from 'react';
import type { Debtor, Draft, Invoice, InvoiceEvent, ThreadMessage } from '../api/types';
import { interestBasis, isAccruing, isLate, pct } from '../lib/interest';
import { pounds } from '../lib/money';
import { fmtDate, fmtDateTime, fmtTime } from '../lib/dates';
import { Icon, type IconName } from './icons';
import { Button, LiveMoney, RiskBadge, riskOf } from './ui';

/* ================================================================ owed */

export function OwedCard({ inv }: { inv: Invoice }) {
  const b = interestBasis(inv);
  const accruing = isAccruing(inv);
  const late = isLate(inv);
  const paid = inv.status === 'paid';
  return (
    <section className="card owed" aria-labelledby="owed-h">
      <p className="eyebrow" id="owed-h">{paid ? 'Settled' : 'Total owed now'}</p>
      <p className="owed-total">
        {accruing ? <LiveMoney base={inv.totalOwedPence} perSecond={b.perSecondPence} /> : <span className="num">{pounds(inv.totalOwedPence)}</span>}
      </p>
      <p className="muted" style={{ fontSize: 14 }}>
        {paid
          ? `Paid on ${fmtDate(inv.paidAt)}`
          : late
            ? `${inv.daysLate} days past the legal due date, and growing by ${pounds(b.dailyPence)} a day`
            : `Not late yet. Interest starts after ${fmtDate(inv.agreedDueDate)}.`}
      </p>

      <ul className="owed-lines">
        <li>
          <span>Invoice {inv.reference}</span>
          <b className="num">{pounds(inv.amountPence)}</b>
        </li>
        <li>
          <span>Statutory interest{inv.daysLate > 0 ? ` (${inv.daysLate} days)` : ''}</span>
          <b className="num interest">
            {accruing ? <LiveMoney base={inv.interestAccruedPence} perSecond={b.perSecondPence} /> : pounds(inv.interestAccruedPence)}
          </b>
        </li>
        <li>
          <span>Fixed recovery sum</span>
          <b className="num interest">{pounds(inv.fixedRecoverySumPence)}</b>
        </li>
      </ul>

      <div className="basis">
        <b>Legal basis.</b>{' '}
        <span className="eq">
          {b.addonPct}% + {pct(b.basePct)} Bank of England base = {pct(b.ratePct)}/yr, {pounds(b.dailyPence)}/day
        </span>
        <small>
          Late Payment of Commercial Debts (Interest) Act 1998. The fixed recovery sum is £40 under £1,000, £70 from £1,000 to £9,999.99, and £100 from £10,000.
          {inv.debtorType === 'individual' ? ' This debtor is an individual, so the Pre-Action Protocol for Debt Claims applies before any claim.' : ''}
        </small>
      </div>
    </section>
  );
}

/* ========================================================== timeline */

const STAGES = [
  { id: 'detect', label: 'Detect', types: ['created', 'extracted', 'confirmed', 'debtor_scored'] },
  { id: 'chase', label: 'Chase', types: ['due', 'chased'] },
  { id: 'reply', label: 'Reply', types: ['replied', 'promised', 'disputed'] },
  { id: 'lba', label: 'LBA', types: ['lba_drafted', 'lba_sent'] },
  { id: 'paid', label: 'Paid', types: ['paid'] },
] as const;

const STATUS_STAGE: Record<Invoice['status'], number> = {
  extracted: 0, confirmed: 0, due: 1, chasing: 1, promised: 2, disputed: 2, lba: 3, escalated: 3, paid: 4,
};

export function Stepper({ inv, events }: { inv: Invoice; events: InvoiceEvent[] }) {
  const has = STAGES.map((s) => events.filter((e) => (s.types as readonly string[]).includes(e.type)));
  let current = -1;
  has.forEach((h, i) => { if (h.length) current = i; });
  current = Math.max(current, events.length ? 0 : STATUS_STAGE[inv.status]);
  if (inv.status === 'paid') current = 4;
  else current = Math.max(current, Math.min(STATUS_STAGE[inv.status], 3));

  const sub = (i: number): string => {
    const h = has[i];
    if (!h.length) return i > current ? '' : 'Skipped';
    const last = h[h.length - 1];
    if (i === 1) return `${h.filter((e) => e.type === 'chased').length} sent`;
    if (i === 2) return last.type === 'disputed' ? 'Disputed' : last.type === 'promised' ? 'Promised' : 'Replied';
    if (i === 3) return last.type === 'lba_sent' ? 'Sent' : 'Drafted';
    return fmtDate(last.createdAt).replace(/ \d{4}$/, '');
  };

  return (
    <ol className="stepper" aria-label="Recovery progress">
      {STAGES.map((s, i) => {
        const done = i < current ? has[i].length > 0 : i === current && inv.status === 'paid';
        const skipped = i < current && !has[i].length;
        const isCurrent = i === current && !done;
        const bad = isCurrent && (inv.status === 'disputed' || inv.status === 'lba' || inv.status === 'escalated');
        const cls = done ? 'done' : skipped ? 'skipped' : isCurrent ? 'current' : 'pending';
        return (
          <li key={s.id} className={`step ${cls} ${bad ? 'alert-step' : ''}`} aria-current={isCurrent ? 'step' : undefined}>
            <span className="dot">{done ? <Icon name="check" /> : i + 1}</span>
            <b>{s.label}</b>
            <small>{sub(i)}</small>
          </li>
        );
      })}
    </ol>
  );
}

function describe(e: InvoiceEvent): { icon: IconName; title: string; quote?: string; tone: string } {
  const d = e.detail as Record<string, unknown>;
  const body = typeof d.body === 'string' ? d.body : undefined;
  const tone = e.actor === 'agent' ? 'agent' : e.actor === 'debtor' ? 'debtor' : '';
  switch (e.type) {
    case 'created':
      return { icon: e.channel === 'whatsapp' ? 'camera' : 'plus', title: e.channel === 'whatsapp' ? 'Invoice photo received on WhatsApp' : 'Invoice added from the dashboard', tone };
    case 'extracted':
      return { icon: 'sparkle', title: `Arrearo read the invoice${typeof d.confidence === 'number' ? ` (${Math.round((d.confidence as number) * 100)}% sure)` : ''}`, tone: 'agent' };
    case 'confirmed':
      return { icon: 'check', title: 'Invoice confirmed, tracking started', tone };
    case 'debtor_scored': {
      const band = d.riskBand as string;
      return { icon: 'shield', title: band && band !== 'unknown' ? `Debtor risk checked: ${band} risk` : 'Debtor risk checked: no payment data on record', tone: 'agent' };
    }
    case 'due':
      return { icon: 'clock', title: 'Invoice reached its due date', tone: '' };
    case 'chased':
      return { icon: e.channel === 'email' ? 'mail' : 'chat', title: `${e.channel === 'email' ? 'Email' : 'WhatsApp'} chase sent${e.actor === 'owner' ? ', approved by you' : ''}`, quote: body, tone: 'agent' };
    case 'replied':
      return { icon: 'chat', title: 'Debtor replied', quote: body, tone: 'debtor' };
    case 'promised':
      return { icon: 'check', title: `Promise to pay recorded${d.promisedDate ? ` for ${fmtDate(String(d.promisedDate))}` : ''}`, quote: body, tone: 'debtor' };
    case 'disputed':
      return { icon: 'pause', title: 'Invoice disputed', quote: (d.reason as string) ?? body, tone: 'bad' };
    case 'lba_drafted':
      return { icon: 'scale', title: 'Letter Before Action drafted', quote: d.reason as string | undefined, tone: 'agent' };
    case 'lba_sent':
      return { icon: 'mail', title: `Letter Before Action emailed${d.to ? ` to ${d.to}` : ''}`, tone: 'bad' };
    case 'paid':
      return { icon: 'check', title: 'Marked as paid', tone: 'agent' };
    case 'digest':
      return { icon: 'mail', title: 'Included in your morning digest', tone: '' };
    case 'compliance_block':
      return { icon: 'shield', title: 'Held back by the compliance check', quote: d.note as string | undefined, tone: 'bad' };
    default:
      return { icon: 'info', title: String(e.type), tone: '' };
  }
}

export function EventList({ events }: { events: InvoiceEvent[] }) {
  const list = [...events].reverse();
  if (!list.length) return <div className="empty">No activity yet.</div>;
  return (
    <ol className="events" aria-label="Activity, newest first">
      {list.map((e, i) => {
        const x = describe(e);
        return (
          <li key={`${e.createdAt}-${e.seq ?? i}`} className={`event ${x.tone}`}>
            <span className="pt"><Icon name={x.icon} /></span>
            <div>
              <b>{x.title}</b>
              <div className="when">{fmtDateTime(e.createdAt)}</div>
              {x.quote && <div className="quote">{x.quote}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* ============================================================== drafts */

const DRAFT_TITLE: Record<Draft['kind'], string> = {
  whatsapp_chase: 'WhatsApp chase',
  email_chase: 'Email chase',
  lba: 'Letter Before Action',
};

export function DraftCard({
  inv,
  draft,
  busy,
  onSend,
}: {
  inv: Invoice;
  draft: Draft;
  busy: boolean;
  onSend: (body: string | undefined) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(draft.body);
  const isLba = draft.kind === 'lba';
  const changed = text !== draft.body;
  const recipient = isLba || draft.kind === 'email_chase' ? inv.debtorEmail : inv.debtorWhatsapp;
  const blocked = draft.status === 'blocked' || !draft.complianceOk;

  return (
    <section className="card draft" aria-label={`${DRAFT_TITLE[draft.kind]} awaiting approval`}>
      <div className="draft-head">
        <b>
          <Icon name={isLba ? 'scale' : 'chat'} />
          {DRAFT_TITLE[draft.kind]} waiting for you
        </b>
        {blocked ? (
          <span className="badge-ok" style={{ color: 'var(--red-700)' }}>
            <Icon name="alert" /> Held by compliance check
          </span>
        ) : (
          <span className="badge-ok">
            <Icon name="shield" /> Compliance check passed
          </span>
        )}
      </div>
      <div className="draft-body">
        {editing ? (
          <>
            <label className="sr-only" htmlFor={`edit-${draft.draftId}`}>Edit message</label>
            <textarea id={`edit-${draft.draftId}`} className="textarea" style={{ minHeight: isLba ? 320 : 220 }} value={text} onChange={(e) => setText(e.target.value)} />
          </>
        ) : isLba ? (
          <div className="letter">{text}</div>
        ) : (
          <div className="bubble">{text}</div>
        )}
      </div>
      <div className="draft-foot">
        <span className="grow">
          {recipient ? `To ${recipient}` : 'No contact on file for this debtor'}
          {changed && ' · edited'}
        </span>
        <Button size="sm" variant="ghost" icon={editing ? 'check' : 'edit'} onClick={() => setEditing((v) => !v)}>
          {editing ? 'Done editing' : 'Edit'}
        </Button>
        <Button size="sm" variant={isLba ? 'copper' : 'primary'} icon="send" loading={busy} disabled={blocked || !recipient || !text.trim()} onClick={() => onSend(changed ? text : undefined)}>
          {isLba ? 'Approve and send letter' : 'Approve and send'}
        </Button>
      </div>
    </section>
  );
}

/* ========================================================= debtor risk */

export function RiskPanel({ inv, debtor }: { inv: Invoice; debtor?: Debtor | null }) {
  const band = debtor?.riskBand ?? riskOf(inv);
  const known = debtor && debtor.source === 'payment-practices' && debtor.avgDaysToPay != null;
  const terms = 30;
  const slip = known ? Math.round((debtor!.avgDaysToPay as number) - terms) : 0;
  const a = debtor?.pctPaidWithin30 ?? 0;
  const b = debtor?.pct31to60 ?? 0;
  const c = debtor?.pct60plus ?? 0;

  return (
    <section className="card risk-card" aria-labelledby="risk-h">
      <div className="risk-top">
        <h2 className="card-title" id="risk-h">Debtor risk</h2>
        <RiskBadge band={band} />
      </div>
      {known ? (
        <>
          <p className="risk-big" style={{ marginTop: 16 }}>
            {Math.round(debtor!.avgDaysToPay as number)}<small>days to pay, on average</small>
          </p>
          <p className="muted" style={{ fontSize: 14, marginTop: 6 }}>
            {slip > 0 ? `That is ${slip} days beyond standard 30-day terms.` : 'That is within standard 30-day terms.'}
          </p>
          <div className="dist" role="img" aria-label={`${a}% paid within 30 days, ${b}% in 31 to 60 days, ${c}% after 60 days`}>
            <i className="a" style={{ width: `${a}%` }} />
            <i className="b" style={{ width: `${b}%` }} />
            <i className="c" style={{ width: `${c}%` }} />
          </div>
          <div className="legend">
            <div><i style={{ background: 'var(--green-600)' }} />Within 30 days<b>{a}%</b></div>
            <div><i style={{ background: '#c88a14' }} />31 to 60 days<b>{b}%</b></div>
            <div><i style={{ background: 'var(--red-700)' }} />Over 60 days<b>{c}%</b></div>
          </div>
          <dl className="kv">
            <dt>Paid late</dt><dd className="num">{debtor!.pctPaidLate ?? '—'}%</dd>
            <dt>Invoices disputed</dt><dd className="num">{debtor!.pctInvoicesDisputed ?? '—'}%</dd>
            <dt>Report period ends</dt><dd>{fmtDate(debtor!.reportPeriodEnd)}</dd>
            <dt>Source</dt><dd>UK payment practices reporting</dd>
          </dl>
        </>
      ) : (
        <p className="muted" style={{ marginTop: 14, fontSize: 14.5 }}>
          There is no published payment-practices report for this debtor, so Arrearo does not guess. It builds a picture
          from how they actually pay you.
        </p>
      )}
    </section>
  );
}

/* =============================================================== thread */

function PhotoMock() {
  return (
    <div className="photo" aria-label="Photo of the invoice">
      <i className="t" /><i className="s" /><i className="m" /><i /><i className="m" /><i className="s" />
      <div className="tot"><i /><i /></div>
    </div>
  );
}

const INTENT: Record<string, string> = {
  promise_to_pay: 'Promise to pay',
  dispute: 'Dispute',
  not_received: 'Says not received',
  paid: 'Says paid',
  question: 'Question',
};

export function Thread({ inv, messages }: { inv: Invoice; messages: ThreadMessage[] }) {
  if (!messages.length) {
    return (
      <div className="card empty">
        <b>No messages yet</b>
        Messages appear here once Arrearo captures this invoice or chases the debtor on WhatsApp.
      </div>
    );
  }
  let lastThread = '';
  let lastDay = '';
  return (
    <div className="chat-wrap">
      <div className="phone">
        <div className="phone-bar">
          <div className="avatar" aria-hidden="true">A</div>
          <div>
            <b>Arrearo</b>
            <small>Everything said about invoice {inv.reference}</small>
          </div>
        </div>
        <div className="chat" role="log" aria-label="WhatsApp conversation">
          {messages.map((m) => {
            const seps: React.ReactNode[] = [];
            const day = fmtDate(m.at);
            if (m.thread !== lastThread) {
              seps.push(
                <div key={`t-${m.id}`} className="chat-sep">
                  {m.thread === 'owner' ? 'You and Arrearo' : `Arrearo and ${inv.debtorName}`}
                </div>,
              );
              lastThread = m.thread;
              lastDay = '';
            }
            if (day !== lastDay) {
              seps.push(<div key={`d-${m.id}`} className="chat-sep" style={{ margin: '4px 0' }}>{day}</div>);
              lastDay = day;
            }
            return (
              <div key={m.id} style={{ display: 'contents' }}>
                {seps}
                <div className={`msg ${m.direction}`}>
                  {m.hasMedia && <PhotoMock />}
                  {m.body}
                  {m.intent && INTENT[m.intent] && <div><span className="tag">Understood: {INTENT[m.intent]}</span></div>}
                  <time dateTime={m.at}>{fmtTime(m.at)}</time>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
