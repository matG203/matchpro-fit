import { FormEvent, useMemo, useState } from 'react';
import { Dumbbell, Plus, Sparkles, Trash2 } from 'lucide-react';
import { Panel } from '../components/ui';
import api, { errorMessage } from '../lib/api';

type ProgramExercise = {
  name: string;
  sets: number;
  reps: string;
  weightKg: number;
  restSeconds: number;
  equipment: string;
  bodyParts: string[];
  instruction: string;
  progression?: string;
};

type Program = {
  type: string;
  duration: number;
  intensity: string;
  targetBodyParts?: string[];
  exercises: ProgramExercise[];
  recommended?: ProgramExercise[];
};

const equipmentOptions = [
  'ball', 'cones', 'bands', 'mini bands', 'dumbbells', 'kettlebell', 'barbell', 'plates', 'bench', 'squat rack',
  'pull-up bar', 'cable machine', 'medicine ball', 'plyo box', 'skipping rope', 'treadmill', 'bike', 'rower',
  'pool', 'mat', 'foam roller', 'heart-rate monitor', 'gps watch', 'gym',
];

const bodyPartOptions = [
  'quads', 'hamstrings', 'glutes', 'calves', 'ankles', 'hip flexors', 'adductors', 'chest', 'back', 'shoulders',
  'biceps', 'triceps', 'core', 'conditioning', 'technical', 'coordination', 'shooting', 'feet', 'recovery',
];

const goals = [
  ['ball', 'Ball Sharpness'],
  ['speed', 'Speed'],
  ['endurance', 'Endurance'],
  ['strength', 'Strength'],
  ['recovery', 'Recovery'],
];

const blankExercise: ProgramExercise = {
  name: 'Custom exercise',
  sets: 3,
  reps: '10',
  weightKg: 0,
  restSeconds: 60,
  equipment: 'bodyweight',
  bodyParts: ['core'],
  instruction: 'Write your own coaching notes here.',
  progression: 'Custom exercise added by you.',
};

const xpPreviewFor = (program?: Program) => {
  if (!program) return 0;
  const factor = { low: 1, medium: 1.35, high: 1.75 }[program.intensity as 'low' | 'medium' | 'high'] || 1;
  const load = (program.exercises || []).reduce((sum, item) => {
    const reps = Number(String(item.reps || '1').match(/\d+/)?.[0] || 1);
    return sum + Number(item.sets || 1) * reps * Math.max(1, Number(item.weightKg || 1));
  }, 0);
  return Math.max(20, Math.round(program.duration * factor) + Math.min(80, Math.round(load / 120)));
};

