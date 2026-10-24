import { useState } from 'react';
import { Link } from 'react-router-dom';
import HeroArt from '../components/HeroArt';
import VerifyBox from '../components/VerifyBox';
import { Badge, Brand, Icon, ThemeToggle } from '../lib/ui';
import { FAQ, FEAT } from '../lib/content';
import { SOCIAL_LINKS, type SocialLink } from '../lib/constants';

const LINKS: [string, string][] = [['top', 'Home'], ['about', 'About'], ['features', 'Features'], ['how', 'How it works'], ['uses', 'Use cases'], ['faq', 'FAQ']];
const USES: [string, string][] = [['Students & holders', 'View certificates associated with your account and check IDs.'], ['Institutions', 'Issue certificates and maintain trusted records.'], ['Recruiters', 'Check whether a credential ID has a record.'], ['Organizations', 'Standardize credential checks across teams.'], ['Record administrators', 'Manage issuance data and review recorded activity.']];

function SocialIcon({ id }: { id: SocialLink['id'] }) {
  if (id === 'instagram') {
    return (
      <svg className="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect width="20" height="20" x="2" y="2" rx="5" ry="5" />
        <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
        <line x1="17.5" x2="17.51" y1="6.5" y2="6.5" />
      </svg>
    );
  }
  if (id === 'facebook') {
    return (
      <svg className="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
      </svg>
    );
  }
  return (
    <svg className="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" x2="22" y1="12" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}

export default function Home() {
  const [open, setOpen] = useState(false);
  return <>
    <header className="nv"><div className="c nb"><a className="lg" href="#top"><Brand /></a>
      <button className="hb" aria-label="Toggle menu" aria-expanded={open} onClick={() => setOpen(!open)}><Icon n="menu" /></button>
      <nav className={`nl${open ? ' open' : ''}`} aria-label="Main">{LINKS.map(l => <a key={l[0]} href={`#${l[0]}`} onClick={() => setOpen(false)}>{l[1]}</a>)}
        <span className="nlx"><ThemeToggle /><Link className="btn g" to="/login">Log in</Link><Link className="btn or" to="/register">Get started</Link></span></nav></div></header>
    <main id="top">
      <section className="hero"><div className="c"><div className="ht"><h1>Secure Verification.<br />Practical Lookup.<br /><span className="rd">Trusted Records.</span></h1>
        <p className="hp">OneSmarter CertiVerify checks certificate IDs against trusted records and returns clear, honest results through secure user and admin dashboards.</p>
        <div className="row"><a className="btn big" href="#demo">Verify a Certificate</a><Link className="btn big ol" to="/register">Get Started</Link></div><div className="rl2" />
        <div className="caps">{[['shield', 'ID LOOKUP', 'TRUSTED RECORDS'], ['file', 'CERTIFICATE', 'ISSUANCE'], ['users', 'ROLE-BASED', 'DASHBOARDS']].map(a => <div key={a[1]}><span className="cc"><Icon n={a[0]} /></span><div><b>{a[1]}</b><span>{a[2]}</span></div></div>)}</div>
        <div className="hb2 card" id="demo"><VerifyBox record={false} /></div></div></div><div className="hv"><HeroArt /></div></section>
      <section className="sec" id="about"><div className="c ab"><div><h2>Certificates are easy to share. Hard to check.</h2><p className="mu">Manual verification means emails and waiting. CertiVerify lets issuers register trusted records so anyone with an ID gets a quick, clearly worded answer.</p></div>
        <div>{[['db', 'Trusted records only', 'IDs are matched against records from authorized imports, never user uploads.'], ['shield', 'Honest results', 'Found, not found, invalid or error. A missing ID is not called fake.'], ['chart', 'Admin oversight', 'Read-only logs, analytics and security events. Outcomes can’t be edited.']].map(a => <div className="it" key={a[1]}><span className="ib"><Icon n={a[0]} /></span><div><h3 style={{ margin: 0 }}>{a[1]}</h3><p className="mu" style={{ margin: '2px 0 0' }}>{a[2]}</p></div></div>)}</div></div></section>
      <section className="sec" id="features" style={{ paddingTop: 0 }}><div className="c"><div className="hd"><h2>Everything you need. Nothing invented.</h2><p>No OCR, AI forgery detection or blockchain claims. Just what the platform does.</p></div>
        <div className="bt">{FEAT.map((f, i) => <div key={f[1]} className={`card fc s${[3, 3, 2, 2, 2, 2, 2, 2, 3, 3][i]}`}><div className="ib"><Icon n={f[0]} /></div><h3>{f[1]}</h3><p>{f[2]}</p></div>)}</div></div></section>
      <section className="sec" id="how" style={{ paddingTop: 0 }}><div className="c"><div className="hd"><h2>How it works</h2><p>Three steps from ID to answer.</p></div>
        <ol className="tl">{['Enter a Certificate ID.', 'The ID is checked against trusted records.', 'You see the result and any available matching details.'].map(t => <li key={t}><b>{t}</b></li>)}</ol>
        <div className="grid"><div className="card"><Badge k="ok">Found</Badge><p>A matching record exists.</p></div><div className="card"><Badge k="wn">Not found</Badge><p>No trusted record matched. Not automatically fake.</p></div><div className="card"><Badge k="in">Note</Badge><p>A record match alone doesn’t prove an uploaded image is unchanged.</p></div></div></div></section>
      <section className="sec" id="uses" style={{ paddingTop: 0 }}><div className="c"><div className="hd"><h2>Built for everyone in the loop</h2></div><div className="ul">{USES.map(u => <div key={u[0]}><b>{u[0]}</b><span className="mu">{u[1]}</span></div>)}</div></div></section>
      <section className="sec" id="faq" style={{ paddingTop: 0 }}><div className="c fq"><div><h2>Questions, answered.</h2><p className="mu">Straight answers that match how the product really works.</p></div><div>{FAQ.map(q => <details className="q" key={q[0]}><summary>{q[0]}</summary><p>{q[1]}</p></details>)}</div></div></section>
      <section className="c"><div className="cta"><h2>Ready to check a certificate?</h2><p>Look up an ID in seconds, or create an account to manage your certificates.</p><div className="row"><a className="btn w" href="#demo">Verify a certificate</a><Link className="btn o" style={{ background: '#ffffff22', color: '#fff' }} to="/register">Get started</Link></div></div></section>
    </main>
    <footer className="ft">
      <div className="c grid">
        <div>
          <a className="lg" href="#top"><Brand /></a>
          <p className="mu">Certificate ID verification against trusted records.</p>
        </div>
        <div>
          <h3>Product</h3>
          {LINKS.slice(1, 5).map(l => <a key={l[0]} href={`#${l[0]}`}>{l[1]}</a>)}
        </div>
        <div>
          <h3>Account</h3>
          <Link to="/login">Log in</Link>
          <Link to="/register">Get started</Link>
        </div>
        <div>
          <h3>Connect & Follow</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
            {SOCIAL_LINKS.map(s => (
              <a
                key={s.id}
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={s.ariaLabel}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', textDecoration: 'none' }}
              >
                <SocialIcon id={s.id} />
                <span>{s.name}</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  </>;
}
