import { FormEvent, useEffect, useState } from 'react';
import { Panel } from '../components/ui';
import api from '../lib/api';

const days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const decode = (value: any) => Array.isArray(value) ? value.join(', ') : '';
export default function RoutinePage() {
  const [routine, setRoutine] = useState<Record<string, string>>(Object.fromEntries(days.map((day) => [day, ''])));
  const [saved, setSaved] = useState(false);
  useEffect(() => { api.get('/routine').then(({ data }) => setRoutine(Object.fromEntries(days.map((day) => [day, decode(data[day])])))); }, []);
  async function save(event: FormEvent) { event.preventDefault(); await api.put('/routine', Object.fromEntries(days.map((day) => [day, routine[day].split(',').map((item) => item.trim()).filter(Boolean)]))); setSaved(true); }
  return <div className="page"><h1>Daily Routine</h1><Panel title="Weekly Plan"><form className="stack" onSubmit={save}>{saved && <p className="success">Routine saved.</p>}<div className="form-grid">{days.map((day) => <div className="routine-day" key={day}><label>{day}</label><input value={routine[day]} onChange={(e) => setRoutine({ ...routine, [day]: e.target.value })} placeholder="Tempo run, mobility" /></div>)}</div><button>Save plan</button></form></Panel></div>;
}
