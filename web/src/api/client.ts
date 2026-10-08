import { API_URL, DEMO } from '../config';
import { deriveMoney } from './derive';
import { demoApi } from './demo';
import type {
  Business,
  Debtor,
  Draft,
  Invoice,
  InvoiceEvent,
  InvoicePatch,
  Me,
  NewInvoiceInput,
  ThreadMessage,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/* The auth layer registers how to get a bearer token and what to do on 401. */
let tokenProvider: () => Promise<string | null> = async () => null;
let unauthorizedHandler: () => void = () => {};
export function configureAuth(p: () => Promise<string | null>, onUnauthorized: () => void) {
  tokenProvider = p;
  unauthorizedHandler = onUnauthorized;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API_URL) throw new ApiError(0, 'VITE_API_URL is not set. Build with the deployed API URL, or use VITE_DEMO=1.');
  const token = await tokenProvider();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(0, "Can't reach Arrearo. Check your connection and try again.");
  }
  if (res.status === 401) {
    unauthorizedHandler();
    throw new ApiError(401, 'Your session has expired. Please sign in again.');
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      message = j.message ?? j.error ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ------------------------------------------------------------ normalisation */

type Raw = Record<string, unknown>;

function list<T>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    for (const k of keys) {
      const v = (data as Raw)[k];
      if (Array.isArray(v)) return v as T[];
    }
  }
  return [];
}

export function normaliseInvoice(raw: Raw): Invoice {
  const r = raw as unknown as Invoice;
  const amountPence = Number(r.amountPence ?? 0);
  const needsDerive = r.totalOwedPence == null || r.daysLate == null;
  const derived = needsDerive
    ? deriveMoney({
        amountPence,
        invoiceDate: r.invoiceDate,
        deliveryDate: r.deliveryDate,
        agreedDueDate: r.agreedDueDate,
        debtorType: r.debtorType ?? 'company',
        paidAt: r.paidAt ? r.paidAt.slice(0, 10) : null,
      })
    : null;
  return {
    ...r,
    amountPence,
    currency: r.currency ?? 'GBP',
    debtorType: r.debtorType ?? 'company',
    daysLate: r.daysLate ?? derived?.daysLate ?? 0,
    interestAccruedPence: r.interestAccruedPence ?? derived?.interestAccruedPence ?? 0,
    fixedRecoverySumPence: r.fixedRecoverySumPence ?? derived?.fixedRecoverySumPence ?? 0,
    totalOwedPence: r.totalOwedPence ?? derived?.totalOwedPence ?? amountPence,
    statutoryRatePct: r.statutoryRatePct ?? derived?.statutoryRatePct,
    baseRatePct: r.baseRatePct ?? derived?.baseRatePct,
    legallyLateDate: r.legallyLateDate ?? derived?.legallyLateDate ?? null,
  };
}

function normaliseMe(data: unknown): Me {
  const d = data as Raw;
  const business = (d.business ?? d) as unknown as Business;
  return { business, email: String(d.email ?? business.email ?? ''), plan: d.plan as string | undefined };
}

/** Build the chat transcript from the audit events when the API sends no messages. */
export function threadFromEvents(events: InvoiceEvent[]): ThreadMessage[] {
  const out: ThreadMessage[] = [];
  for (const e of events) {
    const body = typeof e.detail.body === 'string' ? e.detail.body : '';
    const base = { id: `${e.invoiceId}-${e.seq ?? e.createdAt}`, at: e.createdAt };
    if (e.type === 'created' && e.channel === 'whatsapp') {
      out.push({ ...base, thread: 'owner', direction: 'in', body: 'Invoice photo', hasMedia: true });
    } else if (e.type === 'extracted') {
      out.push({
        ...base,
        id: `${base.id}-x`,
        thread: 'owner',
        direction: 'out',
        body: 'Got it. Please check the details I read from your invoice, then reply YES to confirm.',
      });
    } else if (e.type === 'confirmed' && e.channel === 'whatsapp') {
      out.push({ ...base, thread: 'owner', direction: 'in', body: 'Yes' });
    } else if (e.type === 'chased' && e.channel === 'whatsapp' && body) {
      out.push({ ...base, thread: 'debtor', direction: 'out', body });
    } else if (['replied', 'promised', 'disputed'].includes(e.type) && body) {
      out.push({ ...base, thread: 'debtor', direction: 'in', body, intent: (e.detail.intent as string) ?? null });
    }
  }
  return out;
}

