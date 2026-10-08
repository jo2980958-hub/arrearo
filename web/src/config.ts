export const BRAND = 'Arrearo';
export const DOMAIN = 'arrearo.com';
export const TAGLINE =
  "The credit controller that chases your late invoices on WhatsApp and adds the interest you're legally owed.";

const env = import.meta.env;

export const API_URL: string = (env.VITE_API_URL ?? '').replace(/\/+$/, '');
export const DEMO: boolean = env.VITE_DEMO === '1' || env.VITE_DEMO === 'true';
export const COGNITO_REGION: string = env.VITE_COGNITO_REGION ?? 'us-east-1';
export const COGNITO_CLIENT_ID: string = env.VITE_COGNITO_CLIENT_ID ?? '';
export const DEV_TOKEN: string = env.VITE_DEV_TOKEN ?? '';

/**
 * Statutory interest = 8% + Bank of England base rate (Late Payment of
 * Commercial Debts (Interest) Act 1998). The API supplies the authoritative
 * rate per invoice; these are only the display fallbacks.
 */
export const STATUTORY_ADDON_PCT = 8;
export const FALLBACK_BASE_RATE_PCT = 3.75;

export const WHATSAPP_SENDER = '+233 55 906 2312';
