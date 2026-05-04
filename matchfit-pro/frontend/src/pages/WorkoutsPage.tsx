mport { useEffect, useState } from 'react';
import { Activity, Zap, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../lib/api';
import { format } from 'date-fns';

interface Workout {
  id: string; title: string; category: string; difficulty: string;
  durationMins: number; rpe?: number; notes?: string; xpAwarded: number;
  statsImproved: string[]; completedAt: string;
}

const DIFFICULTY_COLORS: Record<string, string> = {
  recovery: 'text-blue-400', easy: 'text-emerald-400',
  moderate: 'text-yellow-400', hard: 'text-red-400',
};

export default function WorkoutsPage() {
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    api.get('/workouts/history').then(r => { setWorkouts(r.data); setLoading(false); });
  }, []);

  const totalXp = workouts.reduce((s, w) => s + w.xpAwarded, 0);
  const totalMins = workouts.reduce((s, w) => s + w.durationMins, 0);

  return (
    <div className="px-4 py-4 space-y-4">
      <div className="flex items-center gap-3">
        <Activity size={24} className="text-electric-400" />
        <h1 className="section-title">Workout History</h1>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total Sessions', value: workouts.length.toString(), icon: '🏋️' },
          { label: 'Total XP', value: totalXp.toLocaleString(), icon: '⚡' },
          { label: 'Total Time', value: `${Math.round(totalMins / 60)}h`, icon: '⏱️' },
        ].map(s => (
          <div key={s.label} className="card text-center">
            <div className="text-xl mb-1">{s.icon}</div>
            <div className="font-display font-bold text-white">{s.value}</div>
            <div className="text-[10px] text-gray-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : workouts.length === 0 ? (
        <div className="card text-center py-8">
          <p className="text-gray-400 text-sm">No workouts yet — head to the Workout Planner to get started!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {workouts.map(w => (
            <div key={w.id} className="card">
              <button className="w-full text-left" onClick={() => setExpanded(expanded === w.id ? null : w.id)}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-white text-sm truncate">{w.title}</div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className={`text-xs font-medium ${DIFFICULTY_COLORS[w.difficulty] || 'text-gray-400'}`}>
                        {w.difficulty}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-gray-500">
                        <Clock size={10} /> {w.durationMins}m
                      </span>
                      <span className="flex items-center gap-1 text-xs text-yellow-400 font-bold">
                        <Zap size={10} /> {w.xpAwarded}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-gray-600">
                      {format(new Date(w.completedAt), 'dd MMM')}
                    </span>
                    {expanded === w.id ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
                  </div>
                </div>
              </button>

              {expanded === w.id && (
                <div className="mt-3 pt-3 border-t border-pitch-700 space-y-2">
                  {w.rpe && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">RPE</span>
                      <span className="text-white font-medium">{w.rpe}/10</span>
                    </div>
                  )}
                  {w.statsImproved.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {(w.statsImproved as string[]).map((s: string) => (
                        <span key={s} className="px-2 py-0.5 bg-electric-500/10 border border-electric-500/20 rounded text-electric-400 text-xs">
                          +{s}
                        </span>
                      ))}
                    </div>
                  )}
                  {w.notes && <p className="text-xs text-gray-500 italic">{w.notes}</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
