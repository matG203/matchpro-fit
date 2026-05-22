import { FormEvent, useEffect, useState } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import { Panel } from '../components/ui';
import api from '../lib/api';

export default function HealthPage() {
  const [metrics, setMetrics] = useState<any[]>([]);
  const [form, setForm] = useState({ steps: 8000, sleepHours: 7.5, heartRate: 62, weight: 72, hydration: 2.3 });
  const [readiness, setReadiness] = useState<number>();
  const load = () => api.get('/health').then((response) => setMetrics(response.data));
  useEffect(() => { load(); }, []);
  async function submit(event: FormEvent) { event.preventDefault(); const { data } = await api.post('/health', form); setReadiness(data.readiness.score); load(); }
  const chart = metrics.slice().reverse().map((item) => ({ ...item, day: new Date(item.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }));
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Recovery inputs</p><h1>Health</h1></div>{readiness !== undefined && <span className="score-chip">Readiness now {readiness}%</span>}</div><div className="grid-2"><Panel title="Daily Metrics"><form className="form-grid" onSubmit={submit}>{Object.entries(form).map(([key, value]) => <div key={key}><label>{key}</label><input type="number" step={key.match(/sleep|weight|hydration/) ? '.1' : '1'} value={value} onChange={(e) => setForm({ ...form, [key]: +e.target.value })} /></div>)}<button>Log health</button></form></Panel><Panel title="Recovery Trend"><div style={{ height: 280 }}><ResponsiveContainer><LineChart data={chart}><XAxis dataKey="day" stroke="#9caecb" /><Tooltip contentStyle={{ background: '#071020', border: '1px solid #3b82f6' }} /><Line dataKey="sleepHours" name="Sleep hours" stroke="#60a5fa" strokeWidth={3} /><Line dataKey="hydration" name="Hydration L" stroke="#34d399" strokeWidth={3} /></LineChart></ResponsiveContainer></div></Panel></div><div className="grid-2"><Panel title="Load Trend"><div style={{ height: 250 }}><ResponsiveContainer><LineChart data={chart}><XAxis dataKey="day" stroke="#9caecb" /><Tooltip contentStyle={{ background: '#071020', border: '1px solid #3b82f6' }} /><Line dataKey="steps" name="Steps" stroke="#fbbf24" strokeWidth={3} /><Line dataKey="heartRate" name="Heart rate" stroke="#fb7185" strokeWidth={3} /></LineChart></ResponsiveContainer></div></Panel><Panel title="Recent Logs"><ul className="list">{metrics.map((item) => <li className="between" key={item.id}><span>{new Date(item.date).toLocaleDateString()}<br /><small>{item.sleepHours || 0}h sleep | {item.hydration || 0}L water | HR {item.heartRate || '-'}</small></span><strong>{item.steps || 0} steps</strong></li>)}</ul></Panel></div></div>;
}
