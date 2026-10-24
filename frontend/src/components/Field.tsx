import { useState, type InputHTMLAttributes } from 'react';
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
  inputMode?: InputHTMLAttributes<HTMLInputElement>['inputMode'];
  maxLength?: number;
}

/** Label + input (+ show/hide button for passwords) + error text. Used by Login, Register and the MFA form. */
export default function Field({ id, label, value, onChange, type = 'text', error, autoComplete, placeholder, inputMode, maxLength }: Props) {
  const [show, setShow] = useState(false);
  const isPassword = type === 'password';
  return (
    <>
      <label htmlFor={id}>{label}</label>
      <div className={isPassword ? 'pw' : ''}>
        <input id={id} type={isPassword && show ? 'text' : type} value={value} autoComplete={autoComplete} placeholder={placeholder} inputMode={inputMode} maxLength={maxLength} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} onChange={e => onChange(e.target.value)} />
        {isPassword && <button type="button" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow(!show)}><Icon n="eye" /></button>}
      </div>
      {error && <p id={`${id}-error`} className="fe">{error}</p>}
    </>
  );
}
