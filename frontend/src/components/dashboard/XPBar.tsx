nterface XPBarProps {
  level: number;
  current: number;
  needed: number;
  percent: number;
  totalXp: number;
}

export default function XPBar({ level, current, needed, percent, totalXp }: XPBarProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-electric-500/20 border border-electric-500/40 flex items-center justify-center">
            <span className="font-display font-black text-sm text-electric-400">{level}</span>
          </div>
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wider">Level</div>
            <div className="font-display font-bold text-white text-sm">{current.toLocaleString()} / {needed.toLocaleString()} XP</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500">Total XP</div>
          <div className="font-display font-bold text-electric-400">{totalXp.toLocaleString()}</div>
        </div>
      </div>
      <div className="xp-bar">
        <div
          className="xp-bar-fill"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <div className="text-[10px] text-gray-500">Lv {level}</div>
        <div className="text-[10px] text-gray-500">Lv {level + 1}</div>
      </div>
    </div>
  );
}
