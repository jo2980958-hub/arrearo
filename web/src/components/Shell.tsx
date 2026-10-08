import { useMemo } from 'react';
import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useInvoices, useMe } from '../api/hooks';
import { attentionItems } from '../lib/attention';
import { FALLBACK_BASE_RATE_PCT, STATUTORY_ADDON_PCT } from '../config';
import { Icon, LogoMark } from './icons';
import { ErrorState, Skeleton } from './ui';

const NAV = [
  { to: '/', label: 'Overview', icon: 'overview', end: true },
  { to: '/invoices', label: 'Invoices', icon: 'invoices', end: false },
  { to: '/invoices/new', label: 'Add invoice', icon: 'plus', end: true },
  { to: '/settings', label: 'Settings', icon: 'settings', end: true },
] as const;

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('');
}

export default function Shell() {
  const auth = useAuth();
  const loc = useLocation();
  const me = useMe();
  const invoices = useInvoices();
  const attention = useMemo(() => attentionItems(invoices.data ?? []).length, [invoices.data]);

  if (!auth.signedIn) return <Navigate to="/login" replace />;

  if (me.isLoading) {
    return (
      <div className="page" style={{ maxWidth: 560, paddingTop: 80 }}>
        <Skeleton h={34} w="60%" />
        <div style={{ height: 16 }} />
        <Skeleton h={120} />
      </div>
    );
  }
  if (me.isError) {
    return (
      <div className="page" style={{ maxWidth: 560, paddingTop: 80 }}>
        <ErrorState error={me.error} retry={() => me.refetch()} />
      </div>
    );
  }

  const b = me.data!.business;
  const skipped = (() => {
    try {
      return sessionStorage.getItem('arrearo.onboarding-skipped') === '1';
    } catch {
      return false;
    }
  })();
  const incomplete = !b.name || !b.bankSortCode || !b.bankAccount;
  if (incomplete && !skipped && loc.pathname !== '/settings') return <Navigate to="/onboarding" replace />;

  const rate = FALLBACK_BASE_RATE_PCT + STATUTORY_ADDON_PCT;

  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <aside className="sidebar" aria-label="Primary">
        <div className="brand">
          <LogoMark />
          Arrearo
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}>
              <Icon name={n.icon} />
              {n.label}
              {n.to === '/' && attention > 0 && <span className="count" aria-label={`${attention} need attention`}>{attention}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="rate-note">
            Statutory interest today
            <b className="num">{rate}%</b>
            8% plus {FALLBACK_BASE_RATE_PCT}% Bank of England base rate
          </div>
          <div className="who">
            <div className="avatar" aria-hidden="true">{initials(b.name)}</div>
            <div className="who-text">
              <b>{b.name}</b>
              <span>{auth.email}</span>
            </div>
            <button className="icon-btn" onClick={auth.signOut} aria-label="Sign out" title="Sign out">
              <Icon name="logout" />
            </button>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="mobilebar">
          <div className="brand">
            <LogoMark size={28} />
            Arrearo
          </div>
          <button className="icon-btn" onClick={auth.signOut} aria-label="Sign out">
            <Icon name="logout" />
          </button>
        </header>
        <main id="main" tabIndex={-1}>
          <Outlet context={{ business: b }} />
        </main>
      </div>

      <nav className="tabbar" aria-label="Main">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end}>
            <Icon name={n.icon} />
            {n.label === 'Add invoice' ? 'Add' : n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
