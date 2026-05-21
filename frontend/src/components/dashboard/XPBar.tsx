export default function XPBar({ xp, floor, next }: { xp: number; floor: number; next: number }) {
  const progress = Math.min(100, Math.max(0, ((xp - floor) / (next - floor)) * 100));
  return (
    <div>
      <div className="between muted"><span>{xp} XP</span><span>{next - xp} to next level</span></div>
      <div className="xp-track"><span style={{ width: `${progress}%` }} /></div>
    </div>
  );
}
