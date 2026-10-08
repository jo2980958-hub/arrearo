const dmy = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const dm = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' });
const hm = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' });
const long = new Intl.DateTimeFormat('en-GB', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
});

export function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? '—' : dmy.format(d);
}

export function fmtDayMonth(iso: string): string {
  return dm.format(new Date(iso));
}

export function fmtTime(iso: string): string {
  return hm.format(new Date(iso));
}

export function fmtDateTime(iso: string): string {
  return `${fmtDate(iso)}, ${fmtTime(iso)}`;
}

export function fmtLongToday(): string {
  return long.format(new Date());
}

export function relative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return fmtDate(iso);
}

export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function todayIso(): string {
  return isoDate(new Date());
}
