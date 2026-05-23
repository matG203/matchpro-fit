import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage } from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { await login(form.email, form.password); navigate('/dashboard'); }
    catch (requestError) { setError(errorMessage(requestError)); }
    finally { setBusy(false); }
  }
  return (
    <main className="auth-page"><form className="auth-card stack" onSubmit={submit}>
      <Link className="brand" to="/">MatchFit <b>Pro</b></Link><h1>Sign In</h1>
      {error && <p className="error">{error}</p>}
      <div><label>Email or Username</label><input required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
      <div><label>Password</label><input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
      <button disabled={busy}>{busy ? 'Signing In...' : 'Sign In'}</button>
      <p className="muted"><Link to="/forgot-password">Forgot password?</Link></p>
      <p className="muted">New to MatchFit? <Link to="/register">Create Account</Link></p>
    </form></main>
  );
}
