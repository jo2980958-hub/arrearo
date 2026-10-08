import { useMemo } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { useInvoices } from '../api/hooks';
import type { Business, Invoice } from '../api/types';
import { attentionItems, type AttentionItem } from '../lib/attention';
import { interestBasis, isAccruing, isLate, isOpen } from '../lib/interest';
import { pounds, poundsWhole } from '../lib/money';
import { fmtLongToday } from '../lib/dates';
import { Icon, type IconName } from '../components/icons';
import { ErrorState, LiveMoney, Skeleton, usePageTitle } from '../components/ui';
import { FALLBACK_BASE_RATE_PCT, STATUTORY_ADDON_PCT } from '../config';

const KIND_ICON: Record<AttentionItem['kind'], { icon: IconName; bg: string; fg: string }> = {
  lba: { icon: 'scale', bg: 'var(--red-100)', fg: 'var(--red-700)' },
  dispute: { icon: 'pause', bg: 'var(--plum-100)', fg: 'var(--plum-700)' },
  chase: { icon: 'chat', bg: 'var(--green-100)', fg: 'var(--green-700)' },
  confirm: { icon: 'camera', bg: 'var(--amber-100)', fg: 'var(--amber-700)' },
};

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}

function summarise(invoices: Invoice[]) {
  const live = invoices.filter((i) => isOpen(i) && i.status !== 'extracted');
  const late = live.filter(isLate);
  const accruing = live.filter(isAccruing);
  const paid = invoices.filter((i) => i.status === 'paid');
  const promised = live.filter((i) => i.status === 'promised');
  const principal = live.reduce((s, i) => s + i.amountPence, 0);
  const interest = accruing.reduce((s, i) => s + i.interestAccruedPence, 0);
  const fixed = live.reduce((s, i) => s + i.fixedRecoverySumPence, 0);
  const perSecond = accruing.reduce((s, i) => s + interestBasis(i).perSecondPence, 0);
  const perDay = accruing.reduce((s, i) => s + interestBasis(i).dailyPence, 0);
  const recovered = paid.reduce((s, i) => s + i.totalOwedPence, 0);
  const recoveredInterest = paid.reduce((s, i) => s + i.interestAccruedPence + i.fixedRecoverySumPence, 0);
  const avgLate = late.length ? Math.round(late.reduce((s, i) => s + i.daysLate, 0) / late.length) : 0;
  const buckets = [
    { label: 'Not yet due', test: (d: number) => d === 0 },
    { label: '1 to 30 days', test: (d: number) => d >= 1 && d <= 30 },
    { label: '31 to 60', test: (d: number) => d >= 31 && d <= 60 },
    { label: '61 to 90', test: (d: number) => d >= 61 && d <= 90 },
    { label: 'Over 90', test: (d: number) => d > 90 },
  ].map((b) => ({ ...b, amount: live.filter((i) => b.test(i.daysLate)).reduce((s, i) => s + i.amountPence, 0), n: live.filter((i) => b.test(i.daysLate)).length }));
  const biggest = [...live].sort((a, b) => b.totalOwedPence - a.totalOwedPence).slice(0, 5);
  return { live, late, principal, interest, fixed, perSecond, perDay, recovered, recoveredInterest, avgLate, promised, buckets, biggest, paidCount: paid.length };
}

