import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import api, { errorMessage } from '../lib/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const { data } = await api.post('/auth/forgot-password', { email });
      setMessage(data.message);
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }
  return <main className="auth-page"><form className="auth-card stack" onSubmit={submit}><Link className="brand" to="/">MatchFit <b>Pro</b></Link><h1>Reset Password</h1>{message && <p className={message.includes('enabled') ? 'success' : 'error'}>{message}</p>}<div><label>Email Address</label><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="player@example.com" /></div><button>Send Reset Link</button><p className="muted">Remembered it? <Link to="/login">Sign In</Link></p></form></main>;
}
