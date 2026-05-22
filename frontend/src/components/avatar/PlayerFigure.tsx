export type PlayerLoadout = {
  skin?: string;
  face?: string;
  hair?: string;
  kit?: string;
  accessory?: string;
  boots?: string;
  aura?: string;
  pose?: string;
};

export default function PlayerFigure({ loadout, large = false }: { loadout?: PlayerLoadout | null; large?: boolean }) {
  const player = loadout || {};
  const classes = [
    'player-figure',
    large ? 'large' : '',
    `skin-${player.skin || 'warm'}`,
    `face-${player.face || 'focused'}`,
    `hair-${player.hair || 'fade'}`,
    `kit-${player.kit || 'academy'}`,
    `accessory-${player.accessory || 'none'}`,
    `boots-${player.boots || 'black'}`,
    `aura-${player.aura || 'none'}`,
    `pose-${player.pose || 'ready'}`,
  ].filter(Boolean).join(' ');
  return <div className={classes} aria-label="Custom player avatar"><i className="figure-aura" /><i className="figure-shadow" /><i className="figure-head"><b className="figure-eye left" /><b className="figure-eye right" /><b className="figure-mouth" /><b className="figure-face-detail" /></i><i className="figure-hair" /><i className="figure-shirt" /><i className="figure-arm left" /><i className="figure-arm right" /><i className="figure-shorts" /><i className="figure-leg left" /><i className="figure-leg right" /><i className="figure-boot left" /><i className="figure-boot right" /><i className="figure-accessory" /></div>;
}
