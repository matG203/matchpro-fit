import { FormEvent, useEffect, useState } from 'react';
import { Activity, Gauge, Timer } from 'lucide-react';
import { Empty, Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

const initial = { sprint30m: '', run5kMinutes: '', yoyoLevel: '', plankSeconds: '', jumpCm: '', notes: '' };
const fields = [
  ['sprint30m', '30m sprint', 'seconds'],
  ['run5kMinutes', '5K run', 'minutes'],
  ['yoyoLevel', 'Yo-Yo level', 'level'],
  ['plankSeconds', 'Plank hold', 'seconds'],
  ['jumpCm', 'Vertical jump', 'cm'],
] as const;

export default function TestsPage() {
  const [form, setForm] = useState(initial);
  const [tests, setTests] = useState<any[]>([]);
  const [message, setMessage] = useState('');
  const load = () => api.get('/tests').then((response) => setTests(response.data));
  useEffect(() => { load(); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setMessage('');
    try {
      const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== '').map(([key, value]) => [key, key === 'notes' ? value : Number(value)]));
      const { data } = await api.post('/tests', payload);
      setMessage(`Test block saved. +${data.test.xpEarned} XP and your card progressed.`);
      setForm(initial); load();
    } catch (error) { setMessage(errorMessage(error)); }
  }
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Card progression</p><h1>Fitness Tests</h1></div></div><div className="grid-2"><Panel title="Log Testing Block"><form className="stack" onSubmit={submit}>{message && <p className={message.includes('saved') ? 'success' : 'error'}>{message}</p>}<div className="form-grid">{fields.map(([key, label, unit]) => <div key={key}><label>{label}</label><input type="number" step=".1" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} placeholder={unit} /></div>)}</div><div><label>Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Surface, boots, fatigue, or personal best notes" /></div><button><Activity size={18} /> Save tests</button></form></Panel><Panel title="Why Test"><div className="stack"><div className="feature-line"><Gauge size={19} /><span>Sprint and endurance results feed pace, dribbling, and physical ratings.</span></div><div className="feature-line"><Timer size={19} /><span>Plank and jump results sharpen physical duels and card overall.</span></div><p className="muted">Log repeat blocks over time and use workouts between tests to lift your next card review.</p></div></Panel></div><Panel title="Test History">{tests.length ? <ul className="list">{tests.map((test) => <li key={test.id} className="between"><span><b>{new Date(test.testedAt).toLocaleDateString()}</b><br /><small>{test.sprint30m ? `${test.sprint30m}s sprint | ` : ''}{test.run5kMinutes ? `${test.run5kMinutes}m 5K | ` : ''}{test.yoyoLevel ? `Yo-Yo ${test.yoyoLevel} | ` : ''}{test.plankSeconds ? `${test.plankSeconds}s plank` : ''}</small></span><strong>+{test.xpEarned} XP</strong></li>)}</ul> : <Empty>Your first test block will build a baseline here.</Empty>}</Panel></div>;
}
