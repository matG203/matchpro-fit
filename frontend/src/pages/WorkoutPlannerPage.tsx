import { FormEvent, useState } from 'react';
import { Dumbbell } from 'lucide-react';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

export default function WorkoutPlannerPage() {
  const [form, setForm] = useState({ type: 'football', duration: 45, intensity: 'medium', exercises: 'warm-up, first touch drills, small-sided game' });
  const [message, setMessage] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const { data } = await api.post('/workout', { ...form, exercises: form.exercises.split(',').map((item) => item.trim()).filter(Boolean) });
      setMessage(`${data.type} logged for +${data.xpEarned} XP.`);
    } catch (error) { setMessage(errorMessage(error)); }
  }
  return <div className="page"><h1>Workout Planner</h1><Panel title="Complete a session"><form className="stack" onSubmit={submit}>{message && <p className={message.includes('XP') ? 'success' : 'error'}>{message}</p>}<div className="form-grid"><div><label>Type</label><select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{['running', 'gym', 'football', 'swimming', 'cycling', 'other'].map((item) => <option key={item}>{item}</option>)}</select></div><div><label>Duration in minutes</label><input type="number" min={5} max={360} value={form.duration} onChange={(e) => setForm({ ...form, duration: +e.target.value })} /></div><div><label>Intensity</label><select value={form.intensity} onChange={(e) => setForm({ ...form, intensity: e.target.value })}>{['low', 'medium', 'high'].map((item) => <option key={item}>{item}</option>)}</select></div></div><div><label>Exercises</label><textarea value={form.exercises} onChange={(e) => setForm({ ...form, exercises: e.target.value })} /></div><button><Dumbbell size={18} /> Complete workout</button></form></Panel></div>;
}
