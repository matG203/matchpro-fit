mport { useEffect, useState } from 'react';
import { CheckCircle, Circle, Zap, Calendar, Trophy } from 'lucide-react';
import api from '../lib/api';

interface UserChallenge {
  id: string;
  isCompleted: boolean;
  progress: number;
  expiresAt: string;
  xpAwarded: number;
  challenge: {
    title: string;
    description: string;
    xpReward: number;
    target: number;
    unit: string;
    category: string;
    difficulty: string;
    type: string;
  };
}

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: 'text-emerald-400 bg-emerald-400/10',
  medium: 'text-yellow-400 bg-yellow-400/10',
  hard: 'text-red-400 bg-red-400/10',
};

function ChallengeCard({ uc, onComplete }: { uc: UserChallenge; onComplete: (id: string) => void }) {
  const progressPercent = Math.min(100, (uc.progress / uc.challenge.target) * 100);
  const expiry = new Date(uc.expiresAt);
  const hoursLeft = Math.max(0, Math.round((expiry.getTime() - Date.now()) / 3600000));

  return (
    <div className={`card transition-all ${uc.isCompleted ? 'opacity-60' : ''}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5">
          {uc.isCompleted
            ? <CheckCircle size={22} className="text-emerald-400" />
            : <Circle size={22} className="text-gray-600" />
          }
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-white text-sm leading-tight">{uc.challenge.title}</h3>
            <div className="flex items-center gap-1 flex-shrink-0">
              <Zap size={12} className="text-yellow-400" />
              <span className="text-yellow-400 font-bold text-xs">{uc.challenge.xpReward}</span>
            </div>
          </div>
          <p className="text-xs text-gray-500 mt-0.5 mb-2">{uc.challenge.description}</p>

          {/* Progress bar */}
          {!uc.isCompleted && uc.challenge.target > 1 && (
            <div className="mb-2">
              <div className="flex justify-between text-xs text-gray-600 mb-1">
                <span>{uc.progress} / {uc.challenge.target} {uc.challenge.unit}</span>
                <span>{Math.round(progressPercent)}%</span>
              </div>
              <div className="h-1.5 bg-pitch-700 rounded-full overflow-hidden">
                <div className="h-full bg-electric-500 rounded-full transition-all" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded font-medium ${DIFFICULTY_COLORS[uc.challenge.difficulty] || 'text-gray-400'}`}>
                {uc.challenge.difficulty}
              </span>
              <span className="text-xs text-gray-600 flex items-center gap-1">
                <Calendar size={10} />
                {hoursLeft}h left
              </span>
            </div>
            {!uc.isCompleted && (
              <button
                onClick={() => onComplete(uc.id)}
                className="text-xs btn-primary px-3 py-1.5"
              >
                Mark Done
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChallengesPage() {
  const [daily, setDaily] = useState<UserChallenge[]>([]);
  const [weekly, setWeekly] = useState<UserChallenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'daily' | 'weekly'>('daily');

  const load = async () => {
    const [d, w] = await Promise.all([api.get('/challenges/daily'), api.get('/challenges/weekly')]);
    setDaily(d.data);
    setWeekly(w.data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleComplete = async (id: string) => {
    try {
      await api.post(`/challenges/${id}/complete`);
      load();
    } catch (err: any) {
      alert(err.response?.data?.error || 'Could not complete challenge');
    }
  };

  const challenges = tab === 'daily' ? daily : weekly;
  const completed = challenges.filter(c => c.isCompleted).length;
  const totalXp = challenges.filter(c => c.isCompleted).reduce((sum, c) => sum + c.challenge.xpReward, 0);

  return (
    <div className="px-4 py-4 space-y-4">
      <div className="flex items-center gap-3">
        <Trophy size={24} className="text-yellow-400" />
        <h1 className="section-title">Challenges</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 bg-pitch-800 p-1 rounded-xl">
        {(['daily', 'weekly'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${tab === t ? 'bg-electric-500 text-white' : 'text-gray-400'}`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Progress summary */}
      <div className="card flex items-center justify-between">
        <div>
          <div className="text-2xl font-display font-black text-white">{completed}<span className="text-gray-500">/{challenges.length}</span></div>
          <div className="text-xs text-gray-400 uppercase tracking-wider">Completed</div>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-1 justify-end">
            <Zap size={16} className="text-yellow-400" />
            <span className="font-display font-black text-xl text-yellow-400">{totalXp}</span>
          </div>
          <div className="text-xs text-gray-400 uppercase tracking-wider">XP Earned</div>
        </div>
        <div>
          <div className="w-16 h-16">
            <svg viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15" fill="none" stroke="#1a3460" strokeWidth="3" />
              <circle
                cx="18" cy="18" r="15" fill="none"
                stroke="#0ea5e9" strokeWidth="3" strokeLinecap="round"
                strokeDasharray={`${challenges.length ? (completed / challenges.length) * 94 : 0} 94`}
                strokeDashoffset="23.5"
              />
            </svg>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading challenges...</div>
      ) : challenges.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No {tab} challenges yet</div>
      ) : (
        <div className="space-y-3">
          {/* Active first */}
          {challenges.filter(c => !c.isCompleted).map(uc => (
            <ChallengeCard key={uc.id} uc={uc} onComplete={handleComplete} />
          ))}
          {challenges.filter(c => c.isCompleted).length > 0 && (
            <div className="text-xs text-gray-600 uppercase tracking-wider text-center py-2">Completed</div>
          )}
          {challenges.filter(c => c.isCompleted).map(uc => (
            <ChallengeCard key={uc.id} uc={uc} onComplete={handleComplete} />
          ))}
        </div>
      )}
    </div>
  );
}
