import { FormEvent, useState } from 'react';
import { errorMessage } from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function OnboardingPage() {
  const complete = useAuthStore((state) => state.completeOnboarding);
  const user = useAuthStore((state) => state.user);
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ displayName: user?.displayName || '', position: user?.position || 'CM', teamName: user?.teamName || '', age: user?.age || 18, height: user?.height || 175, weight: user?.weight || 72 });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (step === 0) return setStep(1);
    setBusy(true); setError('');
    try { await complete(form); }
    catch (requestError) { setError(errorMessage(requestError)); }
    finally { setBusy(false); }
  }
  return (
    <main className="auth-page"><form className="auth-card stack" onSubmit={submit}>
      <span className="eyebrow">Step {step + 1} of 2</span><h1>Build your profile</h1>{error && <p className="error">{error}</p>}
      {step === 0 ? <>
        <div><label>Display name</label><input value={form.displayName} onChange={(e) => setForm({ ...form, displayName: e.target.value })} placeholder={user?.username} /></div>
        <div><label>Position</label><select value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })}>{['GK', 'CB', 'FB', 'CDM', 'CM', 'CAM', 'Winger', 'ST'].map((item) => <option key={item}>{item}</option>)}</select></div>
        <div><label>Team name</label><input value={form.teamName} onChange={(e) => setForm({ ...form, teamName: e.target.value })} placeholder="Sunday XI" /></div>
      </> : <div className="form-grid">
        <div><label>Age</label><input type="number" min={8} max={90} required value={form.age} onChange={(e) => setForm({ ...form, age: +e.target.value })} /></div>
        <div><label>Height (cm)</label><input type="number" min={80} max={260} required value={form.height} onChange={(e) => setForm({ ...form, height: +e.target.value })} /></div>
        <div><label>Weight (kg)</label><input type="number" min={25} max={400} required value={form.weight} onChange={(e) => setForm({ ...form, weight: +e.target.value })} /></div>
      </div>}
      <div className="actions">{step > 0 && <button type="button" className="secondary" onClick={() => setStep(0)}>Back</button>}<button disabled={busy}>{step ? busy ? 'Saving...' : 'Enter dashboard' : 'Continue'}</button></div>
    </form></main>
  );
}
