import { useState } from 'react';
import { Icon } from '../lib/ui';

interface Props {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  error?: string;
  autoComplete?: string;
  placeholder?: string;
}

/** Label + input (+ show/hide button for passwords) + error text. Used by Login, Register and the MFA form. */
export default function Field({ id, label, value, onChange, type = 'text', error, autoComplete, placeholder }: Props) {
  const [show, setShow] = useState(false);
  const isPassword = type === 'password';
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <div className={isPassword ? 'pw' : ''}>
        <input id={id} type={isPassword && show ? 'text' : type} value={value} autoComplete={autoComplete} placeholder={placeholder} aria-invalid={!!error} onChange={e => onChange(e.target.value)} />
        {isPassword && <button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}><Icon n="eye" /></button>}
      </div>
      {error && <p className="fe">{error}</p>}
    </>
  );
}
