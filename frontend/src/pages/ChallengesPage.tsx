import { FormEvent, useEffect, useState } from 'react';
import { Panel, Tier } from '../components/ui';
import api from '../lib/api';

export default function ChallengesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [message, setMessage] = useState('');
  const load = () => api.get('/challenges').then((response) => setItems(response.data));
  useEffect(() => { load(); }, []);
  async function setProgress(event: FormEvent, item: any) {
    event.preventDefault();
    const value = Number(new FormData(event.target as HTMLFormElement).get('progress'));
    const { data } = await api.post(`/challenges/${item.id}/progress`, { progress: value });
    setMessage(data.completed ? `${data.challenge.title} completed. Bonus XP awarded.` : `${data.challenge.title} updated.`);
    load();
  }
  const done = items.filter((item) => item.completed).length;
  return <div className="page"><div className="page-head"><div><p className="eyebrow">XP objectives</p><h1>Challenges</h1></div><span className="score-chip">{done} / {items.length || 0} complete</span></div>{message && <p className="success">{message}</p>}<Panel title="How Progress Works"><p className="muted">Workouts, health logs, readiness checks, wearable syncs, and fitness tests update challenges automatically. Use manual progress when you want to record an off-app result.</p></Panel><div className="grid-2">{items.map((item) => <Panel key={item.id} title={item.challenge.title} action={<Tier value={item.challenge.tier} />}><p>{item.challenge.description}</p><progress value={item.progress} max={item.challenge.target} /><p className="between muted"><span>{item.progress} / {item.challenge.target}</span><span>+{item.challenge.xpReward} XP</span></p>{item.completed ? <p className="challenge-done">Completed</p> : <form className="inline" onSubmit={(event) => setProgress(event, item)}><input name="progress" type="number" min={0} max={item.challenge.target} defaultValue={item.progress} /><button>Update</button></form>}</Panel>)}</div></div>;
}
