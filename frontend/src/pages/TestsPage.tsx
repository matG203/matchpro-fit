import { useEffect, useState } from ''react'';
import { FlaskConical, TrendingUp, Plus, Trophy } from ''lucide-react'';
import api from ''../lib/api'';

interface TestResult { id: string; testType: string; value: number; unit?: string; notes?: string; testedAt: string; }

const TEST_TYPES = [
  { value: ''20m_sprint'', label: ''20m Sprint'', unit: ''seconds'', desc: ''Time your 20m sprint'', lower_is_better: true },
  { value: ''5_10_5_shuttle'', label: ''5-10-5 Shuttle'', unit: ''seconds'', desc: ''Agility shuttle run'', lower_is_better: true },
  { value: ''cone_drill'', label: ''Cone Drill'', unit: ''seconds'', desc: ''Agility cone course'', lower_is_better: true },
  { value: ''plank'', label: ''Plank Hold'', unit: ''seconds'', desc: ''Core endurance hold'', lower_is_better: false },
  { value: ''push_ups'', label: ''Push-Ups'', unit: ''reps'', desc: ''Max reps in 60 seconds'', lower_is_better: false },
  { value: ''squats'', label: ''Bodyweight Squats'', unit: ''reps'', desc: ''Max reps in 60 seconds'', lower_is_better: false },
  { value: ''wall_passing'', label: ''Wall Passing'', unit: ''passes/min'', desc: ''First touch passes per minute'', lower_is_better: false },
  { value: ''shooting'', label: ''Shooting Practice'', unit: ''goals/10'', desc: ''Goals out of 10 shots'', lower_is_better: false },
  { value: ''beep_test'', label: ''Beep Test Level'', unit: ''level'', desc: ''Estimated VO2max level'', lower_is_better: false },
  { value: ''rower_trial'', label: ''Rower Time Trial'', unit: ''seconds'', desc: ''2000m row time'', lower_is_better: true },
];

export default function TestsPage() {
  const [history, setHistory] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTest, setSelectedTest] = useState('''');
  const [value, setValue] = useState('''');
  const [notes, setNotes] = useState('''');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ xpAwarded: number; isImprovement: boolean } | null>(null);

  const load = () => api.get(''/tests/history'').then(r => { setHistory(r.data); setLoading(false); });
  useEffect(() => { load(); }, []);

  const submit = async () => {
    if (!selectedTest || !value) return;
    setSubmitting(true); setResult(null);
    const test = TEST_TYPES.find(t => t.value === selectedTest)!;
    try {
      const { data } = await api.post(''/tests'', { testType: selectedTest, value: Number(value), unit: test.unit, notes });
      setResult(data);
      setValue(''''); setNotes('''');
      load();
    } finally { setSubmitting(false); }
  };

  // Group history by test type, get latest per type
  const latestByType = TEST_TYPES.map(t => ({
    ...t,
    latest: history.filter(h => h.testType === t.value).sort((a, b) => new Date(b.testedAt).getTime() - new Date(a.testedAt).getTime())[0],
    history: history.filter(h => h.testType === t.value).slice(0, 5),
  }));

  const selectedTestInfo = TEST_TYPES.find(t => t.value === selectedTest);

  return (
    <div className="px-4 py-4 space-y-5 pb-8">
      <div className="flex items-center gap-3">
        <FlaskConical size={24} className="text-electric-400" />
        <h1 className="section-title">Fitness Tests</h1>
      </div>

      {/* Log a test */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Plus size={14} /> Log a Test</h3>

        {result && (
          <div className={`mb-4 p-3 rounded-xl border ${result.isImprovement ? ''bg-yellow-500/10 border-yellow-500/30'' : ''bg-emerald-500/10 border-emerald-500/30''}`}>
            <div className="flex items-center gap-2">
              {result.isImprovement && <Trophy size={16} className="text-yellow-400" />}
              <span className={`font-semibold text-sm ${result.isImprovement ? ''text-yellow-400'' : ''text-emerald-400''}`}>
                {result.isImprovement ? ''ðŸ† New Personal Best!'' : ''Test logged!''}
              </span>
            </div>
            <div className="text-xs text-gray-400 mt-1">+{result.xpAwarded} XP awarded</div>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="label mb-2 block">Select Test</label>
            <select className="input-field" value={selectedTest} onChange={e => setSelectedTest(e.target.value)}>
              <option value="">Choose a test...</option>
              {TEST_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>

          {selectedTestInfo && (
            <div className="text-xs text-gray-500 bg-pitch-700 px-3 py-2 rounded-lg">
              {selectedTestInfo.desc} Â· Measured in {selectedTestInfo.unit}
              {selectedTestInfo.lower_is_better ? '' Â· Lower is better â†“'' : '' Â· Higher is better â†‘''}
            </div>
          )}

          <div>
            <label className="label mb-1.5 block">Result {selectedTestInfo ? `(${selectedTestInfo.unit})` : ''''}</label>
            <input type="number" step="0.01" className="input-field" placeholder="Enter your result..." value={value} onChange={e => setValue(e.target.value)} />
          </div>

          <div>
            <label className="label mb-1.5 block">Notes (optional)</label>
            <input className="input-field" placeholder="Conditions, how you felt..." value={notes} onChange={e => setNotes(e.target.value)} />
          </div>

          <button onClick={submit} disabled={submitting || !selectedTest || !value} className="btn-primary w-full disabled:opacity-50">
            {submitting ? ''Logging...'' : ''Log Test Result''}
          </button>
        </div>
      </div>

      {/* Personal bests */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><TrendingUp size={14} /> Personal Bests</h3>
        {loading ? (
          <div className="text-gray-500 text-sm text-center py-4">Loading...</div>
        ) : (
          <div className="space-y-3">
            {latestByType.filter(t => t.latest).map(t => (
              <div key={t.value} className="flex items-center gap-3 py-2 border-b border-pitch-700 last:border-0">
                <div className="flex-1">
                  <div className="text-white font-medium text-sm">{t.label}</div>
                  <div className="text-xs text-gray-500">
                    {new Date(t.latest!.testedAt).toLocaleDateString(''en-GB'')}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-display font-bold text-electric-400">
                    {t.latest!.value} <span className="text-xs text-gray-500">{t.unit}</span>
                  </div>
                </div>
              </div>
            ))}
            {latestByType.filter(t => t.latest).length === 0 && (
              <p className="text-gray-500 text-sm text-center py-2">No tests logged yet. Log your first test above!</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
