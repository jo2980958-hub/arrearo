import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useInvoices } from '../api/hooks';
import type { Invoice } from '../api/types';
import { isLate, isOpen } from '../lib/interest';
import { pounds } from '../lib/money';
import { fmtDate } from '../lib/dates';
import { Icon } from '../components/icons';
import { ErrorState, RiskBadge, riskOf, Skeleton, StatusPill, usePageTitle } from '../components/ui';

type Filter = 'open' | 'overdue' | 'promised' | 'disputed' | 'lba' | 'paid' | 'all';
type SortKey = 'debtor' | 'status' | 'late' | 'amount' | 'total' | 'risk';

const FILTERS: { id: Filter; label: string; test: (i: Invoice) => boolean }[] = [
  { id: 'open', label: 'Open', test: isOpen },
  { id: 'overdue', label: 'Overdue', test: isLate },
  { id: 'promised', label: 'Promised', test: (i) => i.status === 'promised' },
  { id: 'disputed', label: 'Disputed', test: (i) => i.status === 'disputed' },
  { id: 'lba', label: 'Letter before action', test: (i) => i.status === 'lba' || i.status === 'escalated' },
  { id: 'paid', label: 'Paid', test: (i) => i.status === 'paid' },
  { id: 'all', label: 'All', test: () => true },
];

const riskRank = { high: 3, medium: 2, low: 1, unknown: 0 } as const;

const SORTERS: Record<SortKey, (a: Invoice, b: Invoice) => number> = {
  debtor: (a, b) => a.debtorName.localeCompare(b.debtorName),
  status: (a, b) => a.status.localeCompare(b.status),
  late: (a, b) => a.daysLate - b.daysLate,
  amount: (a, b) => a.amountPence - b.amountPence,
  total: (a, b) => a.totalOwedPence - b.totalOwedPence,
  risk: (a, b) => riskRank[riskOf(a)] - riskRank[riskOf(b)],
};

function lateClass(d: number) {
  return d > 60 ? 'hot' : d > 14 ? 'warm' : '';
}

function csv(rows: Invoice[]) {
  const head = ['Debtor', 'Reference', 'Status', 'Invoice date', 'Due', 'Days late', 'Amount (GBP)', 'Interest (GBP)', 'Fixed sum (GBP)', 'Total owed (GBP)'];
  const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const lines = rows.map((i) =>
    [i.debtorName, i.reference, i.status, i.invoiceDate, i.agreedDueDate ?? '', String(i.daysLate), (i.amountPence / 100).toFixed(2), (i.interestAccruedPence / 100).toFixed(2), (i.fixedRecoverySumPence / 100).toFixed(2), (i.totalOwedPence / 100).toFixed(2)]
      .map(esc)
      .join(','),
  );
  const blob = new Blob([[head.map(esc).join(','), ...lines].join('\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `arrearo-invoices-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function Invoices() {
  usePageTitle('Invoices');
  const q = useInvoices();
  const nav = useNavigate();
  const [filter, setFilter] = useState<Filter>('open');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'total', dir: -1 });

  const all = q.data ?? [];
  const counts = useMemo(() => Object.fromEntries(FILTERS.map((f) => [f.id, all.filter(f.test).length])) as Record<Filter, number>, [all]);
  const rows = useMemo(() => {
    const f = FILTERS.find((x) => x.id === filter)!;
    const term = query.trim().toLowerCase();
    return all
      .filter(f.test)
      .filter((i) => !term || `${i.debtorName} ${i.reference} ${i.description ?? ''}`.toLowerCase().includes(term))
      .sort((a, b) => SORTERS[sort.key](a, b) * sort.dir);
  }, [all, filter, query, sort]);

  const setSortKey = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: key === 'debtor' ? 1 : -1 }));
  const th = (key: SortKey, label: string, right = false) => (
    <th className={right ? 'r' : ''} aria-sort={sort.key === key ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button onClick={() => setSortKey(key)}>
        {label}
        {sort.key === key && <Icon name={sort.dir === 1 ? 'up' : 'down'} width={13} height={13} />}
      </button>
    </th>
  );

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Invoices</h1>
          <p className="sub">Every invoice Arrearo is tracking, with what the law adds to it.</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => csv(rows)} disabled={!rows.length}>
            <Icon name="download" />
            Export CSV
          </button>
          <Link to="/invoices/new" className="btn primary">
            <Icon name="plus" />
            Add invoice
          </Link>
        </div>
      </div>

      <div className="toolbar">
        <div className="search">
          <Icon name="search" />
          <input className="input" type="search" placeholder="Search debtor or reference" aria-label="Search invoices" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="chips" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button key={f.id} className="chip" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label}
              <span className="n">{counts[f.id] ?? 0}</span>
            </button>
          ))}
        </div>
      </div>

      {q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : q.isLoading ? (
        <div className="card card-pad stack">
          {[0, 1, 2, 3].map((n) => (
            <Skeleton key={n} h={40} />
          ))}
        </div>
      ) : (
        <div className="card tbl-wrap has-cards">
          {rows.length === 0 ? (
            <div className="empty">
              <b>No invoices here</b>
              {query ? 'Nothing matches that search.' : 'Add an invoice, or send a photo of one to Arrearo on WhatsApp.'}
            </div>
          ) : (
            <>
              <table className="tbl">
                <caption className="sr-only">Invoices</caption>
                <thead>
                  <tr>
                    {th('debtor', 'Debtor')}
                    {th('status', 'Status')}
                    {th('late', 'Days late', true)}
                    {th('amount', 'Invoice', true)}
                    {th('total', 'Total owed', true)}
                    {th('risk', 'Debtor risk')}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((i) => (
                    <tr key={i.invoiceId} onClick={() => nav(`/invoices/${i.invoiceId}`)}>
                      <td className="rel">
                        <div className="deb">
                          <Link to={`/invoices/${i.invoiceId}`}>{i.debtorName}</Link>
                        </div>
                        <div className="sub mono">{i.reference} · due {fmtDate(i.agreedDueDate)}</div>
                      </td>
                      <td><StatusPill status={i.status} /></td>
                      <td className={`r num late ${lateClass(i.daysLate)}`}>{i.status === 'paid' ? <span className="muted">{i.daysLate ? `${i.daysLate} (paid)` : '—'}</span> : i.daysLate || <span className="muted">—</span>}</td>
                      <td className="r num">{pounds(i.amountPence)}</td>
                      <td className="r num">
                        <b>{pounds(i.totalOwedPence)}</b>
                        {i.interestAccruedPence + i.fixedRecoverySumPence > 0 && (
                          <div className="plus">+{pounds(i.interestAccruedPence + i.fixedRecoverySumPence)} by law</div>
                        )}
                      </td>
                      <td><RiskBadge band={riskOf(i)} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="cards">
                {rows.map((i) => (
                  <div key={i.invoiceId} className="icard">
                    <div className="row">
                      <b><Link to={`/invoices/${i.invoiceId}`}>{i.debtorName}</Link></b>
                      <StatusPill status={i.status} />
                    </div>
                    <div className="row">
                      <span className="muted mono" style={{ fontSize: 13 }}>{i.reference}</span>
                      <span className={`num late ${lateClass(i.daysLate)}`} style={{ fontWeight: 600 }}>{i.daysLate > 0 ? `${i.daysLate} days late` : 'Not late'}</span>
                    </div>
                    <div className="row">
                      <RiskBadge band={riskOf(i)} />
                      <span className="num"><b>{pounds(i.totalOwedPence)}</b></span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