/* --------------------------------------------------------------- live API */

export interface ArrearoApi {
  me(): Promise<Me>;
  updateMe(patch: Partial<Business>): Promise<Me>;
  listInvoices(): Promise<Invoice[]>;
  getInvoice(id: string): Promise<Invoice>;
  createInvoice(input: NewInvoiceInput): Promise<Invoice>;
  patchInvoice(id: string, patch: InvoicePatch): Promise<Invoice>;
  chase(id: string, body?: string): Promise<Invoice>;
  sendLba(id: string, body?: string): Promise<Invoice>;
  events(id: string): Promise<InvoiceEvent[]>;
  debtor(key: string): Promise<Debtor | null>;
}

const enc = encodeURIComponent;

const liveApi: ArrearoApi = {
  async me() {
    return normaliseMe(await request<unknown>('/me'));
  },
  async updateMe(patch) {
    await request<unknown>('/me', { method: 'PUT', body: JSON.stringify(patch) });
    return normaliseMe(await request<unknown>('/me'));
  },
  async listInvoices() {
    return list<Raw>(await request<unknown>('/invoices'), ['invoices', 'items', 'Items']).map(normaliseInvoice);
  },
  async getInvoice(id) {
    const d = await request<Raw>(`/invoices/${enc(id)}`);
    const inv = normaliseInvoice((d.invoice as Raw) ?? d);
    // Populate the agent's composed, compliance-checked chase draft so the detail
    // page can show it for approval (the backend drafts on demand, not on the invoice).
    if (inv.status && ['due', 'chasing', 'escalated'].includes(inv.status)) {
      try {
        const c = await request<Raw>(`/invoices/${enc(id)}/chase`, {
          method: 'POST',
          body: JSON.stringify({ mode: 'draft' }),
        });
        const dr = (c.draft ?? {}) as Record<string, unknown>;
        if (dr.message) {
          const draft: Draft = {
            draftId: 'chase-' + id,
            kind: dr.channel === 'email' ? 'email_chase' : 'whatsapp_chase',
            body: String(dr.message),
            status: 'pending',
            complianceOk: true,
            stage: typeof dr.stage === 'string' ? dr.stage : undefined,
            createdAt: new Date().toISOString(),
          };
          inv.drafts = [draft];
        }
      } catch {
        /* draft is best-effort; the detail page still works without it */
      }
    }
    return inv;
  },
  async createInvoice(input) {
    const d = await request<Raw>('/invoices', { method: 'POST', body: JSON.stringify(input) });
    return normaliseInvoice((d.invoice as Raw) ?? d);
  },
  async patchInvoice(id, patch) {
    const d = await request<Raw>(`/invoices/${enc(id)}`, { method: 'PATCH', body: JSON.stringify(patch) });
    return normaliseInvoice((d.invoice as Raw) ?? d);
  },
  async chase(id, body) {
    // backend contract: {mode:"draft"|"send", message?}; returns {draft,sent,...}, not an invoice
    await request<Raw>(`/invoices/${enc(id)}/chase`, {
      method: 'POST',
      body: JSON.stringify({ mode: 'send', ...(body ? { message: body } : {}) }),
    });
    return liveApi.getInvoice(id);
  },
  async sendLba(id, body) {
    // backend contract: {mode:"draft"|"send", text?}
    await request<Raw>(`/invoices/${enc(id)}/lba`, {
      method: 'POST',
      body: JSON.stringify({ mode: 'send', ...(body ? { text: body } : {}) }),
    });
    return liveApi.getInvoice(id);
  },
  async events(id) {
    const e = list<InvoiceEvent>(await request<unknown>(`/invoices/${enc(id)}/events`), ['events', 'items', 'Items']);
    return e.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  },
  async debtor(key) {
    try {
      const d = await request<Raw>(`/debtors/${enc(key)}`);
      return ((d.debtor as Debtor) ?? (d as unknown as Debtor)) || null;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },
};

export const api: ArrearoApi = DEMO ? (demoApi as ArrearoApi) : liveApi;
