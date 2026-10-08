import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Debtor, InvoiceStatus, RiskBand } from '../api/types';
import { Icon } from './icons';
import { splitTicker } from '../lib/money';

/* ---------------------------------------------------------------- status */

export const STATUS_LABEL: Record<InvoiceStatus, string> = {
  extracted: 'Needs confirming',
  confirmed: 'Tracking',
  due: 'Due',
  chasing: 'Chasing',
  promised: 'Promised',
  disputed: 'Disputed',
  paid: 'Paid',
  lba: 'Letter before action',
  escalated: 'Escalated',
};

export function StatusPill({ status }: { status: InvoiceStatus }) {
  return <span className={`pill s-${status}`}>{STATUS_LABEL[status]}</span>;
}

const RISK_LABEL = { low: 'Low risk', medium: 'Medium risk', high: 'High risk', unknown: 'No data' } as const;

export function RiskBadge({ band }: { band?: RiskBand | 'unknown' | null }) {
  const b = band ?? 'unknown';
  return (
    <span className={`risk ${b}`}>
      {b !== 'unknown' && (
        <span className="bars" aria-hidden="true">
          <i /><i /><i />
        </span>
      )}
      {RISK_LABEL[b]}
    </span>
  );
}

export function riskOf(inv: { riskBand?: RiskBand | 'unknown'; debtor?: Debtor | null }): RiskBand | 'unknown' {
  return inv.riskBand ?? inv.debtor?.riskBand ?? 'unknown';
}

/* ------------------------------------------------------------ live ticker */

/**
 * A figure that visibly accrues. `base` is the value at mount, `perSecond` the
 * (fractional) pence added each second. Renders to 4dp with the sub-penny
 * digits dimmed so the tick is visible.
 */
export function LiveMoney({ base, perSecond, className }: { base: number; perSecond: number; className?: string }) {
  const [value, setValue] = useState(base);
  const t0 = useRef(performance.now());
  const baseRef = useRef(base);

  useEffect(() => {
    baseRef.current = base;
    t0.current = performance.now();
    setValue(base);
  }, [base]);

  useEffect(() => {
    if (perSecond <= 0) return;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const step = reduce ? 5000 : 200;
    const timer = window.setInterval(() => {
      setValue(baseRef.current + ((performance.now() - t0.current) / 1000) * perSecond);
    }, step);
    return () => window.clearInterval(timer);
  }, [perSecond]);

  const { main, fine } = splitTicker(value);
  return (
    <span className={`num ${className ?? ''}`}>
      {main}
      <span className="ticker-fine">{fine}</span>
    </span>
  );
}

/* ---------------------------------------------------------------- toasts */

interface Toast { id: number; text: string; kind: 'ok' | 'err' }
const ToastCtx = createContext<(text: string, kind?: Toast['kind']) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: Toast['kind'] = 'ok') => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, kind }]);
    window.setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4800);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind === 'err' ? 'err' : ''}`}>
            <Icon name={t.kind === 'err' ? 'alert' : 'check'} />
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------------------------------------------------------- dialog */

export function Dialog({
  open,
  onClose,
  title,
  children,
  labelledBy = 'dlg-title',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  labelledBy?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={labelledBy}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      {open && (
        <div className="dlg">
          <h2 id={labelledBy}>{title}</h2>
          {children}
        </div>
      )}
    </dialog>
  );
}

/* ------------------------------------------------------------------ misc */

export function Button({
  variant = 'secondary',
  size,
  loading,
  icon,
  children,
  className = '',
  ...rest
}: {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'copper';
  size?: 'sm';
  loading?: boolean;
  icon?: Parameters<typeof Icon>[0]['name'];
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      type={rest.type ?? 'button'}
      disabled={rest.disabled || loading}
      className={`btn ${variant === 'secondary' ? '' : variant} ${size ?? ''} ${className}`}
    >
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  full,
  htmlFor,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  full?: boolean;
  htmlFor: string;
}) {
  return (
    <div className={`field ${full ? 'full' : ''}`}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && !error && <span className="hint" id={`${htmlFor}-hint`}>{hint}</span>}
      {error && <span className="err" id={`${htmlFor}-err`} role="alert">{error}</span>}
    </div>
  );
}

export function Skeleton({ h = 20, w = '100%' }: { h?: number; w?: number | string }) {
  return <div className="skeleton" style={{ height: h, width: w }} aria-hidden="true" />;
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="alert err" role="alert">
      <Icon name="alert" />
      <div style={{ flex: 1 }}>
        <b>We couldn’t load this.</b>
        <div>{error instanceof Error ? error.message : 'Something went wrong.'}</div>
      </div>
      {retry && <Button size="sm" onClick={retry}>Try again</Button>}
    </div>
  );
}

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Arrearo`;
  }, [title]);
}
