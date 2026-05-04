mport { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dumbbell, Clock, Zap, ChevronRight, CheckCircle } from 'lucide-react';
import api from '../lib/api';

const DURATIONS = [5, 10, 15, 20, 30, 45, 60];
const INTENSITIES = [
  { value: 'recovery', label: 'Recovery', desc: 'Very gentle, mobility focus', color: 'text-blue-400', bg: 'bg-blue-400/10 border-blue-400/30' },
  { value: 'easy', label: 'Easy', desc: 'Light effort, building base', color: 'text-emerald-400', bg: 'bg-emerald-400/10 border-emerald-400/30' },
  { value: 'moderate', label: 'Moderate', desc: 'Challenging but sustainable', color: 'text-yellow-400', bg: 'bg-yellow-400/10 border-yellow-400/30' },
  { value: 'hard', label: 'Hard', desc: 'High intensity, max effort', color: 'text-red-400', bg: 'bg-red-400/10 border-red-400/30' },
];
const GOALS = [
  { value: 'stamina', label: 'Stamina', icon: '🏃' },
  { value: 'strength', label: 'Strength', icon: '💪' },
  { value: 'speed', label: 'Speed', icon: '⚡' },
  { value: 'agility', label: 'Agility', icon: '🏃‍♂️' },
  { value: 'mobility', label: 'Mobility', icon: '🧘' },
  { value: 'recovery', label: 'Recovery', icon: '😴' },
  { value: 'match_simulation', label: 'Match Sim', icon: '⚽' },
  { value: 'football_skill', label: 'Football Skills', icon: '🎯' },
];
const ENERGY_STATES = [
  { value: 'green', label: '🟢 Green – Feeling great', desc: 'Full sessions allowed' },
  { value: 'yellow', label: '🟡 Yellow – Moderate energy', desc: 'Easy/moderate only' },
  { value: 'red', label: '🔴 Red – Low / tired', desc: 'Recovery only' },
];

interface GeneratedWorkout {
  id: string;
  title: string;
  category: string;
  difficulty: string;
  durationMins: number;
  xpReward: number;
  estimatedFatigue: number;
  warmup: { name: string; duration?: string; sets?: string; reps?: string; notes?: string }[];
  mainSection: { name: string; sets?: string; reps?: string; duration?: string; rest?: string; intensity?: string; notes?: string }[];
  cooldown: { name: string; duration?: string }[];
  statsImproved: string[];
}

