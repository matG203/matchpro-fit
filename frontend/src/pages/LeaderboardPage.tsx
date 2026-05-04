mport { useEffect, useState } from ''react'';
import { Trophy, Zap, Star } from ''lucide-react'';
import api from ''../lib/api'';
import { useAuthStore } from ''../store/authStore'';

interface LeaderboardEntry {
  userId: string;
  displayName: string;
  username: string;
  weeklyXp: number;
  totalXp: number;
  overall: number;
  readiness: number;
  weeklySteps: number;
  weeklyWorkouts: number;
  currentStreak: number;
  isCurrentUser?: boolean;
}

const TIER_COLORS: Record<string, string> = {
  bronze: ''#cd7f32'', silver: ''#94a3b8'', common_gold: ''#f59e0b'',
  rare_gold: ''#fbbf24'', elite: ''#a78bfa'',
};

const TABS = [
  { key: ''weeklyXp'', label: ''Weekly XP'' },
  { key: ''totalXp'', label: ''Total XP'' },
  { key: ''overall'', label: ''Overall'' },
  { key: ''weeklyWorkouts'', label: ''Workouts'' },
];

export default function LeaderboardPage() {
  const [friends, setFriends] = useState<LeaderboardEntry[]>([]);
  const [global, setGlobal] = useState<LeaderboardEntry[]>([]);
  const [tab, setTab] = useState<''friends'' | ''global''>(''friends'');
  const [sortKey, setSortKey] = useState(''weeklyXp'');
  const [loading, setLoading] = useState(true);
  const { user } = useAuthStore();

  useEffect(() => {
    Promise.all([api.get(''/leaderboards/friends''), api.get(''/leaderboards/global'')])
      .then(([f, g]) => { setFriends(f.data); setGlobal(g.data); })
      .finally(() => setLoading(false));
  }, []);

  const data = tab === ''friends'' ? friends : global;
  const sorted = [...data].sort((a, b) => (b[sortKey as keyof LeaderboardEntry] as number) - (a[sortKey as keyof LeaderboardEntry] as number));

  const rankEmoji = (i: number) => i === 0 ? ''ðŸ¥‡'' : i === 1 ? ''ðŸ¥ˆ'' : i === 2 ? ''ðŸ¥‰'' : `${i + 1}`;

  return (
    <div className="px-4 py-4 space-y-4">
      <div className="flex items-center gap-3">
        <Trophy size={24} className="text-yellow-400" />
        <h1 className="section-title">Leaderboard</h1>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-2 bg-pitch-800 p-1 rounded-xl">
        {([''friends'', ''global''] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${tab === t ? ''bg-electric-500 text-white'' : ''text-gray-400''}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Sort tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setSortKey(t.key)} className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${sortKey === t.key ? ''bg-electric-500/20 border-electric-500 text-electric-400'' : ''bg-pitch-700 border-pitch-600 text-gray-400''}`}>
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : sorted.length === 0 ? (
        <div className="card text-center py-8">
          <p className="text-gray-400 text-sm">No data yet â€” add friends to compete!</p>
        </div>
      ) : (
        <div className="space-y-2">
          {sorted.map((entry, i) => {
            const isYou = entry.userId === user?.id || entry.isCurrentUser;
            const val = entry[sortKey as keyof LeaderboardEntry];
            return (
              <div key={entry.userId} className={`card flex items-center gap-3 transition-all ${isYou ? ''border-electric-500/50 bg-electric-500/5'' : ''''}`}>
                <div className="text-lg font-display font-black w-8 text-center flex-shrink-0">
                  {rankEmoji(i)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-semibold text-sm truncate ${isYou ? ''text-electric-400'' : ''text-white''}`}>
                      {entry.displayName}
                    </span>
                    {isYou && <span className="text-xs text-electric-400 bg-electric-400/10 px-1.5 py-0.5 rounded">You</span>}
                  </div>
                  <span className="text-xs text-gray-500">@{entry.username}</span>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="flex items-center gap-1 justify-end">
                    {sortKey === ''weeklyXp'' || sortKey === ''totalXp''
                      ? <><Zap size={12} className="text-yellow-400" /><span className="font-display font-bold text-white">{(val as number).toLocaleString()}</span></>
                      : sortKey === ''overall''
                      ? <><Star size={12} className="text-gold-400" /><span className="font-display font-bold text-white">{val}</span></>
                      : <span className="font-display font-bold text-white">{val}</span>
                    }
                  </div>
                  <div className="text-xs text-gray-600">{TABS.find(t => t.key === sortKey)?.label}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
