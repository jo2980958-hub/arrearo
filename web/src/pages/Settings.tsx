import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useMe, useUpdateMe } from '../api/hooks';
import type { Business } from '../api/types';
import { BankSection, BusinessSection, TermsSection, toDraft, validate, type BizDraft, type Errors } from '../components/BusinessFields';
import { Button, useToast, usePageTitle } from '../components/ui';
import { FALLBACK_BASE_RATE_PCT, STATUTORY_ADDON_PCT, WHATSAPP_SENDER } from '../config';

export default function Settings() {
  usePageTitle('Settings');
  const { business } = useOutletContext<{ business: Business }>();
  const me = useMe();
  const save = useUpdateMe();
  const toast = useToast();
  const [draft, setDraft] = useState<BizDraft>(() => toDraft(business));
  const [errors, setErrors] = useState<Errors>({});
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(business));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const err = validate(draft, ['business', 'terms', 'bank']);
    setErrors(err);
    if (Object.keys(err).length) {
      toast('Fix the highlighted fields first.', 'err');
      return;
    }
    try {
      await save.mutateAsync(draft);
      toast('Settings saved.');
    } catch (x) {
      toast(x instanceof Error ? x.message : 'Could not save', 'err');
    }
  }
  const common = { value: draft, onChange: setDraft, errors, prefix: 'set' };

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="sub">Your business, payment terms and bank details. Arrearo uses these in every message it writes for you.</p>
        </div>
      </div>

      <form className="stack" onSubmit={submit} noValidate>
        <section className="card card-pad stack" aria-labelledby="s1"><h2 className="card-title" id="s1">Business</h2><BusinessSection {...common} /></section>
        <section className="card card-pad stack" aria-labelledby="s2"><h2 className="card-title" id="s2">Payment terms</h2><TermsSection {...common} /></section>
        <section className="card card-pad stack" aria-labelledby="s3"><h2 className="card-title" id="s3">Bank details for invoices and letters</h2><BankSection {...common} /></section>

        <section className="card card-pad" aria-labelledby="s4">
          <h2 className="card-title" id="s4">Plan and statutory rate</h2>
          <dl className="kv">
            <dt>Plan</dt><dd>{me.data?.plan ?? 'Growth'}</dd>
            <dt>Statutory interest rate</dt><dd className="num">{STATUTORY_ADDON_PCT + FALLBACK_BASE_RATE_PCT}% ({STATUTORY_ADDON_PCT}% + {FALLBACK_BASE_RATE_PCT}% base)</dd>
            <dt>WhatsApp sender</dt><dd className="mono">{WHATSAPP_SENDER}</dd>
          </dl>
        </section>

        <div className="actions">
          <Button variant="primary" type="submit" loading={save.isPending} disabled={!dirty}>Save changes</Button>
          {dirty && <Button variant="ghost" onClick={() => { setDraft(toDraft(business)); setErrors({}); }}>Discard</Button>}
        </div>
      </form>
    </div>
  );
}
