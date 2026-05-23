import { FormEvent, useEffect, useState } from 'react';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

export default function AdminPage() {
  const [form, setForm] = useState({ login: '', password: '' });
  const [message, setMessage] = useState('');
  const [reports, setReports] = useState<any[]>([]);
  const loadReports = () => api.get('/admin/reports').then((response) => setReports(response.data)).catch(() => setReports([]));
  useEffect(() => { loadReports(); }, []);
  async function reset(event: FormEvent) {
    event.preventDefault(); setMessage('');
    try {
      const { data } = await api.post('/admin/reset-password', form);
      setMessage(data.message);
      setForm({ login: '', password: '' });
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Friend Admin</p><h1>Admin</h1></div></div><div className="grid-2"><Panel title="Reset Password"><form className="stack" onSubmit={reset}>{message && <p className={message.includes('reset') ? 'success' : 'error'}>{message}</p>}<div><label>Email Or Username</label><input required value={form.login} onChange={(event) => setForm({ ...form, login: event.target.value })} /></div><div><label>Temporary Password</label><input required minLength={8} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></div><button>Reset Password</button></form></Panel><Panel title="Latest Reports">{reports.length ? <ul className="list">{reports.map((report) => <li key={report.id}><b>{report.category}</b> from {report.user?.username}<br /><small>{new Date(report.createdAt).toLocaleString()}</small><p>{report.message}</p></li>)}</ul> : <p className="muted">No reports yet.</p>}</Panel></div></div>;
}
