import { deriveMoney } from './derive';
import { pounds } from '../lib/money';
import { fmtDate } from '../lib/dates';
import type {
  Business,
  Debtor,
  Draft,
  Invoice,
  InvoiceEvent,
  InvoicePatch,
  Me,
  NewInvoiceInput,
  RiskBand,
  ThreadMessage,
} from './types';

/* ------------------------------------------------------------------ helpers */

const DAY = 86_400_000;
const now = () => Date.now();
const dayIso = (daysAgo: number) => new Date(now() - daysAgo * DAY).toISOString().slice(0, 10);
const at = (daysAgo: number, hhmm = '09:00') => {
  const [h, m] = hhmm.split(':').map(Number);
  const d = new Date(now() - daysAgo * DAY);
  d.setHours(h, m, 0, 0);
  return d.toISOString();
};
const minsAgo = (m: number) => new Date(now() - m * 60_000).toISOString();
let uid = 1000;
const id = (p: string) => `${p}_${(uid++).toString(36)}`;

const BANK = { bankName: 'Monzo Business', bankSortCode: '04-00-04', bankAccount: '31827406' };

const business: Business = {
  businessId: 'biz_harlow',
  name: 'Harlow & Pike Joinery Ltd',
  ownerName: 'Tom Pike',
  email: 'tom@harlowpike.co.uk',
  whatsappNumber: '+447700900412',
  sector: 'Construction & trades',
  defaultTermsDays: 30,
  ...BANK,
  createdAt: at(120),
};

/* ------------------------------------------------------------------ debtors */

function debtor(
  key: string,
  name: string,
  companyNumber: string | null,
  band: RiskBand,
  avg: number,
  within30: number,
  mid: number,
  over60: number,
  late: number,
  disputed: number,
): Debtor {
  return {
    debtorKey: key,
    name,
    companyNumber,
    avgDaysToPay: avg,
    pctPaidWithin30: within30,
    pct31to60: mid,
    pct60plus: over60,
    pctPaidLate: late,
    pctInvoicesDisputed: disputed,
    reportPeriodEnd: '2026-03-31',
    riskBand: band,
    source: 'payment-practices',
    fetchedAt: at(2),
  };
}

const debtors: Record<string, Debtor> = {
  '04567123': debtor('04567123', 'Calder & Wynne Facilities Ltd', '04567123', 'high', 71, 21, 33, 46, 64, 9),
  '07712458': debtor('07712458', 'Northgate Developments Ltd', '07712458', 'medium', 47, 38, 41, 21, 38, 4),
  '03398810': debtor('03398810', 'Brightwell Care Group plc', '03398810', 'medium', 41, 44, 38, 18, 33, 3),
  '02145590': debtor('02145590', 'Meridian Print & Packaging Ltd', '02145590', 'low', 29, 74, 21, 5, 17, 1),
  'wessex-borough-council': debtor('wessex-borough-council', 'Wessex Borough Council', null, 'low', 26, 82, 15, 3, 12, 1),
  '05871336': debtor('05871336', 'Halden Logistics Ltd', '05871336', 'medium', 52, 31, 40, 29, 42, 11),
  '09022417': debtor('09022417', 'Kestrel Fabrications Ltd', '09022417', 'medium', 44, 40, 37, 23, 36, 5),
};

/* ----------------------------------------------------------------- drafting */

