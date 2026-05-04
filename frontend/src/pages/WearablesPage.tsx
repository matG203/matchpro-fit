import { useEffect, useState } from ''react'';
import { Watch, RefreshCw, Unlink, Plus, Upload } from ''lucide-react'';
import api from ''../lib/api'';

interface WearableConnection { id: string; provider: string; isActive: boolean; lastSync: string | null; }

const PROVIDERS = [
  { key: ''fitbit'', label: ''Fitbit'', icon: ''âŒš'', desc: ''OAuth connection available'', supported: true },
  { key: ''garmin'', label: ''Garmin'', icon: ''ðŸƒ'', desc: ''API partner approval required'', supported: false },
  { key: ''apple'', label: ''Apple Health'', icon: ''ðŸŽ'', desc: ''Requires iOS companion app'', supported: false },
  { key: ''google'', label: ''Google Fit'', icon: ''ðŸ”µ'', desc: ''Health Connect integration'', supported: false },
];

export default function WearablesPage() {
  const [connections, setConnections] = useState<WearableConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [manualForm, setManualForm] = useState({ steps: '''', sleepHours: '''', restingHr: '''', weightKg: '''' });
  const [manualMsg, setManualMsg] = useState('''');
  const [syncing, setSyncing] = useState('''');

  const load = () => api.get(''/wearables'').then(r => { setConnections(r.data); setLoading(false); });
  useEffect(() => { load(); }, []);

  const connectFitbit = async () => {
    const { data } = await api.get(''/wearables/fitbit/connect'');
    if (data.url) window.location.href = data.url;
  };

  const sync = async (provider: string) => {
    setSyncing(provider);
    try {
      if (provider === ''fitbit'') await api.post(''/wearables/fitbit/sync'');
      await load();
    } finally { setSyncing(''''); }
  };

  const disconnect = async (provider: string) => {
    await api.delete(`/wearables/${provider}`);
    load();
  };

  const submitManual = async () => {
    setManualMsg('''');
    const payload: Record<string, number> = {};
    if (manualForm.steps) payload.steps = Number(manualForm.steps);
    if (manualForm.sleepHours) payload.sleepHours = Number(manualForm.sleepHours);
    if (manualForm.restingHr) payload.restingHr = Number(manualForm.restingHr);
    if (manualForm.weightKg) payload.weightKg = Number(manualForm.weightKg);
    try {
      await api.post(''/wearables/manual'', payload);
      setManualMsg(''Data logged! +10 XP'');
      setManualForm({ steps: '''', sleepHours: '''', restingHr: '''', weightKg: '''' });
    } catch { setManualMsg(''Error saving data''); }
  };

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center gap-3">
        <Watch size={24} className="text-electric-400" />
        <h1 className="section-title">Wearables</h1>
      </div>

      {/* Connected */}
      {connections.filter(c => c.isActive).length > 0 && (
        <div className="card">
          <h3 className="label mb-3">Connected</h3>
          <div className="space-y-3">
            {connections.filter(c => c.isActive).map(c => (
              <div key={c.id} className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-lg">
                  {PROVIDERS.find(p => p.key === c.provider)?.icon || ''âŒš''}
                </div>
                <div className="flex-1">
                  <div className="text-white font-semibold text-sm capitalize">{c.provider}</div>
                  <div className="text-xs text-gray-500">{c.lastSync ? `Last sync: ${new Date(c.lastSync).toLocaleString()}` : ''Never synced''}</div>
                </div>
                <button onClick={() => sync(c.provider)} disabled={syncing === c.provider} className="p-2 rounded-lg bg-pitch-700 text-gray-400 hover:text-white">
                  <RefreshCw size={14} className={syncing === c.provider ? ''animate-spin'' : ''''} />
                </button>
                <button onClick={() => disconnect(c.provider)} className="p-2 rounded-lg bg-pitch-700 text-red-400 hover:bg-red-400/10">
                  <Unlink size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Available providers */}
      <div className="card">
        <h3 className="label mb-3">Connect a Device</h3>
        <div className="space-y-2">
          {PROVIDERS.map(p => {
            const connected = connections.find(c => c.provider === p.key && c.isActive);
            return (
              <div key={p.key} className={`flex items-center gap-3 p-3 rounded-xl border ${connected ? ''border-emerald-500/30 bg-emerald-500/5'' : ''border-pitch-600 bg-pitch-700''}`}>
                <div className="text-2xl">{p.icon}</div>
                <div className="flex-1">
                  <div className="text-white font-semibold text-sm">{p.label}</div>
                  <div className="text-xs text-gray-500">{p.desc}</div>
                </div>
                {connected ? (
                  <span className="text-xs text-emerald-400 font-medium">Connected</span>
                ) : p.key === ''fitbit'' ? (
                  <button onClick={connectFitbit} className="btn-primary text-xs px-3 py-1.5 flex items-center gap-1"><Plus size={12} /> Connect</button>
                ) : (
                  <span className="text-xs text-gray-600 bg-pitch-800 px-2 py-1 rounded">Coming soon</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Manual entry */}
      <div className="card">
        <h3 className="label mb-3 flex items-center gap-2"><Plus size={14} /> Manual Entry</h3>
        {manualMsg && <div className={`mb-3 text-sm px-3 py-2 rounded-lg ${manualMsg.includes(''XP'') ? ''bg-emerald-500/10 text-emerald-400'' : ''bg-red-500/10 text-red-400''}`}>{manualMsg}</div>}
        <div className="grid grid-cols-2 gap-3 mb-3">
          {[
            { key: ''steps'', label: ''Steps'', placeholder: ''8500'' },
            { key: ''sleepHours'', label: ''Sleep (hours)'', placeholder: ''7.5'' },
            { key: ''restingHr'', label: ''Resting HR (bpm)'', placeholder: ''62'' },
            { key: ''weightKg'', label: ''Weight (kg)'', placeholder: ''75'' },
          ].map(f => (
            <div key={f.key}>
              <label className="label mb-1 block text-[10px]">{f.label}</label>
              <input type="number" className="input-field" placeholder={f.placeholder} value={manualForm[f.key as keyof typeof manualForm]} onChange={e => setManualForm(m => ({ ...m, [f.key]: e.target.value }))} />
            </div>
          ))}
        </div>
        <button onClick={submitManual} className="btn-primary w-full text-sm">Log Data (+10 XP)</button>
      </div>

      {/* CSV import */}
      <div className="card">
        <h3 className="label mb-2 flex items-center gap-2"><Upload size={14} /> CSV Import</h3>
        <p className="text-xs text-gray-500 mb-3">Import historical data from your wearable export</p>
        <button className="btn-secondary w-full text-sm opacity-60" disabled>CSV Import (Coming Soon)</button>
      </div>
    </div>
  );
}
