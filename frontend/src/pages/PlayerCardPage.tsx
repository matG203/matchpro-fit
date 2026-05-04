import { useEffect, useState } from ''react'';
import { useNavigate } from ''react-router-dom'';
import { RefreshCw, Pencil } from ''lucide-react'';
import api from ''../lib/api'';
import PlayerCard from ''../components/card/PlayerCard'';

interface CardPageData {
  card: {
    overall: number; tier: string; pace: number; shooting: number; passing: number;
    dribbling: number; defending: number; physical: number; stamina: number;
    recovery: number; composure: number; totalXp: number; xpLevel: number;
  };
  profile: { displayName: string; position: string };
  avatar: {
    skinTone: string; kitColour: string; kitPattern: string; hairStyle: string;
    hairColour: string; facialHair: string; bootColour: string; bodyType: string;
    pose: string; headband: boolean; wristTape: boolean; gloves: boolean;
    captainArmband: boolean; glasses: boolean;
  };
}

const TIER_LABELS: Record<string, string> = {
  bronze: ''Bronze'', silver: ''Silver'', common_gold: ''Gold'',
  rare_gold: ''Rare Gold'', elite: ''Elite âš¡'',
};

export default function PlayerCardPage() {
  const [data, setData] = useState<CardPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    api.get(''/player-card'').then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const recalculate = async () => {
    setRecalculating(true);
    await api.post(''/player-card/recalculate'');
    await load();
    setRecalculating(false);
  };

  if (loading || !data) {
    return <div className="flex items-center justify-center min-h-screen"><div className="text-electric-400 font-display font-bold animate-pulse">LOADING CARD...</div></div>;
  }

  const nextTier = { bronze: ''Silver (60+)'', silver: ''Gold (75+)'', common_gold: ''Rare Gold (85+)'', rare_gold: ''Elite (90+)'', elite: ''MAX TIER'' };
  const toNext = nextTier[data.card.tier as keyof typeof nextTier] || '''';

  return (
    <div className="px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="section-title">Player Card</h1>
        <div className="flex gap-2">
          <button onClick={() => navigate(''/avatar'')} className="btn-secondary flex items-center gap-1.5 text-sm px-3 py-2">
            <Pencil size={14} /> Edit Avatar
          </button>
          <button onClick={recalculate} disabled={recalculating} className="btn-secondary p-2">
            <RefreshCw size={16} className={recalculating ? ''animate-spin'' : ''''} />
          </button>
        </div>
      </div>

      {/* Card display */}
      <div className="flex justify-center py-4">
        <PlayerCard card={data.card} profile={data.profile} avatar={data.avatar} animated />
      </div>

      {/* Tier info */}
      <div className="card text-center">
        <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Current Tier</div>
        <div className="font-display font-black text-2xl text-white mb-1">{TIER_LABELS[data.card.tier] || data.card.tier}</div>
        {data.card.tier !== ''elite'' && (
          <div className="text-xs text-gray-500">Next: <span className="text-electric-400">{toNext}</span></div>
        )}
      </div>

      {/* Full stats breakdown */}
      <div className="card">
        <h2 className="font-display font-bold text-white uppercase tracking-wide text-sm mb-4">Stats Breakdown</h2>
        <div className="space-y-3">
          {[
            { label: ''Pace'', value: data.card.pace, desc: ''Sprint tests, speed workouts'' },
            { label: ''Shooting'', value: data.card.shooting, desc: ''Shooting practice sessions'' },
            { label: ''Passing'', value: data.card.passing, desc: ''Wall passing, passing drills'' },
            { label: ''Dribbling'', value: data.card.dribbling, desc: ''Agility, cone drills'' },
            { label: ''Defending'', value: data.card.defending, desc: ''Agility & strength work'' },
            { label: ''Physical'', value: data.card.physical, desc: ''Strength training'' },
            { label: ''Stamina'', value: data.card.stamina, desc: ''Cardio, steps, active mins'' },
            { label: ''Recovery'', value: data.card.recovery, desc: ''Sleep, rest sessions'' },
            { label: ''Composure'', value: data.card.composure, desc: ''Routine consistency, streaks'' },
          ].map(({ label, value, desc }) => {
            const color = value >= 80 ? ''#10b981'' : value >= 65 ? ''#f59e0b'' : ''#0ea5e9'';
            return (
              <div key={label}>
                <div className="flex items-center justify-between mb-1">
                  <div>
                    <span className="text-sm font-semibold text-white">{label}</span>
                    <span className="text-xs text-gray-600 ml-2">{desc}</span>
                  </div>
                  <span className="font-display font-bold text-white">{value}</span>
                </div>
                <div className="h-2 bg-pitch-700 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${value}%`, backgroundColor: color }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="text-xs text-gray-600 text-center pb-4">Tap the card to flip and see all stats. Complete workouts, tests, and challenges to improve your rating.</p>
    </div>
  );
}
