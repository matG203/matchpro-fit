import { FormEvent, useMemo, useState } from 'react';
import { Dumbbell, Plus, Sparkles } from 'lucide-react';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

const equipmentOptions = ['ball', 'cones', 'bands', 'dumbbells', 'barbell', 'gym', 'bike'];
const goals = [
  ['ball', 'Ball sharpness'],
  ['speed', 'Speed'],
  ['endurance', 'Endurance'],
  ['strength', 'Strength'],
  ['recovery', 'Recovery'],
];

export default function WorkoutPlannerPage() {
  const [setup, setSetup] = useState({ goal: 'ball', minutes: 45, type: 'football', equipment: ['ball', 'cones'] });
  const [program, setProgram] = useState<any>();
  const [message, setMessage] = useState('');
  const xpPreview = useMemo(() => program ? Math.max(20, Math.round(program.duration * ({ low: 1, medium: 1.35, high: 1.75 }[program.intensity] || 1))) : 0, [program]);
  function toggleEquipment(item: string) {
    setSetup((current) => ({ ...current, equipment: current.equipment.includes(item) ? current.equipment.filter((value) => value !== item) : [...current.equipment, item] }));
  }
  async function generate(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    try {
      const { data } = await api.post('/program/generate', setup);
      setProgram(data.program);
    } catch (error) { setMessage(errorMessage(error)); }
  }
  async function complete() {
    if (!program) return;
    try {
      const { data } = await api.post('/program/complete', program);
      setMessage(`Program complete. +${data.workout.xpEarned} XP and readiness is now ${data.readiness.score}%.`);
    } catch (error) { setMessage(errorMessage(error)); }
  }
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Equipment-based programming</p><h1>Workout Programmer</h1></div>{program && <span className="score-chip"><Sparkles size={16} /> {xpPreview} XP</span>}</div><div className="grid-2"><Panel title="Build Your Session"><form className="stack" onSubmit={generate}>{message && <p className={message.includes('complete') ? 'success' : 'error'}>{message}</p>}<div className="form-grid"><div><label>Training goal</label><select value={setup.goal} onChange={(e) => setSetup({ ...setup, goal: e.target.value })}>{goals.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></div><div><label>Minutes available</label><input type="number" min={20} max={120} value={setup.minutes} onChange={(e) => setSetup({ ...setup, minutes: +e.target.value })} /></div><div><label>Base type</label><select value={setup.type} onChange={(e) => setSetup({ ...setup, type: e.target.value })}>{['football', 'running', 'gym', 'cycling', 'swimming', 'other'].map((item) => <option key={item}>{item}</option>)}</select></div></div><div><label>Equipment you have</label><div className="choice-row">{equipmentOptions.map((item) => <button type="button" className={`choice ${setup.equipment.includes(item) ? 'selected' : ''}`} key={item} onClick={() => toggleEquipment(item)}><span>{item}</span><small>{setup.equipment.includes(item) ? 'selected' : 'tap to add'}</small></button>)}</div></div><button><Dumbbell size={18} /> Generate workout</button></form></Panel><Panel title="Programmed Session">{program ? <div className="stack"><p className="lead">{program.duration} min {program.intensity} {program.type}</p><ul className="list">{program.exercises.map((item: string) => <li key={item} className="inline"><Plus size={16} /> {item}</li>)}</ul><button onClick={complete}>Complete programmed workout</button><p className="muted">Completing this session counts for daily and weekly objectives because it came from the programme builder.</p></div> : <p className="muted">Choose your equipment, goal, and time. MatchFit will build a session that feeds XP, card stats, objectives, and long-term readiness.</p>}</Panel></div></div>;
}
