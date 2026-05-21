export default function ReadinessRing({ score }: { score: number }) {
  const size = 180;
  const radius = 69;
  const length = Math.PI * 2 * radius;
  return (
    <div className="readiness">
      <svg viewBox={`0 0 ${size} ${size}`} aria-label={`${score}% match readiness`}>
        <circle cx="90" cy="90" r={radius} className="ring-track" />
        <circle cx="90" cy="90" r={radius} className="ring-fill" strokeDasharray={length} strokeDashoffset={length - length * score / 100} />
      </svg>
      <div><strong>{score}%</strong><span>Match readiness</span></div>
    </div>
  );
}
