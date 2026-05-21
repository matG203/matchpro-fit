import { AvatarMark, Tier } from '../ui';

type Card = {
  overall: number;
  pace: number;
  shooting: number;
  passing: number;
  dribbling: number;
  defending: number;
  physical: number;
  user?: { displayName?: string | null; username: string; tier: string; avatarId?: string | null; position?: string | null };
};

export default function PlayerCard({ card }: { card: Card }) {
  const stats = [['PAC', card.pace], ['SHO', card.shooting], ['PAS', card.passing], ['DRI', card.dribbling], ['DEF', card.defending], ['PHY', card.physical]];
  const tier = card.user?.tier || 'Bronze';
  return (
    <article className={`player-card card-${tier.toLowerCase()}`}>
      <div className="card-top"><strong>{card.overall}</strong><div>{card.user?.position || 'PLAYER'}<Tier value={tier} /></div></div>
      <AvatarMark id={card.user?.avatarId} />
      <h2>{card.user?.displayName || card.user?.username || 'MatchFit Player'}</h2>
      <dl>{stats.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    </article>
  );
}
