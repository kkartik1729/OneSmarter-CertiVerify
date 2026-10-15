import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import Field from '../components/Field';
import { useAuth } from '../context/AuthContext';
import { Brand, ThemeToggle, toast } from '../lib/ui';
import { homeFor } from '../lib/paths';
import { ApiError, errMsg } from '../services';

type F = 'name' | 'email' | 'pw' | 'pc';

/** Backend field names -> the form field that shows the message. */
const FIELD_MAP: Record<string, F> = {
  username: 'email', email: 'email', first_name: 'name', last_name: 'name', password: 'pw', password_confirm: 'pc',
};

/**
 * Registration page -> POST /accounts/register/.
 * The backend returns NO tokens, so after success the user is sent to the login page.
 * The form has no separate username box: the email is sent as both `username` and `email`.
 */
export default function Register() {
  const { user, register } = useAuth();
  const go = useNavigate();
  const [v, setV] = useState<Record<F, string>>({ name: '', email: '', pw: '', pc: '' });
  const [e, setE] = useState<Partial<Record<F | 'form', string>>>({});
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const set = (k: F) => (x: string) => setV(p => ({ ...p, [k]: x }));
  const score = (v.pw.length >= 8 ? 1 : 0) + (/[a-z]/i.test(v.pw) && /\d/.test(v.pw) ? 1 : 0) + (v.pw.length >= 12 ? 1 : 0);

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (busy) return;
    const E: typeof e = {};
    const email = v.email.trim().toLowerCase();
    if (!v.name.trim()) E.name = 'Enter your full name.';
    if (!email) E.email = 'Enter your email.';
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) E.email = 'Enter a valid email address.';
    if (!v.pw) E.pw = 'Enter your password.';
    else if (v.pw.length < 8 || !/[a-z]/i.test(v.pw) || !/\d/.test(v.pw)) E.pw = 'Use 8+ characters with a letter and a number.';
    if (v.pw !== v.pc) E.pc = 'Passwords do not match.';
    setE(E);
    if (Object.keys(E).length) return;

    const [first, ...rest] = v.name.trim().split(/\s+/);
    setBusy(true);
    try {
      await register({ username: email, email, first_name: first, last_name: rest.join(' '), password: v.pw, password_confirm: v.pc });
      toast('Account created. Please verify your email with the 6-digit code sent to you.');
      go(`/verify-email?email=${encodeURIComponent(email)}`);
    } catch (x) {
      // Show each backend validation message next to the field it belongs to.
      const next: typeof e = {};
      if (x instanceof ApiError) for (const [k, msg] of Object.entries(x.fields)) { const f = FIELD_MAP[k]; if (f && !next[f]) next[f] = msg; }
      if (!Object.keys(next).length) next.form = errMsg(x);
      setE(next);
    } finally { setBusy(false); }
  };

  return (
    <div className="au" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: 16, right: 16 }}><ThemeToggle /></div>
      <Link className="lg" to="/"><Brand /></Link>
      <form className="card" onSubmit={submit} noValidate>
        <h1>Create your account</h1>
        <p className="mu">New accounts get the user role.</p>
        <Field id="name" label="Full name" value={v.name} onChange={set('name')} error={e.name} autoComplete="name" />
        <Field id="email" label="Email" type="email" value={v.email} onChange={set('email')} error={e.email} autoComplete="email" />
        <Field id="pw" label="Password" type="password" value={v.pw} onChange={set('pw')} error={e.pw} autoComplete="new-password" />
        <div className="pm"><i style={{ width: `${score * 33.3}%` }} /></div>
        <p className="n">At least 8 characters, with a letter and a number.</p>
        <Field id="pc" label="Confirm password" type="password" value={v.pc} onChange={set('pc')} error={e.pc} autoComplete="new-password" />
        {e.form && <p className="fe" role="alert">{e.form}</p>}
        <button className="btn" style={{ width: '100%', marginTop: 14 }} disabled={busy}>{busy ? 'Please wait…' : 'Create account'}</button>
        <p className="mu" style={{ textAlign: 'center' }}>Have an account? <Link to="/login">Log in</Link> · <Link to="/">Home</Link></p>
      </form>
    </div>
  );
}