function ExerciseList({ exercises, title }: { exercises: GeneratedWorkout['warmup']; title: string }) {
  return (
    <div className="card">
      <h3 className="label mb-3">{title}</h3>
      <div className="space-y-2">
        {exercises.map((ex, i) => (
          <div key={i} className="flex items-start gap-3 py-2 border-b border-pitch-700 last:border-0">
            <div className="w-6 h-6 rounded-full bg-electric-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-electric-400 text-xs font-bold">{i + 1}</span>
            </div>
            <div className="flex-1">
              <div className="text-white font-medium text-sm">{ex.name}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                {[
                  ex.sets && `${ex.sets} sets`,
                  ex.reps && `${ex.reps} reps`,
                  ex.duration && ex.duration,
                  ex.rest && `Rest: ${ex.rest}`,
                  ex.intensity && ex.intensity,
                  ex.notes && ex.notes,
                ].filter(Boolean).join(' · ')}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function WorkoutPlannerPage() {
  const [duration, setDuration] = useState(30);
  const [intensity, setIntensity] = useState('moderate');
  const [goal, setGoal] = useState('stamina');
  const [energyState, setEnergyState] = useState<'green' | 'yellow' | 'red'>('green');
  const [generating, setGenerating] = useState(false);
  const [workout, setWorkout] = useState<GeneratedWorkout | null>(null);
  const [completing, setCompleting] = useState(false);
  const [rpe, setRpe] = useState(7);
  const [completed, setCompleted] = useState(false);
  const navigate = useNavigate();

  // Auto-downgrade intensity on red/yellow
  const effectiveIntensity = energyState === 'red' ? 'recovery' : energyState === 'yellow' && intensity === 'hard' ? 'moderate' : intensity;

  const generate = async () => {
    setGenerating(true);
    setWorkout(null);
    setCompleted(false);
    try {
      const { data } = await api.post('/workouts/generate', {
        durationMins: duration,
        intensity: effectiveIntensity,
        goal: energyState === 'red' ? 'recovery' : goal,
        equipment: [],
        energyState,
      });
      setWorkout(data);
    } finally {
      setGenerating(false);
    }
  };

  const complete = async () => {
    if (!workout) return;
    setCompleting(true);
    try {
      await api.post('/workouts/complete', { generatedWorkoutId: workout.id, rpe });
      setCompleted(true);
    } finally {
      setCompleting(false);
    }
  };

  const fatigueLabel = ['', 'Very Low', 'Low', 'Moderate', 'High', 'Very High'];

  return (
    <div className="px-4 py-4 space-y-5 pb-8">
      <h1 className="section-title">Workout Planner</h1>

      {!workout ? (
        <>
          {/* Energy State */}
          <div className="card">
            <h3 className="label mb-3">How are you feeling?</h3>
            <div className="space-y-2">
              {ENERGY_STATES.map(e => (
                <button
                  key={e.value}
                  onClick={() => setEnergyState(e.value as 'green' | 'yellow' | 'red')}
                  className={`w-full text-left px-4 py-3 rounded-xl border transition-all ${energyState === e.value ? 'bg-electric-500/10 border-electric-500' : 'bg-pitch-700 border-pitch-600'}`}
                >
                  <div className="font-medium text-sm text-white">{e.label}</div>
                  <div className="text-xs text-gray-500">{e.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {energyState !== 'red' && (
            <>
              {/* Duration */}
              <div className="card">
                <h3 className="label mb-3">Duration</h3>
                <div className="flex gap-2 flex-wrap">
                  {DURATIONS.map(d => (
                    <button key={d} onClick={() => setDuration(d)} className={`px-4 py-2 rounded-lg font-display font-bold text-sm transition-all border ${duration === d ? 'bg-electric-500/20 border-electric-500 text-electric-400' : 'bg-pitch-700 border-pitch-600 text-gray-300'}`}>
                      {d}m
                    </button>
                  ))}
                </div>
              </div>

              {/* Intensity */}
              <div className="card">
                <h3 className="label mb-3">Intensity {energyState === 'yellow' && intensity === 'hard' ? <span className="text-yellow-400 text-xs">(downgraded to Moderate)</span> : ''}</h3>
                <div className="grid grid-cols-2 gap-2">
                  {INTENSITIES.map(i => (
                    <button key={i.value} onClick={() => setIntensity(i.value)} className={`text-left px-3 py-2.5 rounded-xl border transition-all ${intensity === i.value ? i.bg : 'bg-pitch-700 border-pitch-600'}`}>
                      <div className={`font-semibold text-sm ${intensity === i.value ? i.color : 'text-gray-300'}`}>{i.label}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{i.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Goal */}
              <div className="card">
                <h3 className="label mb-3">Session Goal</h3>
                <div className="grid grid-cols-2 gap-2">
                  {GOALS.map(g => (
                    <button key={g.value} onClick={() => setGoal(g.value)} className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border transition-all ${goal === g.value ? 'bg-electric-500/20 border-electric-500' : 'bg-pitch-700 border-pitch-600'}`}>
                      <span className="text-lg">{g.icon}</span>
                      <span className={`text-sm font-medium ${goal === g.value ? 'text-electric-400' : 'text-gray-300'}`}>{g.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          <button onClick={generate} disabled={generating} className="btn-primary w-full py-4 font-display font-bold uppercase tracking-wide text-base flex items-center justify-center gap-2 disabled:opacity-50">
            <Dumbbell size={20} />
            {generating ? 'Generating...' : 'Generate Workout'}
          </button>
        </>
      ) : (
        <>
          {/* Workout display */}
          {completed ? (
            <div className="card text-center py-8">
              <CheckCircle size={48} className="text-emerald-400 mx-auto mb-3" />
              <div className="font-display font-black text-2xl text-white mb-1">WORKOUT COMPLETE!</div>
              <div className="text-gray-400 mb-4">XP awarded and card stats updated</div>
              <div className="flex gap-3 justify-center">
                <button onClick={() => { setWorkout(null); setCompleted(false); }} className="btn-secondary">New Workout</button>
                <button onClick={() => navigate('/player-card')} className="btn-primary">View Card</button>
              </div>
            </div>
          ) : (
            <>
              <div className="card bg-gradient-to-r from-electric-600/10 to-purple-600/10 border-electric-500/30">
                <div className="flex items-start justify-between mb-2">
                  <h2 className="font-display font-bold text-white text-lg">{workout.title}</h2>
                  <button onClick={() => setWorkout(null)} className="text-xs text-gray-500 hover:text-white">Change</button>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-400">
                  <span className="flex items-center gap-1"><Clock size={14} /> {workout.durationMins} mins</span>
                  <span className="flex items-center gap-1 text-yellow-400"><Zap size={14} /> {workout.xpReward} XP</span>
                  <span>Fatigue: {fatigueLabel[workout.estimatedFatigue]}</span>
                </div>
                {workout.statsImproved.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {workout.statsImproved.map(s => (
                      <span key={s} className="px-2 py-0.5 bg-electric-500/10 border border-electric-500/30 rounded text-electric-400 text-xs">+{s}</span>
                    ))}
                  </div>
                )}
              </div>

              <ExerciseList exercises={workout.warmup} title="🔥 Warm-Up" />
              <ExerciseList exercises={workout.mainSection} title="💪 Main Session" />
              <ExerciseList exercises={workout.cooldown} title="❄️ Cool-Down" />

              {/* RPE slider */}
              <div className="card">
                <h3 className="label mb-3">Rate of Perceived Effort (RPE): {rpe}/10</h3>
                <input type="range" min={1} max={10} value={rpe} onChange={e => setRpe(Number(e.target.value))} className="w-full accent-electric-500" />
                <div className="flex justify-between text-xs text-gray-600 mt-1">
                  <span>Easy (1)</span><span>Max effort (10)</span>
                </div>
              </div>

              <button onClick={complete} disabled={completing} className="btn-gold w-full py-4 font-display font-bold uppercase tracking-wide text-base flex items-center justify-center gap-2 disabled:opacity-50">
                <Zap size={20} />
                {completing ? 'Submitting...' : `Submit for ${workout.xpReward} XP`}
              </button>
            </>
          )}
        </>
      )}
    </div>
  );
}
