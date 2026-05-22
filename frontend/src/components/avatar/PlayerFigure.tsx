export type PlayerLoadout = {
  skin?: string;
  hair?: string;
  kit?: string;
  accessory?: string;
  pose?: string;
};

export default function PlayerFigure({ loadout = {}, large = false }: { loadout?: PlayerLoadout; large?: boolean }) {
  const classes = [
    'player-figure',
    large ? 'large' : '',
    `skin-${loadout.skin || 'warm'}`,
    `hair-${loadout.hair || 'fade'}`,
    `kit-${loadout.kit || 'academy'}`,
    `accessory-${loadout.accessory || 'none'}`,
    `pose-${loadout.pose || 'ready'}`,
  ].filter(Boolean).join(' ');
  return <div className={classes} aria-label="Custom player avatar"><i className="figure-shadow" /><i className="figure-head" /><i className="figure-hair" /><i className="figure-shirt" /><i className="figure-arm left" /><i className="figure-arm right" /><i className="figure-shorts" /><i className="figure-leg left" /><i className="figure-leg right" /><i className="figure-boot left" /><i className="figure-boot right" /><i className="figure-accessory" /></div>;
}
