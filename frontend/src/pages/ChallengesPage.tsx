import { useEffect, useState } from 'react';
import { CheckCircle2, Lock } from 'lucide-react';
import { Panel, Tier } from '../components/ui';
import api from '../lib/api';

export default function ChallengesPage() {
  const [items, setItems] = useState<any[]>([]);
  const load = () => api.get('/challenges').then((response) => setItems(response.data));
  useEffect(() => { load(); }, []);
  const daily = items.filter((item) => item.challenge.period === 'daily');
  const weekly = items.filter((item) => item.challenge.period === 'weekly');
  const done = items.filter((item) => item.completed).length;
  const Card = ({ item }: { item: any }) => (
    <Panel title={item.challenge.title} action={<Tier value={item.challenge.tier} />}>
      <p>{item.challenge.description}</p>
      <progress value={item.progress} max={item.challenge.target} />
      <p className="between muted"><span>{item.progress} / {item.challenge.target}</span><span>+{item.challenge.xpReward} XP</span></p>
      <p className={item.completed ? 'challenge-done' : 'muted'}>{item.completed ? <><CheckCircle2 size={16} /> Completed by verified activity</> : <><Lock size={16} /> Progress comes from programmed workouts, sports sessions, tests, and wearable syncs.</>}</p>
    </Panel>
  );
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Verified XP objectives</p><h1>Objectives</h1></div><span className="score-chip">{done} / {items.length || 0} complete</span></div><Panel title="No Manual Claims"><p className="muted">Objectives cannot be typed in by hand. XP is only awarded when MatchFit records a completed programme workout, sport session, fitness test, or Google Health wearable sync.</p></Panel><h2>Daily</h2><div className="grid-2">{daily.map((item) => <Card item={item} key={item.id} />)}</div><h2>Weekly</h2><div className="grid-2">{weekly.map((item) => <Card item={item} key={item.id} />)}</div></div>;
}