function chaseText(inv: Invoice, stage: 'first' | 'second' | 'final', contact: string): string {
  const rate = inv.statutoryRatePct ?? 11.75;
  const perDay = pounds((inv.amountPence * rate) / 100 / 365);
  const lead =
    stage === 'first'
      ? `Hi ${contact}, this is Arrearo writing on behalf of ${business.name}.`
      : stage === 'second'
        ? `Hi ${contact}, following up from Arrearo on behalf of ${business.name}.`
        : `${contact}, this is a final reminder from Arrearo on behalf of ${business.name}.`;
  const close =
    stage === 'final'
      ? `If we do not hear from you within 7 days, ${business.name} intends to send a formal Letter Before Action.`
      : `If anything about the invoice is wrong, just reply here and we'll look into it straight away.`;
  return (
    `${lead}\n\nInvoice ${inv.reference} for ${pounds(inv.amountPence)} was due on ${fmtDate(
      inv.agreedDueDate,
    )}${inv.daysLate > 0 ? ` and is now ${inv.daysLate} days overdue` : ' and falls due today'}.\n\n` +
    `Under the Late Payment of Commercial Debts (Interest) Act 1998, statutory interest of ${rate}% a year applies (${perDay} a day). ` +
    `So far that is ${pounds(inv.interestAccruedPence)}, plus a fixed recovery sum of ${pounds(inv.fixedRecoverySumPence)}.\n\n` +
    `Total now due: ${pounds(inv.totalOwedPence)}.\n\n` +
    `Pay by bank transfer to ${business.name}, sort code ${business.bankSortCode}, account ${business.bankAccount}, using reference ${inv.reference}.\n\n${close}`
  );
}

function lbaText(inv: Invoice): string {
  const rate = inv.statutoryRatePct ?? 11.75;
  return (
    `${business.name}\nRe: Letter Before Action. Invoice ${inv.reference}\n\n` +
    `Dear ${inv.debtorName},\n\n` +
    `We write on behalf of ${business.name} about invoice ${inv.reference} dated ${fmtDate(inv.invoiceDate)} for ${pounds(inv.amountPence)}, ` +
    `which fell due on ${fmtDate(inv.agreedDueDate)} and remains unpaid after ${inv.daysLate} days.\n\n` +
    `The sums now due are:\n` +
    `  Invoice principal            ${pounds(inv.amountPence)}\n` +
    `  Statutory interest to date   ${pounds(inv.interestAccruedPence)}   (${rate}% a year, 8% above the Bank of England base rate)\n` +
    `  Fixed recovery sum           ${pounds(inv.fixedRecoverySumPence)}\n` +
    `  Total                        ${pounds(inv.totalOwedPence)}\n\n` +
    `Interest continues to accrue at ${pounds((inv.amountPence * rate) / 100 / 365)} a day under the Late Payment of Commercial Debts (Interest) Act 1998.\n\n` +
    `Unless the total is paid in cleared funds within 14 days of the date of this letter, ${business.name} may issue a claim in the County Court without further notice and will seek its costs and further interest. ` +
    `If you dispute any part of this debt, please tell us in writing within the same period, with your reasons and any supporting documents.\n\n` +
    `Payment details: ${business.bankName}, sort code ${business.bankSortCode}, account ${business.bankAccount}, reference ${inv.reference}.\n\n` +
    `Yours sincerely,\n${business.ownerName}\n${business.name}`
  );
}

/* ------------------------------------------------------------------- store */

interface Rec {
  inv: Invoice;
  events: InvoiceEvent[];
  messages: ThreadMessage[];
  drafts: Draft[];
}

const store: Record<string, Rec> = {};

function ev(
  invoiceId: string,
  type: InvoiceEvent['type'],
  channel: InvoiceEvent['channel'],
  actor: InvoiceEvent['actor'],
  createdAt: string,
  detail: Record<string, unknown> = {},
): InvoiceEvent {
  return { invoiceId, type, channel, actor, detail, createdAt };
}

function msg(
  thread: ThreadMessage['thread'],
  direction: ThreadMessage['direction'],
  at_: string,
  body: string,
  extra: Partial<ThreadMessage> = {},
): ThreadMessage {
  return { id: id('m'), thread, direction, at: at_, body, ...extra };
}

type Seed = {
  key: string;
  debtorName: string;
  company?: string | null;
  type?: Invoice['debtorType'];
  contact: string;
  email?: string;
  whatsapp?: string | null;
  amount: number;
  invoicedAgo: number;
  dueAgo: number; // days since agreed due date (negative = in the future)
  ref: string;
  description: string;
  status: Invoice['status'];
  channel?: 'whatsapp' | 'dashboard';
  paidAgo?: number;
  debtorKey?: string;
  confidence?: number;
  risk?: Invoice['riskBand'];
};

