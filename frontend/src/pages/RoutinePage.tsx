import { useEffect, useState } from ''react'';
import { CheckCircle, Circle, ClipboardList, Zap } from ''lucide-react'';
import api from ''../lib/api'';

interface RoutineItem { id: string; label: string; time: string; enabled: boolean; }
interface RoutineCompletion { completedItems: string[]; xpAwarded: number; }

const TIME_GROUPS = [
  { key: ''morning'', label: ''ðŸŒ… Morning'', color: ''text-yellow-400'' },
  { key: ''afternoon'', label: ''â˜€ï¸ Afternoon'', color: ''text-orange-400'' },
  { key: ''evening'', label: ''ðŸŒ† Evening'', color: ''text-purple-400'' },
  { key: ''night'', label: ''ðŸŒ™ Night'', color: ''text-blue-400'' },
];

export default function RoutinePage() {
  const [items, setItems] = useState<RoutineItem[]>([]);
  const [completion, setCompletion] = useState<RoutineCompletion | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState('''');

  const load = async () => {
    const { data } = await api.get(''/routine/today'');
    setItems((data.checklist?.items as RoutineItem[]) || []);
    setCompletion(data.completion);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const toggle = async (itemId: string) => {
    setCompleting(itemId);
    try {
      await api.post(''/routine/complete'', { itemId });
      load();
    } finally { setCompleting(''''); }
  };

  const completedItems = completion?.completedItems || [];
  const enabledItems = items.filter(i => i.enabled);
  const completedCount = enabledItems.filter(i => completedItems.includes(i.id)).length;
  const percent = enabledItems.length > 0 ? Math.round((completedCount / enabledItems.length) * 100) : 0;
  const today = new Date().toLocaleDateString(''en-GB'', { weekday: ''long'', day: ''numeric'', month: ''long'' });

  return (
    <div className="px-4 py-4 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ClipboardList size={24} className="text-electric-400" />
          <h1 className="section-title">Daily Routine</h1>
        </div>
      </div>

      <p className="text-gray-400 text-sm">{today}</p>

      {/* Progress ring */}
      <div className="card flex items-center gap-5">
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
            <circle cx="18" cy="18" r="15" fill="none" stroke="#1a3460" strokeWidth="3" />
            <circle
              cx="18" cy="18" r="15" fill="none"
              stroke={percent === 100 ? ''#10b981'' : ''#0ea5e9''} strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={`${(percent / 100) * 94} 94`}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-display font-black text-lg text-white">{percent}%</span>
          </div>
        </div>
        <div>
          <div className="font-display font-bold text-white text-xl">{completedCount} / {enabledItems.length}</div>
          <div className="text-gray-400 text-sm">items complete</div>
          {completion?.xpAwarded ? (
            <div className="flex items-center gap-1 mt-1 text-yellow-400 text-sm font-semibold">
              <Zap size={14} /> +{completion.xpAwarded} XP earned today
            </div>
          ) : percent === 100 ? (
            <div className="text-emerald-400 text-sm mt-1 font-semibold">All done! ðŸŽ‰</div>
          ) : (
            <div className="text-gray-500 text-xs mt-1">Complete all for +25 XP</div>
          )}
        </div>
      </div>

      {/* Checklist by time */}
      {loading ? (
        <div className="text-center py-8 text-gray-500">Loading routine...</div>
      ) : (
        TIME_GROUPS.map(group => {
          const groupItems = items.filter(i => i.time === group.key && i.enabled);
          if (groupItems.length === 0) return null;
          return (
            <div key={group.key} className="card">
              <h3 className={`font-display font-bold uppercase tracking-wide text-sm mb-3 ${group.color}`}>{group.label}</h3>
              <div className="space-y-1">
                {groupItems.map(item => {
                  const done = completedItems.includes(item.id);
                  const isCompleting = completing === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => !done && toggle(item.id)}
                      disabled={done || isCompleting}
                      className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all text-left ${
                        done
                          ? ''bg-emerald-500/5 border border-emerald-500/20''
                          : ''hover:bg-pitch-700 border border-transparent''
                      }`}
                    >
                      {done
                        ? <CheckCircle size={22} className="text-emerald-400 flex-shrink-0" />
                        : <Circle size={22} className={`flex-shrink-0 ${isCompleting ? ''text-electric-400 animate-pulse'' : ''text-gray-600''}`} />
                      }
                      <span className={`text-sm font-medium ${done ? ''text-gray-500 line-through'' : ''text-white''}`}>
                        {item.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })
      )}

      <p className="text-xs text-gray-600 text-center pb-4">
        Customise your routine in Settings â†’ Routine
      </p>
    </div>
  );
}