export default function Overview() {
  usePageTitle('Overview');
  const { business } = useOutletContext<{ business: Business }>();
  const q = useInvoices();
  const s = useMemo(() => summarise(q.data ?? []), [q.data]);
  const todo = useMemo(() => attentionItems(q.data ?? []), [q.data]);
  const rate = FALLBACK_BASE_RATE_PCT + STATUTORY_ADDON_PCT;

  const firstName = business.ownerName?.split(' ')[0] ?? '';

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">{fmtLongToday()}</p>
          <h1 style={{ marginTop: 6 }}>
            {greeting()}
            {firstName ? `, ${firstName}` : ''}
          </h1>
        </div>
        <div className="actions">
          <Link to="/invoices/new" className="btn primary">
            <Icon name="plus" />
            Add invoice
          </Link>
        </div>
      </div>

      {q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : q.isLoading ? (
        <div className="stack">
          <Skeleton h={190} />
          <Skeleton h={100} />
        </div>
      ) : (
        <>
          <section className="card hero" aria-label="Portfolio summary">
            <div className="hero-grid">
              <div className="hero-cell">
                <p className="eyebrow">Outstanding</p>
                <p className="hero-figure num">{poundsWhole(s.principal)}</p>
                <p className="foot">
                  <span>
                    {s.live.length} open invoice{s.live.length === 1 ? '' : 's'}
                  </span>
                  <span>·</span>
                  <span>{pounds(s.principal + s.interest + s.fixed)} with interest and fixed sums</span>
                </p>
              </div>
              <div className="hero-cell">
                <p className="live">
                  <i /> Interest accruing
                </p>
                <p className="hero-figure copper" aria-label={`Interest accrued so far ${pounds(s.interest)}`}>
                  <LiveMoney base={s.interest} perSecond={s.perSecond} />
                </p>
                <p className="foot">
                  <span>+{pounds(s.perDay)} every day</span>
                  <span>·</span>
                  <span>{rate}% a year, set by law</span>
                </p>
              </div>
            </div>
          </section>

          <div className="stats">
            <div className="card stat">
              <p className="eyebrow">Overdue</p>
              <p className="v">{s.late.length}</p>
              <p className="d">{s.avgLate ? `${s.avgLate} days late on average` : 'Nothing is late'}</p>
            </div>
            <div className="card stat">
              <p className="eyebrow">Recovered</p>
              <p className="v">{poundsWhole(s.recovered)}</p>
              <p className="d">
                {s.paidCount} paid{s.recoveredInterest > 0 ? `, incl. ${pounds(s.recoveredInterest)} interest and fees` : ''}
              </p>
            </div>
            <div className="card stat">
              <p className="eyebrow">Promised</p>
              <p className="v">{poundsWhole(s.promised.reduce((t, i) => t + i.amountPence, 0))}</p>
              <p className="d">
                {s.promised.length} debtor{s.promised.length === 1 ? '' : 's'} committed to pay
              </p>
            </div>
            <div className="card stat">
              <p className="eyebrow">Fixed recovery sums</p>
              <p className="v">{poundsWhole(s.fixed)}</p>
              <p className="d">Claimable on late invoices</p>
            </div>
          </div>

          <div className="two-col">
            <section className="card" aria-labelledby="todo-h">
              <div className="card-head">
                <h2 id="todo-h">Needs your attention</h2>
                <span className="sub">{todo.length ? `${todo.length} to do` : 'All clear'}</span>
              </div>
              {todo.length === 0 ? (
                <div className="empty">
                  <b>Nothing waiting on you</b>
                  Arrearo is watching every invoice and will tell you when a decision is needed.
                </div>
              ) : (
                <ul className="todo">
                  {todo.map((t) => {
                    const k = KIND_ICON[t.kind];
                    return (
                      <li key={`${t.invoice.invoiceId}-${t.kind}`}>
                        <Link to={`/invoices/${t.invoice.invoiceId}`}>
                          <span className="ico" style={{ ['--bg' as string]: k.bg, ['--fg' as string]: k.fg }}>
                            <Icon name={k.icon} />
                          </span>
                          <span>
                            <b>{t.title}</b>
                            <small>{t.detail}</small>
                          </span>
                          <span className="go">
                            {t.cta}
                            <Icon name="arrowRight" />
                          </span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <div className="stack">
              <section className="card" aria-labelledby="age-h">
                <div className="card-head">
                  <h2 id="age-h">How late is it?</h2>
                  <span className="sub">By invoice value</span>
                </div>
                <div className="age">
                  {s.buckets.map((b, i) => {
                    const max = Math.max(...s.buckets.map((x) => x.amount), 1);
                    return (
                      <div key={b.label} className={`age-row l${i}`}>
                        <span>{b.label}</span>
                        <div className="track" role="img" aria-label={`${b.n} invoices, ${pounds(b.amount)}`}>
                          <div className="fill" style={{ width: `${Math.max(b.amount ? 3 : 0, (b.amount / max) * 100)}%` }} />
                        </div>
                        <span className="amt num">{poundsWhole(b.amount)}</span>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="card" aria-labelledby="big-h">
                <div className="card-head">
                  <h2 id="big-h">Biggest debts</h2>
                  <span className="sub">Total owed</span>
                </div>
                <ul className="leader">
                  {s.biggest.map((i) => (
                    <li key={i.invoiceId}>
                      <Link to={`/invoices/${i.invoiceId}`}>
                        <b>{i.debtorName}</b>
                        <span className="muted" style={{ display: 'block', fontSize: 13 }}>
                          {i.reference} · {i.daysLate > 0 ? `${i.daysLate} days late` : 'not yet late'}
                        </span>
                      </Link>
                      <b className="num">{pounds(i.totalOwedPence)}</b>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
