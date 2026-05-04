import { useState } from ''react'';
import { useNavigate } from ''react-router-dom'';
import { ChevronRight, ChevronLeft, Check } from ''lucide-react'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';

const POSITIONS = [''GK'', ''CB'', ''FB/WB'', ''CDM'', ''CM'', ''CAM'', ''Winger'', ''ST'', ''Any''];
const FOOTBALL_LEVELS = [
  { value: ''complete_beginner'', label: ''Complete Beginner'' },
  { value: ''casual'', label: ''Casual'' },
  { value: ''5-a-side'', label: ''5-a-side'' },
  { value: ''sunday_league'', label: ''Sunday League'' },
  { value: ''club'', label: ''Club Level'' },
  { value: ''competitive'', label: ''Competitive'' },
];
const GOALS = [
  { value: ''get_match_fit'', label: ''Get Match Fit'' },
  { value: ''improve_stamina'', label: ''Improve Stamina'' },
  { value: ''improve_speed'', label: ''Improve Speed'' },
  { value: ''lose_weight'', label: ''Lose Weight'' },
  { value: ''gain_muscle'', label: ''Gain Muscle'' },
  { value: ''return_from_injury'', label: ''Return from Injury'' },
  { value: ''general_health'', label: ''General Health'' },
  { value: ''compete_with_friends'', label: ''Compete with Friends'' },
  { value: ''improve_football_skills'', label: ''Improve Football Skills'' },
];
const EQUIPMENT_OPTIONS = [
  ''none/bodyweight only'', ''walking pad'', ''treadmill'', ''exercise bike'', ''rowing machine'',
  ''cross trainer'', ''jump rope'', ''dumbbells'', ''kettlebells'', ''barbell'', ''squat rack'',
  ''bench'', ''resistance bands'', ''pull-up bar'', ''cable machine'', ''full gym access'',
  ''yoga mat'', ''foam roller'', ''massage gun'', ''cones'', ''agility ladder'', ''hurdles'',
  ''football'', ''rebound board'', ''goal/net'', ''weighted vest'', ''medicine ball'',
  ''heart rate monitor'', ''GPS tracker'',
];
const DIETARY_OPTIONS = [
  ''no preference'', ''high protein'', ''calorie deficit'', ''calorie surplus'', ''maintenance'',
  ''gluten-free'', ''dairy-free'', ''vegetarian'', ''vegan'', ''pescatarian'', ''halal'', ''kosher'',
  ''low sugar'', ''anti-inflammatory'', ''budget meals'', ''meal prep focused'', ''quick meals'',
];
const SUPPLEMENT_OPTIONS = [
  ''Vitamin D'', ''Magnesium Glycinate'', ''Omega-3'', ''Creatine'', ''Electrolytes'',
  ''Multivitamin'', ''Protein Powder'', ''Vitamin C'', ''Zinc'', ''Iron'',
];
const SUPPLEMENT_TIMINGS = [''morning'', ''lunchtime'', ''afternoon'', ''evening'', ''bedtime''];
const DAYS = [''Monday'', ''Tuesday'', ''Wednesday'', ''Thursday'', ''Friday'', ''Saturday'', ''Sunday''];

interface FormData {
  displayName: string;
  dateOfBirth: string;
  gender: string;
  heightCm: string;
  weightKg: string;
  country: string;
  timezone: string;
  units: ''metric'' | ''imperial'';
  mainGoal: string;
  targetDate: string;
  matchDate: string;
  fitnessLevel: number;
  footballLevel: string;
  position: string;
  fatigueSensitive: boolean;
  sleepDifficulty: boolean;
  injuryConcerns: string;
  energyBaseline: number;
  stressBaseline: number;
  preferredWorkoutDays: string[];
  preferredWorkoutTime: string;
  maxWorkoutDuration: number;
  preferredRestDays: string[];
  equipment: string[];
  dietaryPreferences: string[];
  supplements: { name: string; timing: string }[];
}

const STEPS = [
  ''About You'', ''Your Goal'', ''Health & Recovery'',
  ''Schedule'', ''Equipment'', ''Diet & Supplements''
];

