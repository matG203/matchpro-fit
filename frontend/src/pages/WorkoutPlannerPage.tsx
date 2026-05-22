import { FormEvent, useMemo, useState } from 'react';
import { Dumbbell, Plus, Sparkles } from 'lucide-react';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

const templates = {
  football: ['Activation ladder', 'First touch wall passes', '1v1 dribble changes', 'Finishing under fatigue'],
  running: ['Easy warm-up', 'Tempo block', 'Acceleration strides', 'Walk down'],
  gym: ['Mobility prep', 'Squat pattern', 'Single-leg strength', 'Core finisher'],
  cycling: ['Cadence ramp', 'Threshold intervals', 'Recovery spin'],
  swimming: ['Technique warm-up', 'Aerobic lengths', 'Breathing reset'],
  other: ['Warm-up', 'Main block', 'Cooldown'],
} as Record<string, string[]>;
const trainedStats: Record<string, string> = {
  football: 'Pace, passing, dribbling and shooting',
  running: 'Pace and physical',
  gym: 'Physical and defending',
  cycling: 'Physical engine',
  swimming: 'Physical recovery',
  other: 'Physical base',
};

export default function WorkoutPlannerPage() {
  const [form, setForm] = useState({ type: 'football', duration: 45, intensity: 'medium', exercises: templates.football.join('\n') });
  const [message, setMessage] = useState('');
  const xpPreview = useMemo(() => Math.max(20, Math.round(form.duration * ({ low: 1, medium: 1.35, high: 1.75 }[form.intensity] || 1))), [form]);
  function useTemplate(type: string) { setForm((current) => ({ ...current, type, exercises: templates[type].join('\n') })); }
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const { data } = await api.post('/workout', { ...form, exercises: form.exercises.split(/\n|,/).map((item) => item.trim()).filter(Boolean) });
      setMessage(`${data.type} logged for +${data.xpEarned} XP. Your player card moved too.`);
    } catch (error) { setMessage(errorMessage(error)); }
  }
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Session builder</p><h1>Workout Planner</h1></div><span className="score-chip"><Sparkles size={16} /> {xpPreview} XP preview</span></div><div className="grid-2"><Panel title="Complete A Session"><form className="stack" onSubmit={submit}>{message && <p className={message.includes('logged') ? 'success' : 'error'}>{message}</p>}<div className="form-grid"><div><label>Training type</label><select value={form.type} onChange={(e) => useTemplate(e.target.value)}>{Object.keys(templates).map((item) => <option key={item}>{item}</option>)}</select></div><div><label>Duration in minutes</label><input type="number" min={5} max={360} value={form.duration} onChange={(e) => setForm({ ...form, duration: +e.target.value })} /></div><div><label>Intensity</label><select value={form.intensity} onChange={(e) => setForm({ ...form, intensity: e.target.value })}>{['low', 'medium', 'high'].map((item) => <option key={item}>{item}</option>)}</select></div></div><div><label>Exercise plan</label><textarea value={form.exercises} onChange={(e) => setForm({ ...form, exercises: e.target.value })} /></div><button><Dumbbell size={18} /> Complete workout</button></form></Panel><Panel title="Training Focus"><p className="lead">{trainedStats[form.type]}</p><ul className="list">{templates[form.type].map((item) => <li key={item} className="inline"><Plus size={16} /> {item}</li>)}</ul><p className="muted" style={{ marginTop: '1rem' }}>Each completed workout awards XP, pushes workout challenges, refreshes readiness, and improves the card stats this session trains.</p></Panel></div></div>;
}
