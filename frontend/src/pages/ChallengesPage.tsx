import { FormEvent, useEffect, useState } from 'react';
import { Panel, Tier } from '../components/ui';
import api from '../lib/api';

export default function ChallengesPage() {
  const [items, setItems] = useState<any[]>([]);
  const load = () => api.get('/challenges').then((response) => setItems(response.data));
  useEffect(() => { load(); }, []);
  async function setProgress(event: FormEvent, item: any) {
    event.preventDefault();
    const value = Number(new FormData(event.target as HTMLFormElement).get('progress'));
    await api.post(`/challenges/${item.id}/progress`, { progress: value }); load();
  }
  return <div className="page"><h1>Challenges</h1><div className="grid-2">{items.map((item) => <Panel key={item.id} title={item.challenge.title} action={<Tier value={item.challenge.tier} />}><p>{item.challenge.description}</p><progress value={item.progress} max={item.challenge.target} /><p className="between muted"><span>{item.progress} / {item.challenge.target}</span><span>+{item.challenge.xpReward} XP</span></p>{!item.completed && <form className="inline" onSubmit={(event) => setProgress(event, item)}><input name="progress" type="number" min={0} max={item.challenge.target} defaultValue={item.progress} /><button>Update</button></form>}</Panel>)}</div></div>;
}
