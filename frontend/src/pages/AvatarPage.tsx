import { Lock } from 'lucide-react';
import { useEffect, useState } from 'react';
import PlayerFigure from '../components/avatar/PlayerFigure';
import { AvatarMark, Panel } from '../components/ui';
import api from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function AvatarPage() {
  const setUser = useAuthStore((state) => state.setUser);
  const [data, setData] = useState<any>();
  useEffect(() => { api.get('/avatar').then((response) => setData(response.data)); }, []);
  async function equip(avatarId: string) {
    const { data: response } = await api.put('/avatar', { avatarId });
    setUser(response.user); setData({ ...data, equipped: avatarId });
  }
  async function choose(part: string, value: string) {
    const { data: response } = await api.put('/avatar', { [part]: value });
    setData((current: any) => ({ ...current, loadout: response.loadout }));
  }
  const equipped = data?.avatars.find((avatar: any) => avatar.id === data.equipped);
  const next = data?.avatars.find((avatar: any) => !avatar.unlocked);
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Player creator</p><h1>Customise Player</h1></div>{equipped && <span className="score-chip"><AvatarMark id={equipped.id} /> {equipped.name}</span>}</div>{data && <Panel title="Level And Objective Unlocks"><div className="stat-grid"><div className="stat"><strong>{data.level}</strong><small>Current level</small></div><div className="stat"><strong>{data.xp}</strong><small>Total XP</small></div><div className="stat"><strong>{data.level * 500 - data.xp}</strong><small>XP to next level</small></div></div><p className="muted" style={{ marginTop: '1rem' }}>Some items unlock through levels. Others are earned from daily, weekly, and campaign objectives.</p></Panel>}<div className="customizer-grid"><Panel title="Player Preview"><div className="player-stage"><PlayerFigure loadout={data?.loadout} large /></div><p className="muted">Your face, features, kit, boots, extras, aura, and pose appear inside your player card.</p></Panel><Panel title="Face, Features And Gear">{data && <div className="customizer-controls">{Object.entries(data.parts).map(([part, options]: any) => <div key={part}><h3>{part}</h3><div className="choice-row">{options.map((option: any) => <button className={`choice ${data.loadout?.[part] === option.id ? 'selected' : ''}`} key={option.id} disabled={!option.unlocked} onClick={() => choose(part, option.id)}><span>{option.name}</span><small>{option.unlocked ? option.rewardUnlocked ? 'Objective Reward' : 'Use' : <><Lock size={12} /> Level {option.level}</>}</small></button>)}</div></div>)}</div>}</Panel></div>{next && <Panel title="Next Profile Crest"><p className="between"><span>{next.name}</span><strong>Level {next.level}</strong></p><progress value={data.avatars.filter((avatar: any) => avatar.unlocked).length} max={data.avatars.length} /></Panel>}<Panel title="Profile Crests"><p className="muted">Crests appear by your name on leaderboards and menus. They unlock separately from the player figure.</p><div className="avatar-grid">{data?.avatars.map((avatar: any) => <button className={`avatar-card ${avatar.unlocked ? '' : 'locked'} ${data.equipped === avatar.id ? 'secondary' : ''}`} key={avatar.id} disabled={!avatar.unlocked} onClick={() => equip(avatar.id)}><AvatarMark id={avatar.id} /><strong>{avatar.name}</strong><small>{avatar.unlocked ? data.equipped === avatar.id ? 'Equipped' : 'Equip' : <><Lock size={13} /> Level {avatar.level}</>}</small></button>)}</div></Panel></div>;
}