function build(s: Seed): Rec {
  const invoiceId = `inv_${s.key}`;
  const base = {
    amountPence: s.amount,
    invoiceDate: dayIso(s.invoicedAgo),
    deliveryDate: dayIso(s.invoicedAgo),
    agreedDueDate: dayIso(s.dueAgo),
    debtorType: s.type ?? 'company',
    paidAt: s.paidAgo != null ? dayIso(s.paidAgo) : null,
  };
  const money = deriveMoney(base);
  const inv: Invoice = {
    invoiceId,
    businessId: business.businessId,
    debtorName: s.debtorName,
    debtorCompanyNumber: s.company ?? null,
    debtorType: base.debtorType,
    debtorEmail: s.email ?? `accounts@${s.debtorName.toLowerCase().replace(/[^a-z]+/g, '')}.co.uk`,
    debtorWhatsapp: s.whatsapp === undefined ? '+447700900' + (100 + (uid % 800)) : s.whatsapp,
    amountPence: s.amount,
    currency: 'GBP',
    invoiceDate: base.invoiceDate,
    deliveryDate: base.deliveryDate,
    agreedDueDate: base.agreedDueDate,
    reference: s.ref,
    description: s.description,
    status: s.status,
    sourceChannel: s.channel ?? 'whatsapp',
    extractionConfidence: s.confidence ?? 0.97,
    createdAt: at(s.invoicedAgo - 1 > 0 ? s.invoicedAgo - 1 : 0, '10:12'),
    confirmedAt: s.status === 'extracted' ? null : at(s.invoicedAgo - 1 > 0 ? s.invoicedAgo - 1 : 0, '10:15'),
    paidAt: s.paidAgo != null ? at(s.paidAgo, '14:20') : null,
    ...money,
    dailyInterestPence: (s.amount * money.statutoryRatePct) / 100 / 365,
    debtorKey: s.debtorKey ?? s.company ?? undefined,
    riskBand: s.risk,
  };
  return { inv, events: [], messages: [], drafts: [] };
}

function add(rec: Rec) {
  store[rec.inv.invoiceId] = rec;
  return rec;
}

function opening(rec: Rec, whenAgo: number, hhmm = '10:12') {
  const { inv } = rec;
  const t = at(whenAgo, hhmm);
  const t2 = at(whenAgo, hhmm.replace(/:\d\d$/, (m) => `:${String(Number(m.slice(1)) + 1).padStart(2, '0')}`));
  rec.messages.push(
    msg('owner', 'in', t, 'Invoice photo', { hasMedia: true }),
    msg(
      'owner',
      'out',
      t2,
      `Got it. I read this as:\n\n${inv.debtorName}\nInvoice ${inv.reference}\n${pounds(inv.amountPence)}, due ${fmtDate(inv.agreedDueDate)}\n\nReply YES to confirm and I'll start tracking it.`,
    ),
    msg('owner', 'in', at(whenAgo, hhmm.replace(/:\d\d$/, (m) => `:${String(Number(m.slice(1)) + 2).padStart(2, '0')}`)), 'Yes'),
  );
  rec.events.push(
    ev(inv.invoiceId, 'created', 'whatsapp', 'owner', t, { source: 'whatsapp' }),
    ev(inv.invoiceId, 'extracted', 'system', 'agent', t, {
      confidence: inv.extractionConfidence,
      amountPence: inv.amountPence,
    }),
    ev(inv.invoiceId, 'confirmed', 'whatsapp', 'owner', at(whenAgo, hhmm.replace(/:\d\d$/, (m) => `:${String(Number(m.slice(1)) + 2).padStart(2, '0')}`)), {}),
  );
}

