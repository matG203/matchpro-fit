import { FormEvent, useMemo, useState } from 'react';
import { Dumbbell, Sparkles } from 'lucide-react';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

const equipmentOptions = [
  'ball', 'cones', 'bands', 'mini bands', 'dumbbells', 'kettlebell', 'barbell', 'plates', 'bench', 'squat rack',
  'pull-up bar', 'cable machine', 'medicine ball', 'plyo box', 'skipping rope', 'treadmill', 'bike', 'rower',
  'pool', 'mat', 'foam roller', 'heart-rate monitor', 'gps watch', 'gym',
];
const goals = [
  ['ball', 'Ball sharpness'],
  ['speed', 'Speed'],
  ['endurance', 'Endurance'],
  ['strength', 'Strength'],
  ['recovery', 'Recovery'],
];
const xpPreviewFor = (program: any) => {
  if (!program) return 0;
  const factor = { low: 1, medium: 1.35, high: 1.75 }[program.intensity] || 1;
  const load = (program.exercises || []).reduce((sum: number, item: any) => sum + Number(item.sets || 1) * Number(String(item.reps || '1').match(/\d+/)?.[0] || 1) * Math.max(1, Number(item.weightKg || 1)), 0);
  return Math.max(20, Math.round(program.duration * factor) + Math.min(80, Math.round(load / 120)));
};

export default function WorkoutPlannerPage() {
  const [setup, setSetup] = useState({ goal: 'strength', minutes: 45, type: 'gym', equipment: ['dumbbells', 'bench', 'bands', 'ball'] });
  const [program, setProgram] = useState<any>();
  const [message, setMessage] = useState('');
  const xpPreview = useMemo(() => xpPreviewFor(program), [program]);
  function toggleEquipment(item: string) {
    setSetup((current) => ({ ...current, equipment: current.equipment.includes(item) ? current.equipment.filter((value) => value !== item) : [...current.equipment, item] }));
  }
  function updateExercise(index: number, key: string, value: string | number) {
    setProgram((current: any) => ({ ...current, exercises: current.exercises.map((item: any, itemIndex: number) => itemIndex === index ? { ...item, [key]: value } : item) }));
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
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Progressive workout programming</p><h1>Workout Programmer</h1></div>{program && <span className="score-chip"><Sparkles size={16} /> {xpPreview} XP preview</span>}</div><div className="grid-2"><Panel title="Build Your Session"><form className="stack" onSubmit={generate}>{message && <p className={message.includes('complete') ? 'success' : 'error'}>{message}</p>}<div className="form-grid"><div><label>Training goal</label><select value={setup.goal} onChange={(e) => setSetup({ ...setup, goal: e.target.value })}>{goals.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></div><div><label>Minutes available</label><input type="number" min={20} max={120} value={setup.minutes} onChange={(e) => setSetup({ ...setup, minutes: +e.target.value })} /></div><div><label>Base type</label><select value={setup.type} onChange={(e) => setSetup({ ...setup, type: e.target.value })}>{['football', 'running', 'gym', 'cycling', 'swimming', 'other'].map((item) => <option key={item}>{item}</option>)}</select></div></div><div><label>Equipment you have</label><div className="choice-row equipment-grid">{equipmentOptions.map((item) => <button type="button" className={`choice ${setup.equipment.includes(item) ? 'selected' : ''}`} key={item} onClick={() => toggleEquipment(item)}><span>{item}</span><small>{setup.equipment.includes(item) ? 'selected' : 'tap to add'}</small></button>)}</div></div><button><Dumbbell size={18} /> Generate workout</button></form></Panel><Panel title="How Progression Works"><p className="muted">First weights are estimated from your profile, especially age and bodyweight. After you complete sessions, MatchFit checks previous exercises and pushes the next target slightly higher when it is sensible.</p><p className="muted">More demanding sessions earn more XP through duration, intensity, and training volume. You can edit sets, reps, weights, and rest before completing the session.</p></Panel></div><Panel title="Programmed Session">{program ? <div className="stack"><p className="lead">{program.duration} min {program.intensity} {program.type}</p><div className="exercise-list">{program.exercises.map((item: any, index: number) => <div className="exercise-card" key={`${item.name}-${index}`}><div><h3>{item.name}</h3><p className="muted">{item.instruction}</p><p className="muted">{item.progression}</p></div><div className="exercise-fields"><label>Sets<input type="number" min={1} max={10} value={item.sets} onChange={(e) => updateExercise(index, 'sets', +e.target.value)} /></label><label>Reps<input value={item.reps} onChange={(e) => updateExercise(index, 'reps', e.target.value)} /></label><label>Weight kg<input type="number" min={0} step={0.5} value={item.weightKg} onChange={(e) => updateExercise(index, 'weightKg', +e.target.value)} /></label><label>Rest sec<input type="number" min={0} step={15} value={item.restSeconds} onChange={(e) => updateExercise(index, 'restSeconds', +e.target.value)} /></label></div><small className="score-chip">{item.equipment}</small></div>)}</div><button onClick={complete}>Complete programmed workout</button><p className="muted">Completing this session counts for objectives because it came from the programme builder.</p></div> : <p className="muted">Choose your equipment, goal, and time. MatchFit will build a specific editable session with set, rep, weight, and coaching details.</p>}</Panel></div>;
}
