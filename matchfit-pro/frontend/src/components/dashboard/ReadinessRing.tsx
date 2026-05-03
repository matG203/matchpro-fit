interface ReadinessRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
}

export default function ReadinessRing({ score, size = 120, strokeWidth = 10, showLabel = true }: ReadinessRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const color = score >= 70 ? '#10b981' : score >= 40 ? '#f59e0b' : '#ef4444';
  const label = score >= 70 ? 'MATCH READY' : score >= 40 ? 'BUILDING' : 'EARLY DAYS';

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="readiness-ring">
          {/* Background ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#1a3460"
            strokeWidth={strokeWidth}
          />
          {/* Progress ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1s ease-out, stroke 0.3s' }}
            filter={`drop-shadow(0 0 6px ${color})`}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display font-black text-3xl text-white">{score}%</span>
          <span className="text-[9px] font-medium text-gray-400 uppercase tracking-wider">READY</span>
        </div>
      </div>
      {showLabel && (
        <div className="mt-1 text-xs font-display font-bold uppercase tracking-wider" style={{ color }}>
          {label}
        </div>
      )}
    </div>
  );
}