function scored(rec: Rec, whenAgo: number) {
  const d = rec.inv.debtorKey ? debtors[rec.inv.debtorKey] : undefined;
  rec.events.push(
    ev(
      rec.inv.invoiceId,
      'debtor_scored',
      'system',
      'agent',
      at(whenAgo, '10:16'),
      d
        ? { riskBand: d.riskBand, avgDaysToPay: d.avgDaysToPay, source: 'payment-practices' }
        : { riskBand: 'unknown', source: 'unknown' },
    ),
  );
}

function chased(rec: Rec, whenAgo: number, stage: 'first' | 'second' | 'final', contact: string) {
  const { inv } = rec;
  const body = chaseText({ ...inv, daysLate: Math.max(0, inv.daysLate - whenAgo) }, stage, contact);
  rec.events.push(
    ev(inv.invoiceId, 'chased', 'whatsapp', 'agent', at(whenAgo, '09:30'), { stage, body }),
  );
  rec.messages.push(msg('debtor', 'out', at(whenAgo, '09:30'), body));
}

function reply(rec: Rec, whenAgo: number, hhmm: string, body: string, intent: string, evType: InvoiceEvent['type'] = 'replied', extra: Record<string, unknown> = {}) {
  rec.events.push(ev(rec.inv.invoiceId, evType, 'whatsapp', 'debtor', at(whenAgo, hhmm), { body, intent, ...extra }));
  rec.messages.push(msg('debtor', 'in', at(whenAgo, hhmm), body, { intent }));
}

