import { useEffect, useState } from ''react'';
import { useNavigate } from ''react-router-dom'';
import { Dumbbell, Zap, Battery, Plus, ChevronRight, CheckCircle, Circle, Watch } from ''lucide-react'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';
import ReadinessRing from ''../components/dashboard/ReadinessRing'';
import XPBar from ''../components/dashboard/XPBar'';

interface DashboardData {
  profile: { displayName: string; position: string } | null;
  playerCard: { overall: number; tier: string; totalXp: number; xpLevel: number } | null;
  readiness: number;
  level: number;
  xpProgress: { current: number; needed: number; percent: number };
  totalXp: number;
  todaySummary: { steps?: number; sleepHours?: number; restingHr?: number; energyLevel?: number } | null;
  energyState: ''green'' | ''yellow'' | ''red'' | null;
  wearables: { provider: string; lastSync: string | null }[];
  notifications: { id: string; title: string; body: string }[];
  dailyChallenges: { id: string; isCompleted: boolean; challenge: { title: string; xpReward: number } }[];
}

const TIER_COLORS: Record<string, string> = {
  bronze: ''#cd7f32'',
  silver: ''#94a3b8'',
  common_gold: ''#f59e0b'',
  rare_gold: ''#fbbf24'',
  elite: ''#a78bfa'',
};

