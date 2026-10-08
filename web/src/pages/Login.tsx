import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { DEMO, TAGLINE } from '../config';
import { Button, Field, usePageTitle } from '../components/ui';
import { Icon, LogoMark } from '../components/icons';

export default function Login() {
  usePageTitle('Sign in');
  const auth = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPw, setNewPw] = useState('');
  const [challenge, setChallenge] = useState<{ username: string; session: string } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (auth.signedIn) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (challenge) {
        if (newPw.length < 8) throw new Error('Choose a password of at least 8 characters.');
        await auth.finishNewPassword(challenge.username, newPw, challenge.session);
        nav('/', { replace: true });
      } else {
        const r = await auth.signIn(email.trim(), password);
        if (r.kind === 'new_password') setChallenge({ username: r.username, session: r.challengeSession });
        else nav('/', { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <aside className="auth-art">
        <div className="brand" style={{ padding: 0 }}>
          <LogoMark size={34} />
          Arrearo
        </div>
        <div>
          <h2>
            Late invoices, chased on WhatsApp. <em>Interest added, as the law allows.</em>
          </h2>
          <p>{TAGLINE}</p>
          <div className="auth-chat" aria-hidden="true">
            <div className="msg out">Invoice HP-2078 for £8,640.00 is 41 days overdue. Statutory interest of 11.75% a year (£2.78 a day) brings the total to £8,824.04, with the fixed recovery sum.</div>
            <div className="msg in">Apologies, payment run slipped. We will pay in full this Friday.</div>
            <div className="msg out">Thanks Marcus. I’ve noted Friday and will check back after.</div>
          </div>
        </div>
        <small style={{ color: '#8aa094' }}>Statutory interest under the Late Payment of Commercial Debts (Interest) Act 1998</small>
      </aside>

      <main className="auth-form-wrap" id="main">
        <form className="auth-form" onSubmit={submit} noValidate>
          <div>
            <h1>{challenge ? 'Choose your password' : 'Welcome back'}</h1>
            <p className="muted" style={{ marginTop: 6 }}>
              {challenge
                ? 'This is your first sign-in. Set a password you will remember.'
                : DEMO
                  ? 'You are viewing Arrearo with sample data.'
                  : 'Sign in to see who owes you, and what Arrearo has done about it.'}
            </p>
          </div>

          {error && (
            <div className="alert err" role="alert">
              <Icon name="alert" />
              <span>{error}</span>
            </div>
          )}

          {DEMO ? (
            <>
              <Button variant="primary" className="block" onClick={() => { auth.enterDemo(); nav('/', { replace: true }); }}>
                Open the demo
                <Icon name="arrowRight" />
              </Button>
              <p className="auth-foot">Harlow &amp; Pike Joinery Ltd · sample invoices, nothing is sent.</p>
            </>
          ) : challenge ? (
            <>
              <Field label="New password" htmlFor="newpw" hint="At least 8 characters.">
                <input id="newpw" className="input" type="password" autoComplete="new-password" value={newPw} onChange={(e) => setNewPw(e.target.value)} autoFocus />
              </Field>
              <Button variant="primary" className="block" type="submit" loading={busy}>Set password and continue</Button>
            </>
          ) : (
            <>
              <Field label="Work email" htmlFor="email">
                <input id="email" className="input" type="email" autoComplete="username" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
              </Field>
              <Field label="Password" htmlFor="password">
                <input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </Field>
              <Button variant="primary" className="block" type="submit" loading={busy} disabled={!email || !password}>Sign in</Button>
              <p className="auth-foot">Protected by Amazon Cognito. Arrearo never holds your customers’ money.</p>
            </>
          )}
        </form>
      </main>
    </div>
  );
}
