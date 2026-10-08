import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useMe, useUpdateMe } from '../api/hooks';
import { BankSection, BusinessSection, TermsSection, toDraft, validate, type BizDraft, type Errors } from '../components/BusinessFields';
import { Icon, LogoMark } from '../components/icons';
import { Button, Skeleton, useToast, usePageTitle } from '../components/ui';

const STEPS = [
  { title: 'Tell us about your business', lede: 'Arrearo writes to your customers in your name. It starts with who you are.' },
  { title: 'How long do you give customers to pay?', lede: 'Arrearo needs to know when an invoice is due before it can tell you when it’s late.' },
  { title: 'Where should customers pay you?', lede: 'These details go on chase messages and any Letter Before Action. Payments go straight to your account. Arrearo never holds your customers’ money.' },
  { title: 'Ready to chase', lede: 'Check the details, then send your first invoice photo to Arrearo on WhatsApp.' },
] as const;

export default function Onboarding() {
  usePageTitle('Set up');
  const auth = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const me = useMe();
  const save = useUpdateMe();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<BizDraft | null>(null);
  const [errors, setErrors] = useState<Errors>({});

  if (!auth.signedIn) return <Navigate to="/login" replace />;
  if (me.isLoading || !me.data) {
    return <div className="onb"><Skeleton h={40} w="70%" /><div style={{ height: 20 }} /><Skeleton h={220} /></div>;
  }
  const d = draft ?? toDraft({ ...me.data.business, email: me.data.business.email || me.data.email });

  function next() {
    const parts = (['business', 'terms', 'bank'] as const)[step];
    if (parts) {
      const e = validate(d, [parts]);
      setErrors(e);
      if (Object.keys(e).length) return;
    }
    setStep((s) => s + 1);
  }

  async function finish() {
    try {
      await save.mutateAsync(d);
      try { sessionStorage.removeItem('arrearo.onboarding-skipped'); } catch { /* ignore */ }
      toast('You’re all set. Arrearo is ready to chase.');
      nav('/', { replace: true });
    } catch (err) {
      toast(err instanceof Error ? err.message : 'Could not save your details', 'err');
    }
  }

  function skip() {
    try { sessionStorage.setItem('arrearo.onboarding-skipped', '1'); } catch { /* ignore */ }
    nav('/', { replace: true });
  }

  const s = STEPS[step];
  const common = { value: d, onChange: setDraft as (v: BizDraft) => void, errors, prefix: 'onb' };

  return (
    <div className="onb">
      <div className="onb-top">
        <div className="brand" style={{ padding: 0, color: 'var(--ink)' }}>
          <LogoMark size={30} onLight />
          Arrearo
        </div>
        <Button variant="ghost" size="sm" onClick={skip}>Skip for now</Button>
      </div>

      <div className="progress" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={step + 1} aria-label={`Step ${step + 1} of ${STEPS.length}`}>
        {STEPS.map((_, i) => <i key={i} className={i <= step ? 'on' : ''} />)}
      </div>

      <h1>{s.title}</h1>
      <p className="lede">{s.lede}</p>

      <div className="card card-pad">
        {step === 0 && <BusinessSection {...common} />}
        {step === 1 && <TermsSection {...common} />}
        {step === 2 && <BankSection {...common} />}
        {step === 3 && (
          <dl className="summary">
            <div><dt>Business</dt><dd>{d.name}</dd></div>
            <div><dt>Owner</dt><dd>{d.ownerName}</dd></div>
            <div><dt>WhatsApp</dt><dd className="mono">{d.whatsappNumber}</dd></div>
            <div><dt>Payment terms</dt><dd>{d.defaultTermsDays} days</dd></div>
            <div><dt>Pay to</dt><dd>{d.bankName}</dd></div>
            <div><dt>Sort code · account</dt><dd className="mono">{d.bankSortCode} · {d.bankAccount}</dd></div>
          </dl>
        )}
      </div>

      <div className="onb-nav">
        <Button variant="ghost" disabled={step === 0} onClick={() => setStep((x) => x - 1)} icon="arrowLeft">Back</Button>
        {step < STEPS.length - 1 ? (
          <Button variant="primary" onClick={next}>Continue <Icon name="arrowRight" /></Button>
        ) : (
          <Button variant="primary" loading={save.isPending} onClick={finish} icon="check">Finish setup</Button>
        )}
      </div>
    </div>
  );
}
