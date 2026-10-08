export type InvoiceStatus =
  | 'extracted'
  | 'confirmed'
  | 'due'
  | 'chasing'
  | 'promised'
  | 'disputed'
  | 'paid'
  | 'lba'
  | 'escalated';

export type DebtorType = 'company' | 'sole_trader' | 'individual' | 'public_authority';
export type RiskBand = 'low' | 'medium' | 'high';

export interface Business {
  businessId: string;
  name: string;
  ownerName: string;
  email: string;
  whatsappNumber: string;
  sector?: string;
  defaultTermsDays: number;
  bankName?: string;
  bankSortCode?: string;
  bankAccount?: string;
  createdAt?: string;
}

export interface Me {
  business: Business;
  email: string;
  plan?: string;
}

export interface Invoice {
  invoiceId: string;
  businessId: string;
  debtorName: string;
  debtorCompanyNumber?: string | null;
  debtorType: DebtorType;
  debtorEmail?: string | null;
  debtorWhatsapp?: string | null;
  amountPence: number;
  currency: string;
  invoiceDate: string;
  deliveryDate?: string | null;
  agreedDueDate?: string | null;
  reference: string;
  description?: string;
  status: InvoiceStatus;
  sourceChannel: 'whatsapp' | 'dashboard';
  extractionConfidence?: number | null;
  legallyLateDate?: string | null;
  createdAt: string;
  confirmedAt?: string | null;
  paidAt?: string | null;
  // derived on read by the API
  daysLate: number;
  interestAccruedPence: number;
  fixedRecoverySumPence: number;
  totalOwedPence: number;
  // optional enrichments (used when the API provides them)
  statutoryRatePct?: number;
  baseRatePct?: number;
  dailyInterestPence?: number;
  debtorKey?: string;
  riskBand?: RiskBand | 'unknown';
  debtor?: Debtor | null;
  drafts?: Draft[];
  messages?: ThreadMessage[];
}

export interface Debtor {
  debtorKey: string;
  name: string;
  companyNumber?: string | null;
  avgDaysToPay?: number | null;
  pctPaidWithin30?: number | null;
  pct31to60?: number | null;
  pct60plus?: number | null;
  pctPaidLate?: number | null;
  pctInvoicesDisputed?: number | null;
  reportPeriodEnd?: string | null;
  riskBand: RiskBand | 'unknown';
  source: 'payment-practices' | 'unknown';
  fetchedAt?: string;
}

export type EventType =
  | 'created'
  | 'extracted'
  | 'confirmed'
  | 'debtor_scored'
  | 'due'
  | 'chased'
  | 'replied'
  | 'promised'
  | 'disputed'
  | 'lba_drafted'
  | 'lba_sent'
  | 'paid'
  | 'digest'
  | 'compliance_block';

export interface InvoiceEvent {
  invoiceId: string;
  type: EventType;
  channel: 'whatsapp' | 'email' | 'system';
  actor: 'agent' | 'owner' | 'debtor' | 'system';
  detail: Record<string, unknown>;
  createdAt: string;
  seq?: number;
}

export type DraftKind = 'whatsapp_chase' | 'email_chase' | 'lba';

export interface Draft {
  draftId: string;
  kind: DraftKind;
  subject?: string;
  body: string;
  status: 'pending' | 'sent' | 'blocked';
  complianceOk: boolean;
  stage?: string;
  createdAt: string;
}

export interface ThreadMessage {
  id: string;
  direction: 'in' | 'out';
  body: string;
  mediaUrl?: string | null;
  hasMedia?: boolean;
  intent?: string | null;
  at: string;
  party: 'owner' | 'debtor' | 'agent';
}

export interface NewInvoiceInput {
  debtorName: string;
  debtorType: DebtorType;
  debtorCompanyNumber?: string;
  debtorEmail?: string;
  debtorWhatsapp?: string;
  amountPence: number;
  invoiceDate: string;
  deliveryDate?: string;
  agreedDueDate?: string;
  reference: string;
  description?: string;
}

export type InvoicePatch = Partial<
  Pick<
    Invoice,
    | 'status'
    | 'debtorName'
    | 'amountPence'
    | 'invoiceDate'
    | 'agreedDueDate'
    | 'reference'
    | 'debtorEmail'
    | 'debtorWhatsapp'
  >
>;