export default function WorkoutPlannerPage() {
  const [setup, setSetup] = useState({
    goal: 'strength',
    minutes: 45,
    type: 'gym',
    equipment: ['dumbbells', 'bench', 'bands', 'ball'],
    bodyParts: ['quads', 'glutes'],
  });
  const [program, setProgram] = useState<Program>();
  const [message, setMessage] = useState('');
  const [exerciseSearch, setExerciseSearch] = useState('');
  const xpPreview = useMemo(() => xpPreviewFor(program), [program]);
  const recommendedExercises = useMemo(() => {
    const query = exerciseSearch.trim().toLowerCase();
    return (program?.recommended || []).filter((item) => {
      const searchable = `${item.name} ${item.equipment} ${item.bodyParts.join(' ')} ${item.instruction}`.toLowerCase();
      return !query || searchable.includes(query);
    });
  }, [exerciseSearch, program]);

  function toggleList(key: 'equipment' | 'bodyParts', item: string) {
    setSetup((current) => ({
      ...current,
      [key]: current[key].includes(item) ? current[key].filter((value) => value !== item) : [...current[key], item],
    }));
  }

  function updateExercise(index: number, key: keyof ProgramExercise, value: string | number | string[]) {
    setProgram((current) => current ? {
      ...current,
      exercises: current.exercises.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item),
    } : current);
  }

  function addExercise(exercise: ProgramExercise = blankExercise) {
    setProgram((current) => current ? { ...current, exercises: [...current.exercises, { ...exercise }] } : current);
  }

  function removeExercise(index: number) {
    setProgram((current) => current ? { ...current, exercises: current.exercises.filter((_, itemIndex) => itemIndex !== index) } : current);
  }

  async function generate(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    try {
      const { data } = await api.post('/program/generate', setup);
      setProgram(data.program);
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  async function complete() {
    if (!program) return;
    try {
      const { data } = await api.post('/program/complete', program);
      setMessage(`Program complete. +${data.workout.xpEarned} XP and readiness is now ${data.readiness.score}%.`);
      setProgram(undefined);
      setExerciseSearch('');
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Progressive Workout Programming</p>
          <h1>Workout Programmer</h1>
        </div>
        {program && <span className="score-chip"><Sparkles size={16} /> {xpPreview} XP preview</span>}
      </div>

      <div className="grid-2">
        <Panel title="Build Your Session">
          <form className="stack" onSubmit={generate}>
            {message && <p className={message.includes('complete') ? 'success' : 'error'}>{message}</p>}
            <div className="form-grid">
              <div>
                <label>Training Goal</label>
                <select value={setup.goal} onChange={(e) => setSetup({ ...setup, goal: e.target.value })}>
                  {goals.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
              </div>
              <div>
                <label>Minutes Available</label>
                <input type="number" min={20} max={120} value={setup.minutes} onChange={(e) => setSetup({ ...setup, minutes: +e.target.value })} />
              </div>
              <div>
                <label>Base Type</label>
                <select value={setup.type} onChange={(e) => setSetup({ ...setup, type: e.target.value })}>
                  {['football', 'running', 'gym', 'cycling', 'swimming', 'other'].map((item) => <option key={item}>{item}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label>Body Parts Or Focus Areas</label>
              <div className="choice-row equipment-grid">
                {bodyPartOptions.map((item) => (
                  <button type="button" className={`choice ${setup.bodyParts.includes(item) ? 'selected' : ''}`} key={item} onClick={() => toggleList('bodyParts', item)}>
                    <span>{item}</span>
                    <small>{setup.bodyParts.includes(item) ? 'targeted' : 'tap to target'}</small>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label>Equipment You Have</label>
              <div className="choice-row equipment-grid">
                {equipmentOptions.map((item) => (
                  <button type="button" className={`choice ${setup.equipment.includes(item) ? 'selected' : ''}`} key={item} onClick={() => toggleList('equipment', item)}>
                    <span>{item}</span>
                    <small>{setup.equipment.includes(item) ? 'selected' : 'tap to add'}</small>
                  </button>
                ))}
              </div>
            </div>
            <button><Dumbbell size={18} /> Generate Workout</button>
          </form>
        </Panel>

        <Panel title="How Custom Workouts Work">
          <p className="muted">Pick the body parts you want to train, then MatchFit recommends exercises that fit your equipment. You can add the recommendations, remove anything, or write a completely custom exercise.</p>
          <p className="muted">Sets, reps, weight, rest, equipment, coaching notes, and target body parts all stay editable before you complete the workout.</p>
        </Panel>
      </div>

      <Panel title="Programmed Session">
        {program ? (
          <div className="stack">
            <p className="lead">{program.duration} min {program.intensity} {program.type}</p>
            {!!program.targetBodyParts?.length && <p className="muted">Targeting: {program.targetBodyParts.join(', ')}</p>}

            {!!program.recommended?.length && (
              <div>
                <div className="between">
                  <h3>Searchable Exercise Picker</h3>
                  <span className="score-chip">{recommendedExercises.length} matches</span>
                </div>
                <input value={exerciseSearch} onChange={(e) => setExerciseSearch(e.target.value)} placeholder="Search by exercise, equipment, or body part" />
                <div className="choice-row equipment-grid">
                  {recommendedExercises.map((item) => (
                    <button type="button" className="choice" key={item.name} onClick={() => addExercise(item)}>
                      <span>{item.name}</span>
                      <small>{item.bodyParts.join(', ')}</small>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="exercise-list">
              {program.exercises.map((item, index) => (
                <div className="exercise-card" key={`${item.name}-${index}`}>
                  <div className="exercise-title-row">
                    <input value={item.name} onChange={(e) => updateExercise(index, 'name', e.target.value)} />
                    <button type="button" className="ghost-button" onClick={() => removeExercise(index)}><Trash2 size={16} /> Remove</button>
                  </div>
                  <textarea value={item.instruction} onChange={(e) => updateExercise(index, 'instruction', e.target.value)} />
                  <textarea value={item.progression || ''} onChange={(e) => updateExercise(index, 'progression', e.target.value)} />
                  <div className="exercise-fields">
                    <label>Sets<input type="number" min={1} max={10} value={item.sets} onChange={(e) => updateExercise(index, 'sets', +e.target.value)} /></label>
                    <label>Reps<input value={item.reps} onChange={(e) => updateExercise(index, 'reps', e.target.value)} /></label>
                    <label>Weight kg<input type="number" min={0} step={0.5} value={item.weightKg} onChange={(e) => updateExercise(index, 'weightKg', +e.target.value)} /></label>
                    <label>Rest sec<input type="number" min={0} step={15} value={item.restSeconds} onChange={(e) => updateExercise(index, 'restSeconds', +e.target.value)} /></label>
                    <label>Equipment<input value={item.equipment} onChange={(e) => updateExercise(index, 'equipment', e.target.value)} /></label>
                    <label>Body parts<input value={item.bodyParts.join(', ')} onChange={(e) => updateExercise(index, 'bodyParts', e.target.value.split(',').map((part) => part.trim()).filter(Boolean))} /></label>
                  </div>
                </div>
              ))}
            </div>

            <div className="button-row">
              <button type="button" className="secondary-button" onClick={() => addExercise()}><Plus size={18} /> Add Custom Exercise</button>
              <button onClick={complete}>Complete Programmed Workout</button>
            </div>
            <p className="muted">Completing this session counts for objectives because it came from the programme builder.</p>
          </div>
        ) : (
          <p className="muted">Choose your body parts, equipment, goal, and time. MatchFit will build a specific editable session with set, rep, weight, rest, and coaching details.</p>
        )}
      </Panel>
    </div>
  );
}