function seedAll() {
  // 1. Aged: Letter Before Action drafted for approval
  {
    const r = add(
      build({
        key: 'calder',
        debtorName: 'Calder & Wynne Facilities Ltd',
        company: '04567123',
        contact: 'Priya',
        amount: 1_275_000,
        invoicedAgo: 126,
        dueAgo: 96,
        ref: 'HP-2041',
        description: 'Bespoke oak fit-out, reception and 4 meeting rooms (Leeds)',
        status: 'lba',
        risk: 'high',
      }),
    );
    opening(r, 125);
    scored(r, 125);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(96, '00:05'), {}));
    chased(r, 95, 'first', 'Priya');
    reply(r, 94, '11:40', "Hi, can you resend the invoice? Didn't get it", 'question');
    chased(r, 80, 'second', 'Priya');
    reply(r, 79, '16:02', "Will sort this next week, finance are chasing the PO", 'promise_to_pay', 'promised', { promisedDate: dayIso(72) });
    chased(r, 40, 'final', 'Priya');
    r.events.push(
      ev(r.inv.invoiceId, 'lba_drafted', 'system', 'agent', at(0, '07:45'), {
        reason: 'No payment 24 days after the promised date',
      }),
    );
    r.drafts.push({
      draftId: id('d'),
      kind: 'lba',
      subject: `Letter Before Action: Invoice ${r.inv.reference}`,
      body: lbaText(r.inv),
      status: 'pending',
      complianceOk: true,
      stage: 'lba',
      createdAt: at(0, '07:45'),
    });
  }
  // 2. Promised to pay
  {
    const r = add(
      build({
        key: 'northgate',
        debtorName: 'Northgate Developments Ltd',
        company: '07712458',
        contact: 'Marcus',
        amount: 864_000,
        invoicedAgo: 71,
        dueAgo: 41,
        ref: 'HP-2078',
        description: 'Staircases and balustrades, plots 12 to 19',
        status: 'promised',
        risk: 'medium',
      }),
    );
    opening(r, 70);
    scored(r, 70);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(41, '00:05'), {}));
    chased(r, 40, 'first', 'Marcus');
    reply(r, 38, '14:11', 'Apologies, payment run slipped. We will pay in full this Friday.', 'promise_to_pay', 'promised', { promisedDate: dayIso(-2) });
    r.events.push(ev(r.inv.invoiceId, 'digest', 'whatsapp', 'agent', at(0, '07:30'), { note: 'Included in morning digest: promise lands Friday' }));
  }
  // 3. Chasing: second chase draft ready
  {
    const r = add(
      build({
        key: 'brightwell',
        debtorName: 'Brightwell Care Group plc',
        company: '03398810',
        contact: 'Helen',
        amount: 420_000,
        invoicedAgo: 47,
        dueAgo: 17,
        ref: 'HP-2096',
        description: 'Reception desk and wall panelling, Brightwell Harrogate',
        status: 'chasing',
        risk: 'medium',
      }),
    );
    opening(r, 46);
    scored(r, 46);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(17, '00:05'), {}));
    chased(r, 16, 'first', 'Helen');
    reply(r, 15, '10:20', 'Thanks, passing to our AP team now.', 'other');
    r.drafts.push({
      draftId: id('d'),
      kind: 'whatsapp_chase',
      body: chaseText(r.inv, 'second', 'Helen'),
      status: 'pending',
      complianceOk: true,
      stage: 'second_chase',
      createdAt: at(0, '07:46'),
    });
  }
  // 4. Due today -> first chase
  {
    const r = add(
      build({
        key: 'meridian',
        debtorName: 'Meridian Print & Packaging Ltd',
        company: '02145590',
        contact: 'Dan',
        amount: 132_000,
        invoicedAgo: 30,
        dueAgo: 0,
        ref: 'HP-2112',
        description: 'Packing-bench repairs and replacement shelving',
        status: 'due',
        risk: 'low',
      }),
    );
    opening(r, 29);
    scored(r, 29);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(0, '00:05'), {}));
    r.drafts.push({
      draftId: id('d'),
      kind: 'whatsapp_chase',
      body:
        `Hi Dan, this is Arrearo writing on behalf of ${business.name}.\n\n` +
        `Invoice ${r.inv.reference} for ${pounds(r.inv.amountPence)} falls due today. A quick nudge so it doesn't slip by.\n\n` +
        `Pay by bank transfer to ${business.name}, sort code ${business.bankSortCode}, account ${business.bankAccount}, using reference ${r.inv.reference}.\n\n` +
        `If it has already gone out, thank you, and please ignore this message.`,
      status: 'pending',
      complianceOk: true,
      stage: 'reminder',
      createdAt: at(0, '07:46'),
    });
  }
  // 5. Fresh extraction from WhatsApp, awaiting confirmation
  {
    const r = add(
      build({
        key: 'fenwick',
        debtorName: 'Fenwick Dental Practice',
        company: null,
        contact: 'Dr Fenwick',
        amount: 64_000,
        invoicedAgo: 9,
        dueAgo: -21,
        ref: 'HP-2131',
        description: 'Surgery door set and skirting',
        status: 'extracted',
        confidence: 0.86,
        risk: 'unknown',
        debtorKey: undefined,
      }),
    );
    const t = minsAgo(22);
    r.messages.push(
      msg('owner', 'in', t, 'Invoice photo', { hasMedia: true }),
      msg(
        'owner',
        'out',
        minsAgo(21),
        `Got it. I read this as:\n\nFenwick Dental Practice\nInvoice HP-2131\n${pounds(64_000)}, due ${fmtDate(r.inv.agreedDueDate)}\n\nThe due date is a little blurry, so please check it. Reply YES to confirm, or send a correction.`,
      ),
    );
    r.events.push(
      ev(r.inv.invoiceId, 'created', 'whatsapp', 'owner', t, { source: 'whatsapp' }),
      ev(r.inv.invoiceId, 'extracted', 'system', 'agent', minsAgo(21), { confidence: 0.86, amountPence: 64_000 }),
    );
    r.inv.createdAt = t;
  }
  // 6. Public authority, 12 days late
  {
    const r = add(
      build({
        key: 'wessex',
        debtorName: 'Wessex Borough Council',
        company: null,
        type: 'public_authority',
        contact: 'Accounts Payable',
        amount: 590_000,
        invoicedAgo: 42,
        dueAgo: 12,
        ref: 'HP-2102',
        description: 'Library refurbishment, joinery package B',
        status: 'chasing',
        risk: 'low',
        debtorKey: 'wessex-borough-council',
      }),
    );
    opening(r, 41);
    scored(r, 41);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(12, '00:05'), {}));
    chased(r, 11, 'first', 'Accounts Payable');
  }
  // 7. Disputed
  {
    const r = add(
      build({
        key: 'halden',
        debtorName: 'Halden Logistics Ltd',
        company: '05871336',
        contact: 'Gareth',
        amount: 318_000,
        invoicedAgo: 59,
        dueAgo: 29,
        ref: 'HP-2085',
        description: 'Loading-bay racking and timber cladding',
        status: 'disputed',
        risk: 'medium',
      }),
    );
    opening(r, 58);
    scored(r, 58);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(29, '00:05'), {}));
    chased(r, 28, 'first', 'Gareth');
    reply(r, 27, '09:48', 'Two of the cladding panels arrived cracked. We are not paying the full amount until that is sorted.', 'dispute', 'disputed', { reason: 'Damaged goods on delivery' });
    r.events.push(
      ev(r.inv.invoiceId, 'compliance_block', 'system', 'system', at(20, '08:00'), {
        note: 'Automatic chasing paused while the invoice is disputed',
      }),
    );
  }
  // 8. Sole trader, small
  {
    const r = add(
      build({
        key: 'hurst',
        debtorName: 'Dale Hurst (t/a Hurst Landscapes)',
        company: null,
        type: 'sole_trader',
        contact: 'Dale',
        amount: 96_000,
        invoicedAgo: 63,
        dueAgo: 33,
        ref: 'HP-2074',
        description: 'Garden room frame, labour only',
        status: 'chasing',
        risk: 'unknown',
        debtorKey: undefined,
      }),
    );
    opening(r, 62);
    scored(r, 62);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(33, '00:05'), {}));
    chased(r, 32, 'first', 'Dale');
    chased(r, 24, 'second', 'Dale');
  }
  // 9. Not yet due
  {
    const r = add(
      build({
        key: 'oakmere',
        debtorName: 'Oakmere Interiors Ltd',
        company: '08840291',
        contact: 'Sophie',
        amount: 735_000,
        invoicedAgo: 18,
        dueAgo: -12,
        ref: 'HP-2124',
        description: 'Showroom joinery, phase one',
        status: 'confirmed',
        risk: 'unknown',
        debtorKey: undefined,
      }),
    );
    opening(r, 17);
    scored(r, 17);
  }
  // 10-12. Paid
  {
    const r = add(
      build({
        key: 'pemberton',
        debtorName: 'Pemberton Events Ltd',
        company: '10233018',
        contact: 'Isla',
        amount: 248_000,
        invoicedAgo: 55,
        dueAgo: 25,
        ref: 'HP-2069',
        description: 'Exhibition stand build',
        status: 'paid',
        paidAgo: 3,
        risk: 'unknown',
        debtorKey: undefined,
      }),
    );
    opening(r, 54);
    scored(r, 54);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(25, '00:05'), {}));
    chased(r, 24, 'first', 'Isla');
    reply(r, 23, '12:30', 'So sorry, missed this. Paying today.', 'promise_to_pay', 'promised', { promisedDate: dayIso(23) });
    chased(r, 10, 'second', 'Isla');
    reply(r, 9, '15:10', 'Paid, can you check?', 'paid');
    r.events.push(
      ev(r.inv.invoiceId, 'paid', 'system', 'owner', at(3, '14:20'), {
        amountPence: r.inv.totalOwedPence,
        note: 'Marked paid by owner',
      }),
    );
  }
  {
    const r = add(
      build({
        key: 'sterling',
        debtorName: 'Sterling & Rowe Architects LLP',
        company: 'OC391204',
        contact: 'James',
        amount: 490_000,
        invoicedAgo: 70,
        dueAgo: 40,
        ref: 'HP-2058',
        description: 'Site-hut joinery and hoarding',
        status: 'paid',
        paidAgo: 19,
        risk: 'unknown',
        debtorKey: undefined,
      }),
    );
    opening(r, 69);
    scored(r, 69);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(40, '00:05'), {}));
    chased(r, 39, 'first', 'James');
    r.events.push(
      ev(r.inv.invoiceId, 'paid', 'system', 'owner', at(19, '11:05'), { amountPence: r.inv.totalOwedPence }),
    );
  }
  {
    const r = add(
      build({
        key: 'kestrel',
        debtorName: 'Kestrel Fabrications Ltd',
        company: '09022417',
        contact: 'Ruth',
        amount: 610_000,
        invoicedAgo: 100,
        dueAgo: 70,
        ref: 'HP-2033',
        description: 'Workshop mezzanine, timber and fixings',
        status: 'paid',
        paidAgo: 34,
        risk: 'medium',
      }),
    );
    opening(r, 99);
    scored(r, 99);
    r.events.push(ev(r.inv.invoiceId, 'due', 'system', 'system', at(70, '00:05'), {}));
    chased(r, 69, 'first', 'Ruth');
    chased(r, 55, 'second', 'Ruth');
    reply(r, 52, '10:02', 'Finance has approved it, payment on the 25th.', 'promise_to_pay', 'promised', { promisedDate: dayIso(44) });
    r.events.push(
      ev(r.inv.invoiceId, 'paid', 'system', 'owner', at(34, '16:42'), { amountPence: r.inv.totalOwedPence }),
    );
  }

  for (const rec of Object.values(store)) {
    rec.events.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    rec.events.forEach((e, i) => (e.seq = i));
    rec.messages.sort((a, b) => a.at.localeCompare(b.at));
  }
}
seedAll();