const ENERGY_CONFIG = {
  green: { label: ''High Energy'', color: ''text-emerald-400'', bg: ''bg-emerald-400/10 border-emerald-400/20'', dot: ''bg-emerald-400'' },
  yellow: { label: ''Moderate Energy'', color: ''text-yellow-400'', bg: ''bg-yellow-400/10 border-yellow-400/20'', dot: ''bg-yellow-400'' },
  red: { label: ''Low Energy'', color: ''text-red-400'', bg: ''bg-red-400/10 border-red-400/20'', dot: ''bg-red-400'' },
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const { user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    api.get(''/dashboard'').then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const handleLogEnergy = async () => navigate(''/health'');
  const handleGenerateWorkout = () => navigate(''/workout-planner'');

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-electric-400 font-display font-bold text-xl animate-pulse">LOADING...</div>
      </div>
    );
  }

  const energyState = data?.energyState;
  const energyCfg = energyState ? ENERGY_CONFIG[energyState] : null;

  return (
    <div className="px-4 py-4 space-y-4">
      {/* Greeting */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm">Welcome back,</p>
          <h1 className="font-display font-black text-2xl text-white">
            {data?.profile?.displayName || user?.username}
          </h1>
        </div>
        <div
          className="px-3 py-1.5 rounded-xl border text-xs font-display font-bold uppercase tracking-wider"
          style={{ color: TIER_COLORS[data?.playerCard?.tier || ''bronze''], borderColor: TIER_COLORS[data?.playerCard?.tier || ''bronze''] + ''40'', backgroundColor: TIER_COLORS[data?.playerCard?.tier || ''bronze''] + ''10'' }}
        >
          {(data?.playerCard?.tier || ''bronze'').replace(''_'', '' '')}
        </div>
      </div>

      {/* Readiness + Card Overall */}
      <div className="card flex items-center justify-between">
        <ReadinessRing score={data?.readiness || 0} size={110} />
        <div className="flex-1 flex flex-col items-center">
          <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Card Overall</div>
          <div
            className="font-display font-black text-5xl"
            style={{ color: TIER_COLORS[data?.playerCard?.tier || ''bronze''] }}
          >
            {data?.playerCard?.overall || 45}
          </div>
          <div className="text-gray-500 text-xs mt-1">OVERALL RATING</div>
          <button onClick={() => navigate(''/player-card'')} className="mt-2 text-xs text-electric-400 flex items-center gap-1">
            View Card <ChevronRight size={12} />
          </button>
        </div>
      </div>

      {/* XP Bar */}
      <XPBar
        level={data?.level || 1}
        current={data?.xpProgress.current || 0}
        needed={data?.xpProgress.needed || 500}
        percent={data?.xpProgress.percent || 0}
        totalXp={data?.totalXp || 0}
      />

      {/* Energy State */}
      {energyCfg ? (
        <div className={`card border flex items-center gap-3 ${energyCfg.bg}`}>
          <div className={`w-3 h-3 rounded-full ${energyCfg.dot} animate-pulse`} />
          <div className="flex-1">
            <div className={`font-semibold text-sm ${energyCfg.color}`}>{energyCfg.label}</div>
            <div className="text-xs text-gray-500">Energy logged today</div>
          </div>
          <button onClick={handleGenerateWorkout} className="btn-primary text-xs px-3 py-1.5">Train</button>
        </div>
      ) : (
        <button onClick={handleLogEnergy} className="card border border-pitch-600 w-full flex items-center gap-3 hover:border-electric-500/50 transition-colors">
          <div className="w-10 h-10 rounded-xl bg-pitch-700 flex items-center justify-center">
            <Battery size={20} className="text-gray-400" />
          </div>
          <div className="flex-1 text-left">
            <div className="text-white font-semibold text-sm">Log Today''s Energy</div>
            <div className="text-xs text-gray-500">Earn 10 XP + unlock smart workout</div>
          </div>
          <Plus size={16} className="text-gray-500" />
        </button>
      )}

      {/* Today''s stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: ''Steps'', value: data?.todaySummary?.steps?.toLocaleString() || ''â€”'', icon: ''ðŸ‘Ÿ'' },
          { label: ''Sleep'', value: data?.todaySummary?.sleepHours ? `${data.todaySummary.sleepHours}h` : ''â€”'', icon: ''ðŸ˜´'' },
          { label: ''Resting HR'', value: data?.todaySummary?.restingHr ? `${data.todaySummary.restingHr}bpm` : ''â€”'', icon: ''â¤ï¸'' },
        ].map(({ label, value, icon }) => (
          <div key={label} className="card text-center">
            <div className="text-xl mb-1">{icon}</div>
            <div className="font-display font-bold text-white text-lg leading-none">{value}</div>
            <div className="text-[10px] text-gray-500 mt-1 uppercase tracking-wider">{label}</div>
          </div>
        ))}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3">
        <button onClick={handleGenerateWorkout} className="card flex flex-col items-center gap-2 py-4 hover:border-electric-500/50 transition-colors border border-pitch-600">
          <div className="w-10 h-10 rounded-xl bg-electric-500/10 flex items-center justify-center">
            <Dumbbell size={20} className="text-electric-400" />
          </div>
          <span className="text-sm font-semibold text-white">Generate Workout</span>
        </button>
        <button
          onClick={() => api.post(''/workouts/minimum-viable'').then(() => navigate(''/workouts''))}
          className="card flex flex-col items-center gap-2 py-4 hover:border-yellow-500/50 transition-colors border border-pitch-600"
        >
          <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
            <Zap size={20} className="text-yellow-400" />
          </div>
          <span className="text-sm font-semibold text-white">Min. Session</span>
        </button>
      </div>

      {/* Daily Challenges */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <span className="font-display font-bold text-white uppercase tracking-wide text-sm">Daily Challenges</span>
          <button onClick={() => navigate(''/challenges'')} className="text-xs text-electric-400">View All</button>
        </div>
        <div className="space-y-2">
          {(data?.dailyChallenges || []).slice(0, 3).map((uc) => (
            <div key={uc.id} className={`flex items-center gap-3 p-2 rounded-lg transition-colors ${uc.isCompleted ? ''opacity-50'' : ''hover:bg-pitch-700''}`}>
              {uc.isCompleted
                ? <CheckCircle size={18} className="text-emerald-400 flex-shrink-0" />
                : <Circle size={18} className="text-gray-600 flex-shrink-0" />
              }
              <div className="flex-1 text-sm text-white">{uc.challenge.title}</div>
              <div className="flex items-center gap-1">
                <Zap size={10} className="text-yellow-400" />
                <span className="text-xs text-yellow-400 font-bold">{uc.challenge.xpReward}</span>
              </div>
            </div>
          ))}
          {(!data?.dailyChallenges || data.dailyChallenges.length === 0) && (
            <p className="text-gray-500 text-sm text-center py-2">No challenges yet â€” check back shortly!</p>
          )}
        </div>
      </div>

      {/* Wearable status */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <span className="font-display font-bold text-white uppercase tracking-wide text-sm">Connected Devices</span>
          <button onClick={() => navigate(''/wearables'')} className="text-xs text-electric-400">Manage</button>
        </div>
        {data?.wearables && data.wearables.length > 0 ? (
          <div className="space-y-2">
            {data.wearables.map(w => (
              <div key={w.provider} className="flex items-center gap-3">
                <Watch size={16} className="text-electric-400" />
                <span className="text-sm text-white capitalize">{w.provider}</span>
                <span className="text-xs text-gray-500 ml-auto">
                  {w.lastSync ? `Synced ${new Date(w.lastSync).toLocaleDateString()}` : ''Never synced''}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <button onClick={() => navigate(''/wearables'')} className="w-full text-center text-sm text-gray-500 hover:text-electric-400 transition-colors py-1">
            + Connect a wearable for automatic tracking
          </button>
        )}
      </div>
    </div>
  );
}
