import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage } from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function RegisterPage() {
  const register = useAuthStore((state) => state.register);
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', username: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError('');
    try { await register(form.email, form.username, form.password); navigate('/onboarding'); }
    catch (requestError) { setError(errorMessage(requestError)); }
    finally { setBusy(false); }
  }
  return (
    <main className="auth-page"><form className="auth-card stack" onSubmit={submit}>
      <Link className="brand" to="/">MatchFit <b>Pro</b></Link><h1>Create account</h1>
      {error && <p className="error">{error}</p>}
      <div><label>Email</label><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="player@example.com" /></div>
      <div><label>Username</label><input required minLength={3} pattern="[a-zA-Z0-9_]+" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') })} placeholder="midfield_engine" /></div>
      <div><label>Password</label><input type="password" minLength={8} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="At least 8 characters" /></div>
      <button disabled={busy}>{busy ? 'Creating...' : 'Create Account'}</button>
      <p className="muted">Already registered? <Link to="/login">Sign in</Link></p>
    </form></main>
  );
}
