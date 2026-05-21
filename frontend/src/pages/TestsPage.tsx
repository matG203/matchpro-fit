import { FormEvent, useState } from 'react';
import { Panel } from '../components/ui';
import api from '../lib/api';

const tests = ['5K time', '30m sprint', 'Yo-Yo level', 'Plank hold', 'Vertical jump'];
export default function TestsPage() {
  const [results, setResults] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); await api.post('/xp/award', { amount: 50, reason: 'fitness test' }); setMessage('Test set logged. +50 XP.'); }
  return <div className="page"><h1>Fitness Tests</h1><Panel title="Testing Block"><form className="form-grid" onSubmit={submit}>{message && <p className="success">{message}</p>}{tests.map((test) => <div key={test}><label>{test}</label><input value={results[test] || ''} onChange={(e) => setResults({ ...results, [test]: e.target.value })} /></div>)}<button>Log tests</button></form></Panel></div>;
}
