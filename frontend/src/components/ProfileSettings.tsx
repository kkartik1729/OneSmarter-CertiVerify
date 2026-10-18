import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useAuth } from '../context/AuthContext';
import { User, Mail, ShieldCheck, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from '../lib/ui';
import { errMsg } from '../services';
import { getCountries, getCountryCallingCode, parsePhoneNumberFromString } from 'libphonenumber-js/max';
import type { CountryCode } from 'libphonenumber-js';

type PhoneCountry = { code: CountryCode; name: string; flag: string; dial: string };
const countryDisplayNames = new (Intl as unknown as {
  DisplayNames: new (locales: string[], options: { type: string }) => { of(code: string): string | undefined };
}).DisplayNames(['en'], { type: 'region' });
const flagForCountry = (code: string) => String.fromCodePoint(...code.toUpperCase().split('').map((letter) => letter.charCodeAt(0) + 127397));
const phoneCountries: PhoneCountry[] = getCountries().map((code) => ({
  code,
  name: countryDisplayNames.of(code) ?? code,
  flag: flagForCountry(code),
  dial: `+${getCountryCallingCode(code)}`,
})).sort((a, b) => a.name.localeCompare(b.name));

export default function ProfileSettings() {
  const { user, updateProfile } = useAuth();

  const [organization, setOrganization] = useState(user?.organization ?? '');
  const savedPhone = user?.phone ?? '';
  const parsedSavedPhone = savedPhone.startsWith('+') ? parsePhoneNumberFromString(savedPhone) : undefined;
  const initialCountryCode = parsedSavedPhone?.country && phoneCountries.some((item) => item.code === parsedSavedPhone.country)
    ? parsedSavedPhone.country
    : 'IN';
  const initialNationalPhone = parsedSavedPhone?.country ? parsedSavedPhone.nationalNumber : savedPhone.replace(/\D/g, '');
  const [countryCode, setCountryCode] = useState<CountryCode>(initialCountryCode);
  const country = phoneCountries.find((item) => item.code === countryCode) ?? phoneCountries[0];
  const [phone, setPhone] = useState(initialNationalPhone);
  const [countryMenuOpen, setCountryMenuOpen] = useState(false);
  const [countrySearch, setCountrySearch] = useState('');
  const countryMenuRef = useRef<HTMLDivElement>(null);
  const countrySearchRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [organizationError, setOrganizationError] = useState<string | null>(null);
  const [phoneError, setPhoneError] = useState<string | null>(null);

  useEffect(() => {
    if (countryMenuOpen) countrySearchRef.current?.focus();
  }, [countryMenuOpen]);

  useEffect(() => {
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!countryMenuRef.current?.contains(event.target as Node)) setCountryMenuOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutsideClick);
    return () => document.removeEventListener('pointerdown', closeOnOutsideClick);
  }, []);

  const filteredCountries = phoneCountries.filter((item) =>
    `${item.name} ${item.code} ${item.dial}`.toLowerCase().includes(countrySearch.trim().toLowerCase()),
  );

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    const org = organization.trim();
    if (org && (!/[\p{L}]/u.test(org) || /\d|[^\p{L}\s.,&'’()\-/+]/u.test(org))) {
      setOrganizationError('Please enter a valid organization name.');
      return;
    }
    setOrganizationError(null);
    const unchangedLegacyPhone = countryCode === initialCountryCode && phone === initialNationalPhone;
    const parsedPhone = phone ? parsePhoneNumberFromString(phone, countryCode) : undefined;
    if (phone && !unchangedLegacyPhone && (
      (countryCode === 'IN' && !/^\d{10}$/.test(phone))
      || !parsedPhone?.isValid()
      || (parsedPhone.country && parsedPhone.country !== countryCode)
    )) {
      setPhoneError(countryCode === 'IN'
        ? 'Enter exactly 10 valid national digits for India (do not include +91).'
        : `Enter a valid phone number for ${country.name}.`);
      return;
    }
    setPhoneError(null);
    setSaving(true);
    try {
      const phoneToSave = unchangedLegacyPhone ? savedPhone : phone ? parsedPhone?.number ?? '' : '';
      await updateProfile({ organization: org, phone: phoneToSave });
      setSuccess(true);
      toast('Profile updated successfully.');
    } catch (err) {
      const fieldErrors = err && typeof err === 'object' && 'fields' in err ? (err as { fields?: Record<string, string> }).fields : undefined;
      setOrganizationError(fieldErrors?.organization ?? null);
      setPhoneError(fieldErrors?.phone ?? null);
      setError(err && typeof err === 'object' && 'status' in err && (err as { status: number }).status >= 500
        ? 'Unable to update your profile. Please try again.'
        : errMsg(err).includes('PATCH') || errMsg(err).includes('Method Not Allowed')
          ? 'Unable to update your profile. Please try again.'
          : errMsg(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm">
      <div className="mb-6">
        <h3 className="text-lg font-bold text-slate-900 dark:text-white">
          Account Profile Information
        </h3>
      </div>

      {success && (
        <div className="mb-6 p-3.5 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-300 flex items-center gap-2.5 text-xs font-medium">
          <CheckCircle2 className="w-4 h-4 text-teal-600 flex-shrink-0" />
          <span>Profile updated successfully.</span>
        </div>
      )}

      {error && (
        <div className="mb-6 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-300 flex items-center gap-2.5 text-xs font-medium">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Username (read-only) */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
              Username
            </label>
            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm">
              <User className="w-4 h-4 text-slate-400" />
              <span>{user?.username || '—'}</span>
            </div>
          </div>

          {/* Email (read-only) */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Email Address
              </label>
              {user?.emailVerified ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/60 px-2 py-0.5 rounded-full">
                  <CheckCircle2 className="w-3 h-3" /> Verified
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800/60 px-2 py-0.5 rounded-full">
                  <AlertCircle className="w-3 h-3" /> Unverified
                </span>
              )}
            </div>
            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm">
              <Mail className="w-4 h-4 text-slate-400" />
              <span>{user?.email || '—'}</span>
            </div>
          </div>

          {/* Full Name */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
              Full Name
            </label>
            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm">
              <User className="w-4 h-4 text-slate-400" />
              <span>{user?.name || '—'}</span>
            </div>
          </div>

          {/* Assigned Role */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
              Assigned System Role
            </label>
            <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm">
              <ShieldCheck className="w-4 h-4 text-teal-600" />
              <span className="uppercase font-semibold text-xs tracking-wider">
                {user?.role}
              </span>
            </div>
          </div>

          {/* Organization (editable) */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Organization / Company
            </label>
            <div className="relative max-w-xl">
              <input
                type="text"
                value={organization}
                onChange={e => setOrganization(e.target.value)}
                placeholder="e.g. Acme Corporation"
                className="w-full px-3.5 py-2.5 text-sm bg-white dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-600"
              />
            </div>
            {organizationError && <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{organizationError}</p>}
          </div>

          {/* Phone (editable) */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
              Phone Number
            </label>
            <div className="relative">
              <div className="relative flex min-w-0 max-w-xl gap-2">
                <div className="relative shrink-0" ref={countryMenuRef}>
                  <button type="button" aria-label={`Phone country: ${country.name}, ${country.dial}`} aria-haspopup="listbox" aria-expanded={countryMenuOpen} onClick={() => { setCountrySearch(''); setCountryMenuOpen((open) => !open); }} className="inline-flex h-full min-h-11 items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-white">
                    <span aria-hidden="true">{country.flag}</span><span>{country.dial}</span><span aria-hidden="true" className="text-slate-500">▾</span>
                  </button>
                  {countryMenuOpen && <div className="absolute left-0 top-full z-30 mt-1 w-[min(20rem,calc(100vw-3rem))] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900">
                    <div className="border-b border-slate-200 p-2 dark:border-slate-700">
                      <input ref={countrySearchRef} type="search" value={countrySearch} onChange={event => setCountrySearch(event.target.value)} onKeyDown={event => { if (event.key === 'Escape') setCountryMenuOpen(false); }} placeholder="Search country or calling code" aria-label="Search countries" className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 dark:border-slate-600 dark:bg-slate-800 dark:text-white" />
                    </div>
                    <div role="listbox" aria-label="Countries" className="max-h-64 overflow-y-auto py-1">
                      {filteredCountries.map(item => <button key={item.code} type="button" role="option" aria-selected={item.code === countryCode} onClick={() => { setCountryCode(item.code); setCountryMenuOpen(false); setPhoneError(null); }} className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800 ${item.code === countryCode ? 'bg-teal-50 dark:bg-teal-950/50' : ''}`}>
                        <span className="w-6 text-center" aria-hidden="true">{item.flag}</span><span className="min-w-0 flex-1 truncate text-slate-800 dark:text-slate-100">{item.name}</span><span className="text-slate-500 dark:text-slate-400">{item.dial}</span>
                      </button>)}
                      {filteredCountries.length === 0 && <div className="px-3 py-3 text-sm text-slate-500">No countries found.</div>}
                    </div>
                  </div>}
                </div>
                <input type="tel" inputMode="tel" autoComplete="tel-national" value={phone} onChange={event => {
                  const entered = event.target.value.trim();
                  if (entered.startsWith('+')) {
                    const parsed = parsePhoneNumberFromString(entered);
                    if (parsed?.country && phoneCountries.some(item => item.code === parsed.country)) {
                      setCountryCode(parsed.country);
                      setPhone(parsed.nationalNumber);
                      setPhoneError(null);
                      return;
                    }
                  }
                  setPhone(entered.replace(/[^\d]/g, ''));
                  setPhoneError(null);
                }} placeholder="National phone number" aria-label={`National phone number for ${country.name}, ${country.dial}`} className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 dark:border-slate-700 dark:bg-slate-800/60 dark:text-white" />
              </div>
            </div>
            {phoneError && <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{phoneError}</p>}
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-slate-200 dark:border-slate-800">
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 disabled:opacity-50 rounded-xl shadow-sm transition"
          >
            {saving ? 'Saving changes...' : 'Save Profile'}
          </button>
        </div>
      </form>
    </div>
  );
}
