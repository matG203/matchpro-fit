import { Lock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AvatarMark, Panel } from '../components/ui';
import api from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function AvatarPage() {
  const setUser = useAuthStore((state) => state.setUser);
  const [data, setData] = useState<any>();
  useEffect(() => { api.get('/avatar').then((response) => setData(response.data)); }, []);
  async function equip(avatarId: string) {
    const response = await api.put('/avatar', { avatarId });
    setUser(response.data); setData({ ...data, equipped: avatarId });
  }
  const equipped = data?.avatars.find((avatar: any) => avatar.id === data.equipped);
  const next = data?.avatars.find((avatar: any) => !avatar.unlocked);
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Identity unlocks</p><h1>Avatars</h1></div>{equipped && <span className="score-chip"><AvatarMark id={equipped.id} /> {equipped.name}</span>}</div>{next && <Panel title="Next Unlock"><p className="between"><span>{next.name}</span><strong>{next.xp} XP</strong></p><progress value={data.avatars.filter((avatar: any) => avatar.unlocked).length} max={data.avatars.length} /></Panel>}<Panel title="Unlocked by XP"><div className="avatar-grid">{data?.avatars.map((avatar: any) => <button className={`avatar-card ${avatar.unlocked ? '' : 'locked'} ${data.equipped === avatar.id ? 'secondary' : ''}`} key={avatar.id} disabled={!avatar.unlocked} onClick={() => equip(avatar.id)}><AvatarMark id={avatar.id} /><strong>{avatar.name}</strong><small>{avatar.unlocked ? data.equipped === avatar.id ? 'Equipped' : 'Equip' : <><Lock size={13} /> {avatar.xp} XP</>}</small></button>)}</div></Panel></div>;
}
