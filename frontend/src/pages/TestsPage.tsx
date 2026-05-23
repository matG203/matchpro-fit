import { FormEvent, useEffect, useState } from 'react';
import { Activity, Gauge, Timer } from 'lucide-react';
import { Empty, Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

const initial: Record<string, string> = {
  sprint30m: '', run5kMinutes: '', yoyoLevel: '', agility505Seconds: '', shuttleRunSeconds: '',
  plankSeconds: '', jumpCm: '', broadJumpCm: '', pushUps: '', pullUps: '', squatKg: '', benchKg: '', deadliftKg: '',
  passingScore: '', dribbleSeconds: '', shootingScore: '', notes: '',
};
const groups = [
  ['Pace', [['sprint30m', '30m Sprint', 'Seconds'], ['run5kMinutes', '5K Run', 'Minutes'], ['yoyoLevel', 'Yo-Yo Test', 'Level']]],
  ['Dribbling And Defending', [['agility505Seconds', '505 Agility', 'Seconds'], ['shuttleRunSeconds', '5-10-5 Shuttle', 'Seconds'], ['dribbleSeconds', 'Cone Dribble Course', 'Seconds']]],
  ['Physical', [['plankSeconds', 'Plank Hold', 'Seconds'], ['jumpCm', 'Vertical Jump', 'cm'], ['broadJumpCm', 'Broad Jump', 'cm'], ['pushUps', 'Push-Ups', 'Reps'], ['pullUps', 'Pull-Ups', 'Reps'], ['squatKg', 'Squat', 'kg'], ['benchKg', 'Bench Press', 'kg'], ['deadliftKg', 'Deadlift', 'kg']]],
  ['Technical', [['passingScore', 'Passing Score', '0-100'], ['shootingScore', 'Shooting Score', '0-100']]],
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
      setMessage(`Testing block saved. +${data.test.xpEarned} XP. Benchmarks can lift card stats to milestone ratings while training still adds smaller gains.`);
      setForm(initial); load();
    } catch (error) { setMessage(errorMessage(error)); }
  }
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Card Benchmarks</p><h1>Fitness Tests</h1></div></div><div className="grid-2"><Panel title="Log Testing Block"><form className="stack" onSubmit={submit}>{message && <p className={message.includes('saved') ? 'success' : 'error'}>{message}</p>}{groups.map(([title, fields]) => <div key={title}><h3>{title}</h3><div className="form-grid">{fields.map(([key, label, unit]) => <div key={key}><label>{label}</label><input type="number" step=".1" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} placeholder={unit} /></div>)}</div></div>)}<div><label>Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Surface, boots, fatigue, or personal best notes" /></div><button><Activity size={18} /> Save Tests</button></form></Panel><Panel title="How Ratings Scale"><div className="stack"><div className="feature-line"><Gauge size={19} /><span>50 is the baseline for everyone. Elite milestone scores can lift a stat much higher, but only up to the benchmark cap earned by the result.</span></div><div className="feature-line"><Timer size={19} /><span>Training still matters: workouts add small gains between tests, and neglected stats can decay over time.</span></div><p className="muted">A world-class result is treated as roughly 95. Nobody is casually handed a 100.</p></div></Panel></div><Panel title="Test History">{tests.length ? <ul className="list">{tests.map((test) => <li key={test.id} className="between"><span><b>{new Date(test.testedAt).toLocaleDateString()}</b><br /><small>{test.sprint30m ? `${test.sprint30m}s 30m | ` : ''}{test.run5kMinutes ? `${test.run5kMinutes}m 5K | ` : ''}{test.agility505Seconds ? `${test.agility505Seconds}s 505 | ` : ''}{test.squatKg ? `${test.squatKg}kg squat | ` : ''}{test.passingScore ? `${test.passingScore} passing` : ''}</small></span><strong>+{test.xpEarned} XP</strong></li>)}</ul> : <Empty>Your first testing block will build a baseline here.</Empty>}</Panel></div>;
}
