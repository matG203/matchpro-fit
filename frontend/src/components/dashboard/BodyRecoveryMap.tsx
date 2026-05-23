type BodyPartLoad = {
  part: string;
  load: number;
  status: string;
};

const zones = [
  ['head', 'conditioning', 'Conditioning'],
  ['chest', 'chest', 'Chest'],
  ['shoulder-left', 'shoulders', 'Shoulders'],
  ['shoulder-right', 'shoulders', 'Shoulders'],
  ['arm-left', 'biceps', 'Biceps'],
  ['arm-right', 'triceps', 'Triceps'],
  ['torso', 'core', 'Core'],
  ['back', 'back', 'Back'],
  ['hip-left', 'hip flexors', 'Hip Flexors'],
  ['hip-right', 'adductors', 'Adductors'],
  ['glutes', 'glutes', 'Glutes'],
  ['leg-left', 'quads', 'Quads'],
  ['leg-right', 'hamstrings', 'Hamstrings'],
  ['calf-left', 'calves', 'Calves'],
  ['calf-right', 'calves', 'Calves'],
  ['ankle-left', 'ankles', 'Ankles'],
  ['ankle-right', 'ankles', 'Ankles'],
  ['ball', 'technical', 'Technical'],
];

function colorFor(load = 0) {
  if (load >= 75) return '#ef4444';
  if (load >= 45) return '#f97316';
  if (load >= 18) return '#facc15';
  return '#22c55e';
}

export default function BodyRecoveryMap({ map }: { map?: { parts?: BodyPartLoad[]; summary?: string } }) {
  const parts = new Map((map?.parts || []).map((item) => [item.part, item]));
  const mostLoaded = [...parts.values()].sort((a, b) => b.load - a.load).slice(0, 6);

  return (
    <div className="body-recovery-wrap">
      <div className="body-map" aria-label="Body recovery heat map">
        {zones.map(([className, part, label]) => {
          const load = parts.get(part)?.load || 0;
          return (
            <div
              key={`${className}-${part}`}
              className={`body-zone ${className}`}
              title={`${label}: ${load}% loaded`}
              style={{ background: colorFor(load), opacity: Math.max(0.38, 0.42 + load / 140) }}
            />
          );
        })}
      </div>
      <div className="stack">
        <p className="muted">{map?.summary || 'Complete a programmed workout to start the recovery map.'}</p>
        <div className="recovery-legend">
          <span><i style={{ background: '#22c55e' }} /> Fresh</span>
          <span><i style={{ background: '#facc15' }} /> Warm</span>
          <span><i style={{ background: '#f97316' }} /> Loaded</span>
          <span><i style={{ background: '#ef4444' }} /> Recovery</span>
        </div>
        <div className="body-load-list">
          {mostLoaded.map((item) => (
            <div key={item.part}>
              <p className="between muted"><span>{item.part}</span><b>{item.load}%</b></p>
              <progress value={item.load} max={100} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
