mport { useEffect, useState } from 'react';
import { Heart, TrendingUp, Plus } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import api from '../lib/api';
import { format } from 'date-fns';

interface DailySummary {
  date: string; steps?: number; sleepHours?: number; restingHr?: number;
  weightKg?: number; energyLevel?: number; activeMinutes?: number;
}

const CHARTS = [
  { key: 'steps', label: 'Steps', color: '#0ea5e9', unit: '' },
  { key: 'sleepHours', label: 'Sleep', color: '#8b5cf6', unit: 'h' },
  { key: 'restingHr', label: 'Resting HR', color: '#ef4444', unit: 'bpm' },
  { key: 'weightKg', label: 'Weight', color: '#f59e0b', unit: 'kg' },
  { key: 'energyLevel', label: 'Energy', color: '#10b981', unit: '/5' },
  { key: 'activeMinutes', label: 'Active Mins', color: '#06b6d4', unit: 'min' },
];

export default function HealthPage() {
  const [summaries, setSummaries] = useState<DailySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeChart, setActiveChart] = useState('steps');
  const [logForm, setLogForm] = useState({ energyLevel: '3', sleepHours: '', steps: '', restingHr: '', weightKg: '' });
  const [logMsg, setLogMsg] = useState('');

  useEffect(() => {
    api.get('/health?days=30').then(r => { setSummaries(r.data.summaries); setLoading(false); });
  }, []);

  const chart = CHARTS.find(c => c.key === activeChart)!;
  const chartData = summaries
    .filter(s => s[activeChart as keyof DailySummary] != null)
    .map(s => ({
      date: format(new Date(s.date), 'dd MMM'),
      value: s[activeChart as keyof DailySummary],
    }));

  const submitLog = async () => {
    setLogMsg('');
    const payload: Record<string, number> = {};
    if (logForm.energyLevel) payload.energyLevel = Number(logForm.energyLevel);
    if (logForm.sleepHours) payload.sleepHours = Number(logForm.sleepHours);
    if (logForm.steps) payload.steps = Number(logForm.steps);
    if (logForm.restingHr) payload.restingHr = Number(logForm.restingHr);
    if (logForm.weightKg) payload.weightKg = Number(logForm.weightKg);
    try {
      await api.post('/health/log-energy', payload);
      setLogMsg('Logged! +10 XP');
      api.get('/health?days=30').then(r => setSummaries(r.data.summaries));
    } catch { setLogMsg('Error logging'); }
  };

  // Quick averages
  const avg = (key: keyof DailySummary) => {
    const vals = summaries.map(s => s[key]).filter(v => v != null) as number[];
    return vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1) : '—';
  };

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center gap-3">
        <Heart size={24} className="text-red-400" />
        <h1 className="section-title">Health Data</h1>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: 'Avg Steps', value: Number(avg('steps')).toLocaleString(), icon: '👟' },
          { label: 'Avg Sleep', value: `${avg('sleepHours')}h`, icon: '😴' },
          { label: 'Avg HR', value: `${avg('restingHr')}bpm`, icon: '❤️' },
        ].map(s => (
          <div key={s.label} className="card text-center">
            <div className="text-xl mb-1">{s.icon}</div>
            <div className="font-display font-bold text-white text-base">{s.value}</div>
            <div className="text-[10px] text-gray-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Chart selector */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {CHARTS.map(c => (
          <button key={c.key} onClick={() => setActiveChart(c.key)} className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${activeChart === c.key ? 'border-2 text-white' : 'bg-pitch-700 border-pitch-600 text-gray-400'}`} style={activeChart === c.key ? { borderColor: c.color, backgroundColor: c.color + '20', color: c.color } : {}}>
            {c.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-bold text-white">{chart.label}</h3>
          <TrendingUp size={16} style={{ color: chart.color }} />
        </div>
        {loading || chartData.length === 0 ? (
          <div className="h-40 flex items-center justify-center text-gray-600 text-sm">
            {loading ? 'Loading...' : 'No data yet — start logging!'}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a3460" />
              <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} tickLine={false} width={35} />
              <Tooltip contentStyle={{ backgroundColor: '#0d1f3c', border: '1px solid #1a3460', borderRadius: 8, color: '#fff', fontSize: 12 }} formatter={(v: number) => [`${v}${chart.unit}`, chart.label]} />
              <Line type="monotone" dataKey="value" stroke={chart.color} strokeWidth={2} dot={{ fill: chart.color, r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Log form */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Plus size={14} /> Log Today's Data</h3>
        {logMsg && <div className={`mb-3 text-sm px-3 py-2 rounded-lg ${logMsg.includes('XP') ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>{logMsg}</div>}
        <div className="space-y-3">
          <div>
            <label className="label mb-2 block">Energy Level: {logForm.energyLevel}/5</label>
            <input type="range" min={1} max={5} value={logForm.energyLevel} onChange={e => setLogForm(f => ({ ...f, energyLevel: e.target.value }))} className="w-full accent-electric-500" />
            <div className="flex justify-between text-xs text-gray-600 mt-1"><span>Low</span><span>High</span></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { key: 'sleepHours', label: 'Sleep (hours)', placeholder: '7.5' },
              { key: 'steps', label: 'Steps', placeholder: '8500' },
              { key: 'restingHr', label: 'Resting HR', placeholder: '65' },
              { key: 'weightKg', label: 'Weight (kg)', placeholder: '75' },
            ].map(f => (
              <div key={f.key}>
                <label className="label mb-1 block text-[10px]">{f.label}</label>
                <input type="number" className="input-field" placeholder={f.placeholder} value={logForm[f.key as keyof typeof logForm]} onChange={e => setLogForm(form => ({ ...form, [f.key]: e.target.value }))} />
              </div>
            ))}
          </div>
          <button onClick={submitLog} className="btn-primary w-full">Log Data (+10 XP)</button>
        </div>
      </div>
    </div>
  );
}