/* --------------------------------------------------------------- operations */

const sleep = (ms = 280) => new Promise((r) => setTimeout(r, ms));

/** Re-derive the money fields so days late and interest are always current. */
function fresh(rec: Rec): Invoice {
  const { inv } = rec;
  const money = deriveMoney({
    amountPence: inv.amountPence,
    invoiceDate: inv.invoiceDate,
    deliveryDate: inv.deliveryDate,
    agreedDueDate: inv.agreedDueDate,
    debtorType: inv.debtorType,
    paidAt: inv.paidAt ? inv.paidAt.slice(0, 10) : null,
  });
  const out: Invoice = {
    ...inv,
    ...money,
    dailyInterestPence: (inv.amountPence * money.statutoryRatePct) / 100 / 365,
  };
  out.debtor = out.debtorKey ? (debtors[out.debtorKey] ?? null) : null;
  out.drafts = rec.drafts.map((d) => ({ ...d }));
  out.messages = rec.messages.map((m) => ({ ...m }));
  return out;
}

export const demoApi = {
  async me(): Promise<Me> {
    await sleep(120);
    return { business: { ...business }, email: business.email, plan: 'Growth' };
  },
  async updateMe(patch: Partial<Business>): Promise<Me> {
    await sleep();
    Object.assign(business, patch);
    return { business: { ...business }, email: business.email, plan: 'Growth' };
  },
  async listInvoices(): Promise<Invoice[]> {
    await sleep(160);
    return Object.values(store).map(fresh);
  },
  async getInvoice(invoiceId: string): Promise<Invoice> {
    await sleep(120);
    const rec = store[invoiceId];
    if (!rec) throw new Error('Invoice not found');
    return fresh(rec);
  },
  async createInvoice(input: NewInvoiceInput): Promise<Invoice> {
    await sleep();
    const invoiceId = id('inv');
    const base = {
      amountPence: input.amountPence,
      invoiceDate: input.invoiceDate,
      deliveryDate: input.deliveryDate ?? null,
      agreedDueDate: input.agreedDueDate ?? null,
      debtorType: input.debtorType,
      paidAt: null,
    };
    const money = deriveMoney(base);
    const created = new Date().toISOString();
    const inv: Invoice = {
      invoiceId,
      businessId: business.businessId,
      debtorName: input.debtorName,
      debtorCompanyNumber: input.debtorCompanyNumber ?? null,
      debtorType: input.debtorType,
      debtorEmail: input.debtorEmail ?? null,
      debtorWhatsapp: input.debtorWhatsapp ?? null,
      amountPence: input.amountPence,
      currency: 'GBP',
      invoiceDate: input.invoiceDate,
      deliveryDate: input.deliveryDate ?? null,
      agreedDueDate: input.agreedDueDate ?? null,
      reference: input.reference,
      description: input.description,
      status: 'confirmed',
      sourceChannel: 'dashboard',
      extractionConfidence: null,
      createdAt: created,
      confirmedAt: created,
      paidAt: null,
      debtorKey: input.debtorCompanyNumber ?? undefined,
      ...money,
    };
    const rec: Rec = {
      inv,
      events: [
        ev(invoiceId, 'created', 'system', 'owner', created, { source: 'dashboard' }),
        ev(invoiceId, 'confirmed', 'system', 'owner', created, {}),
      ],
      messages: [],
      drafts: [],
    };
    rec.events.forEach((e, i) => (e.seq = i));
    store[invoiceId] = rec;
    return fresh(rec);
  },
  async patchInvoice(invoiceId: string, patch: InvoicePatch): Promise<Invoice> {
    await sleep();
    const rec = store[invoiceId];
    if (!rec) throw new Error('Invoice not found');
    const prev = rec.inv.status;
    Object.assign(rec.inv, patch);
    const t = new Date().toISOString();
    if (patch.status && patch.status !== prev) {
      if (patch.status === 'confirmed') {
        rec.inv.confirmedAt = t;
        rec.events.push(ev(invoiceId, 'confirmed', 'system', 'owner', t));
      }
      if (patch.status === 'paid') {
        rec.inv.paidAt = t;
        rec.drafts = [];
        const f = fresh(rec);
        rec.events.push(ev(invoiceId, 'paid', 'system', 'owner', t, { amountPence: f.totalOwedPence }));
      }
      if (patch.status === 'disputed') {
        rec.drafts = [];
        rec.events.push(ev(invoiceId, 'disputed', 'system', 'owner', t, { reason: 'Marked as disputed by owner' }));
      }
    }
    rec.events.forEach((e, i) => (e.seq = i));
    return fresh(rec);
  },
  async chase(invoiceId: string, body?: string): Promise<Invoice> {
    await sleep(700);
    const rec = store[invoiceId];
    if (!rec) throw new Error('Invoice not found');
    const t = new Date().toISOString();
    const pending = rec.drafts.find((d) => d.kind !== 'lba' && d.status === 'pending');
    const text = body ?? pending?.body ?? chaseText(fresh(rec), 'first', 'there');
    rec.drafts = rec.drafts.filter((d) => d !== pending);
    rec.events.push(ev(invoiceId, 'chased', 'whatsapp', 'owner', t, { body: text, approvedByOwner: true }));
    rec.messages.push(msg('debtor', 'out', t, text));
    if (rec.inv.status === 'due' || rec.inv.status === 'confirmed') rec.inv.status = 'chasing';
    rec.events.forEach((e, i) => (e.seq = i));
    return fresh(rec);
  },
  async sendLba(invoiceId: string, body?: string): Promise<Invoice> {
    await sleep(900);
    const rec = store[invoiceId];
    if (!rec) throw new Error('Invoice not found');
    const t = new Date().toISOString();
    const pending = rec.drafts.find((d) => d.kind === 'lba');
    rec.drafts = rec.drafts.filter((d) => d !== pending);
    rec.events.push(
      ev(invoiceId, 'lba_sent', 'email', 'owner', t, { body: body ?? pending?.body ?? lbaText(fresh(rec)), to: rec.inv.debtorEmail }),
    );
    rec.inv.status = 'lba';
    rec.events.forEach((e, i) => (e.seq = i));
    return fresh(rec);
  },
  async events(invoiceId: string): Promise<InvoiceEvent[]> {
    await sleep(100);
    const rec = store[invoiceId];
    if (!rec) throw new Error('Invoice not found');
    return rec.events.map((e) => ({ ...e }));
  },
  async debtor(key: string): Promise<Debtor | null> {
    await sleep(100);
    return debtors[key] ?? null;
  },
};
