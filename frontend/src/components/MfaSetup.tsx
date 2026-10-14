import { useState, type FormEvent } from 'react';
import { toast } from '../lib/ui';
import { errMsg, mfaService } from '../services';

type Step = 'idle' | 'scan' | 'done';

/** Google Authenticator enrolment: POST mfa/setup (QR) -> user scans -> POST mfa/confirm (6-digit code). */
export default function MfaSetup() {
  const [step, setStep] = useState<Step>('idle');
  const [qr, setQr] = useState('');
  const [hint, setHint] = useState('');
  const [code, setCode] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setErr(''); setBusy(true);
    try {
      const r = await mfaService.setup();
      setQr(r.qr); setHint(r.message); setCode(''); setStep('scan');
    } catch (e) {
      const m = errMsg(e);
      if (/already enabled/i.test(m)) setStep('done'); else setErr(m);
    } finally { setBusy(false); }
  };

  const confirm = async (ev: FormEvent) => {
    ev.preventDefault();
    if (busy) return;
    if (!/^\d{6}$/.test(code)) return setErr('Enter the six-digit code from Google Authenticator.');
    setErr(''); setBusy(true);
    try {
      await mfaService.confirm(code);
      setStep('done'); setQr(''); // success is shown only after the backend confirmed it
      toast('Google Authenticator enabled.');
    } catch (e) { setErr(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <div className="card">
      <h3>Two-step verification</h3>
      {step === 'idle' && <>
        <p className="mu">Protect your account with a six-digit code from Google Authenticator each time you sign in.</p>
        {err && <p className="fe" role="alert">{err}</p>}
        <button className="btn s" onClick={start} disabled={busy}>{busy ? 'Please wait…' : 'Set up Google Authenticator'}</button>
      </>}
      {step === 'scan' && <form onSubmit={confirm} noValidate>
        <p className="mu">{hint || 'Scan this QR code with Google Authenticator, then enter the six-digit code.'}</p>
        <img src={qr} alt="QR code for Google Authenticator" style={{ width: 200, height: 200, background: '#fff', padding: 8, borderRadius: 10 }} />
        <label htmlFor="mfa-confirm">Six-digit code</label>
        <input id="mfa-confirm" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} aria-invalid={!!err} />
        {err && <p className="fe" role="alert">{err}</p>}
        <button className="btn s" style={{ marginTop: 12 }} disabled={busy}>{busy ? 'Checking…' : 'Confirm and enable'}</button>
      </form>}
      {step === 'done' && <p role="status"><b>Google Authenticator is enabled.</b> You will be asked for a code the next time you sign in.</p>}
    </div>
  );
}