function ToggleChip({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border ${
        selected
          ? ''bg-electric-500/20 border-electric-500 text-electric-400''
          : ''bg-pitch-700 border-pitch-600 text-gray-400 hover:border-gray-500''
      }`}
    >
      {label}
    </button>
  );
}

function StarRating({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  return (
    <div>
      <label className="label mb-2 block">{label}</label>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map(n => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            className={`w-10 h-10 rounded-lg font-display font-bold text-lg transition-all ${
              n <= value ? ''bg-electric-500 text-white'' : ''bg-pitch-700 text-gray-500''
            }`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { fetchMe } = useAuthStore();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('''');

  const [form, setForm] = useState<FormData>({
    displayName: '''',
    dateOfBirth: '''',
    gender: '''',
    heightCm: '''',
    weightKg: '''',
    country: '''',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    units: ''metric'',
    mainGoal: ''get_match_fit'',
    targetDate: '''',
    matchDate: '''',
    fitnessLevel: 3,
    footballLevel: ''casual'',
    position: ''Any'',
    fatigueSensitive: false,
    sleepDifficulty: false,
    injuryConcerns: '''',
    energyBaseline: 3,
    stressBaseline: 2,
    preferredWorkoutDays: [''Monday'', ''Wednesday'', ''Friday''],
    preferredWorkoutTime: ''morning'',
    maxWorkoutDuration: 45,
    preferredRestDays: [''Sunday''],
    equipment: [],
    dietaryPreferences: [''no preference''],
    supplements: [],
  });

  const update = (key: keyof FormData, val: unknown) => setForm(f => ({ ...f, [key]: val }));

  const toggleArr = (key: keyof FormData, val: string) => {
    const arr = form[key] as string[];
    update(key, arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val]);
  };

  const addSupplement = (name: string) => {
    if (!form.supplements.find(s => s.name === name)) {
      update(''supplements'', [...form.supplements, { name, timing: ''morning'' }]);
    }
  };

  const updateSupplementTiming = (name: string, timing: string) => {
    update(''supplements'', form.supplements.map(s => s.name === name ? { ...s, timing } : s));
  };

  const removeSupplement = (name: string) => {
    update(''supplements'', form.supplements.filter(s => s.name !== name));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('''');
    try {
      await api.post(''/onboarding'', {
        ...form,
        heightCm: form.heightCm ? parseFloat(form.heightCm) : undefined,
        weightKg: form.weightKg ? parseFloat(form.weightKg) : undefined,
      });
      await fetchMe();
      navigate(''/dashboard'');
    } catch (err: any) {
      setError(err.response?.data?.error || ''Something went wrong'');
    } finally {
      setLoading(false);
    }
  };

  const canContinue = () => {
    if (step === 0) return form.displayName.trim().length > 0;
    return true;
  };

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col max-w-md mx-auto">
      {/* Header */}
      <div className="px-4 pt-8 pb-4">
        <div className="font-display font-black text-2xl text-white mb-1">
          MATCH<span className="text-electric-400">FIT</span> PRO
        </div>
        <p className="text-gray-400 text-sm">Let''s set up your profile</p>
      </div>

      {/* Progress */}
      <div className="px-4 mb-6">
        <div className="flex items-center gap-1.5 mb-2">
          {STEPS.map((s, i) => (
            <div key={s} className={`flex-1 h-1 rounded-full transition-all ${i <= step ? ''bg-electric-500'' : ''bg-pitch-700''}`} />
          ))}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 font-medium">{STEPS[step]}</span>
          <span className="text-xs text-gray-600">{step + 1} / {STEPS.length}</span>
        </div>
      </div>

      {/* Steps */}
      <div className="flex-1 px-4 pb-4 overflow-y-auto">
        {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm mb-4">{error}</div>}

        {/* Step 0: About You */}
        {step === 0 && (
          <div className="space-y-4">
            <div>
              <label className="label mb-1.5 block">Display Name *</label>
              <input className="input-field" placeholder="How should we call you?" value={form.displayName} onChange={e => update(''displayName'', e.target.value)} />
            </div>
            <div>
              <label className="label mb-1.5 block">Date of Birth</label>
              <input type="date" className="input-field" value={form.dateOfBirth} onChange={e => update(''dateOfBirth'', e.target.value)} />
            </div>
            <div>
              <label className="label mb-1.5 block">Gender (optional)</label>
              <div className="flex gap-2 flex-wrap">
                {[''Male'', ''Female'', ''Non-binary'', ''Prefer not to say''].map(g => (
                  <ToggleChip key={g} label={g} selected={form.gender === g} onClick={() => update(''gender'', g)} />
                ))}
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="label mb-1.5 block">Height (cm)</label>
                <input type="number" className="input-field" placeholder="178" value={form.heightCm} onChange={e => update(''heightCm'', e.target.value)} />
              </div>
              <div className="flex-1">
                <label className="label mb-1.5 block">Weight (kg)</label>
                <input type="number" className="input-field" placeholder="75" value={form.weightKg} onChange={e => update(''weightKg'', e.target.value)} />
              </div>
            </div>
            <div>
              <label className="label mb-1.5 block">Country</label>
              <input className="input-field" placeholder="United Kingdom" value={form.country} onChange={e => update(''country'', e.target.value)} />
            </div>
          </div>
        )}

        {/* Step 1: Your Goal */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <label className="label mb-2 block">Main Goal</label>
              <div className="grid grid-cols-1 gap-2">
                {GOALS.map(g => (
                  <button
                    key={g.value}
                    type="button"
                    onClick={() => update(''mainGoal'', g.value)}
                    className={`w-full text-left px-4 py-3 rounded-xl border font-medium text-sm transition-all ${
                      form.mainGoal === g.value
                        ? ''bg-electric-500/20 border-electric-500 text-electric-400''
                        : ''bg-pitch-700 border-pitch-600 text-gray-300 hover:border-gray-500''
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-1.5 block">Target Date (optional)</label>
              <input type="date" className="input-field" value={form.targetDate} onChange={e => update(''targetDate'', e.target.value)} />
            </div>
            <div>
              <label className="label mb-1.5 block">Match Date (if applicable)</label>
              <input type="date" className="input-field" value={form.matchDate} onChange={e => update(''matchDate'', e.target.value)} />
            </div>
            <StarRating value={form.fitnessLevel} onChange={v => update(''fitnessLevel'', v)} label="Current Fitness Level (1-5)" />
            <div>
              <label className="label mb-2 block">Football Level</label>
              <div className="grid grid-cols-2 gap-2">
                {FOOTBALL_LEVELS.map(l => (
                  <ToggleChip key={l.value} label={l.label} selected={form.footballLevel === l.value} onClick={() => update(''footballLevel'', l.value)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Preferred Position</label>
              <div className="flex flex-wrap gap-2">
                {POSITIONS.map(p => (
                  <ToggleChip key={p} label={p} selected={form.position === p} onClick={() => update(''position'', p)} />
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Health & Recovery */}
        {step === 2 && (
          <div className="space-y-5">
            <StarRating value={form.energyBaseline} onChange={v => update(''energyBaseline'', v)} label="Typical Energy Level (1=Low, 5=High)" />
            <StarRating value={form.stressBaseline} onChange={v => update(''stressBaseline'', v)} label="Typical Stress Level (1=Low, 5=High)" />
            <div>
              <label className="label mb-2 block">Fatigue Sensitive?</label>
              <p className="text-xs text-gray-500 mb-2">Do you crash hard after intense effort or poor sleep?</p>
              <div className="flex gap-3">
                <ToggleChip label="Yes" selected={form.fatigueSensitive} onClick={() => update(''fatigueSensitive'', true)} />
                <ToggleChip label="No" selected={!form.fatigueSensitive} onClick={() => update(''fatigueSensitive'', false)} />
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Sleep Difficulties?</label>
              <div className="flex gap-3">
                <ToggleChip label="Yes" selected={form.sleepDifficulty} onClick={() => update(''sleepDifficulty'', true)} />
                <ToggleChip label="No" selected={!form.sleepDifficulty} onClick={() => update(''sleepDifficulty'', false)} />
              </div>
            </div>
            <div>
              <label className="label mb-1.5 block">Injury Concerns (optional)</label>
              <textarea
                className="input-field resize-none"
                rows={3}
                placeholder="e.g. left knee, lower back..."
                value={form.injuryConcerns}
                onChange={e => update(''injuryConcerns'', e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Step 3: Schedule */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <label className="label mb-2 block">Preferred Workout Days</label>
              <div className="flex flex-wrap gap-2">
                {DAYS.map(d => (
                  <ToggleChip key={d} label={d.slice(0, 3)} selected={form.preferredWorkoutDays.includes(d)} onClick={() => toggleArr(''preferredWorkoutDays'', d)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Preferred Rest Days</label>
              <div className="flex flex-wrap gap-2">
                {DAYS.map(d => (
                  <ToggleChip key={d} label={d.slice(0, 3)} selected={form.preferredRestDays.includes(d)} onClick={() => toggleArr(''preferredRestDays'', d)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Preferred Workout Time</label>
              <div className="flex flex-wrap gap-2">
                {[''morning'', ''lunchtime'', ''afternoon'', ''evening''].map(t => (
                  <ToggleChip key={t} label={t.charAt(0).toUpperCase() + t.slice(1)} selected={form.preferredWorkoutTime === t} onClick={() => update(''preferredWorkoutTime'', t)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Max Workout Duration: {form.maxWorkoutDuration} mins</label>
              <input type="range" min={10} max={120} step={5} value={form.maxWorkoutDuration} onChange={e => update(''maxWorkoutDuration'', Number(e.target.value))} className="w-full accent-electric-500" />
              <div className="flex justify-between text-xs text-gray-600 mt-1">
                <span>10 min</span><span>120 min</span>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Equipment */}
        {step === 4 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-400">Select all equipment you have access to:</p>
            <div className="flex flex-wrap gap-2">
              {EQUIPMENT_OPTIONS.map(e => (
                <ToggleChip key={e} label={e} selected={form.equipment.includes(e)} onClick={() => toggleArr(''equipment'', e)} />
              ))}
            </div>
          </div>
        )}

        {/* Step 5: Diet & Supplements */}
        {step === 5 && (
          <div className="space-y-5">
            <div>
              <label className="label mb-2 block">Dietary Preferences</label>
              <div className="flex flex-wrap gap-2">
                {DIETARY_OPTIONS.map(d => (
                  <ToggleChip key={d} label={d} selected={form.dietaryPreferences.includes(d)} onClick={() => toggleArr(''dietaryPreferences'', d)} />
                ))}
              </div>
            </div>
            <div>
              <label className="label mb-2 block">Supplements & Reminders</label>
              <div className="flex flex-wrap gap-2 mb-3">
                {SUPPLEMENT_OPTIONS.map(s => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => form.supplements.find(x => x.name === s) ? removeSupplement(s) : addSupplement(s)}
                    className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                      form.supplements.find(x => x.name === s)
                        ? ''bg-electric-500/20 border-electric-500 text-electric-400''
                        : ''bg-pitch-700 border-pitch-600 text-gray-400''
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
              {form.supplements.length > 0 && (
                <div className="space-y-2">
                  {form.supplements.map(s => (
                    <div key={s.name} className="card flex items-center gap-3">
                      <div className="flex-1 text-sm text-white font-medium">{s.name}</div>
                      <select
                        className="bg-pitch-700 border border-pitch-600 text-gray-300 text-xs rounded-lg px-2 py-1"
                        value={s.timing}
                        onChange={e => updateSupplementTiming(s.name, e.target.value)}
                      >
                        {SUPPLEMENT_TIMINGS.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-gray-600 mt-3">âš ï¸ This app does not provide medical advice. Always consult a professional for medication decisions.</p>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="px-4 py-4 border-t border-pitch-700 flex gap-3">
        {step > 0 && (
          <button type="button" onClick={() => setStep(s => s - 1)} className="btn-secondary flex items-center gap-1 px-4">
            <ChevronLeft size={16} /> Back
          </button>
        )}
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep(s => s + 1)}
            disabled={!canContinue()}
            className="btn-primary flex-1 flex items-center justify-center gap-1 disabled:opacity-40"
          >
            Continue <ChevronRight size={16} />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="btn-primary flex-1 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? ''Setting up...'' : <><Check size={16} /> Let''s Go!</>}
          </button>
        )}
      </div>
    </div>
  );
}
