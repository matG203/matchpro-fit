import { useEffect, useState } from 'react';
import { CheckCircle2, Lock } from 'lucide-react';
import { Panel, Tier } from '../components/ui';
import api from '../lib/api';

function timeLeft(target?: string) {
  if (!target) return '';
  const ms = Math.max(0, new Date(target).getTime() - Date.now());
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  const days = Math.floor(hours / 24);
  return days ? `${days}d ${hours % 24}h` : `${hours}h ${minutes}m`;
}

export default function ChallengesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [resets, setResets] = useState<any>({});
  const load = () => api.get('/challenges').then((response) => { setItems(response.data.items || response.data); setResets(response.data.resets || {}); });
  useEffect(() => { load(); const timer = setInterval(load, 60_000); return () => clearInterval(timer); }, []);
  const daily = items.filter((item) => item.challenge.period === 'daily');
  const weekly = items.filter((item) => item.challenge.period === 'weekly');
  const campaign = items.filter((item) => item.challenge.period === 'campaign');
  const done = items.filter((item) => item.completed).length;
  const Card = ({ item }: { item: any }) => (
    <Panel title={item.challenge.title} action={<Tier value={item.challenge.tier} />}>
      <p>{item.challenge.description}</p>
      <progress value={item.progress} max={item.challenge.target} />
      <p className="between muted"><span>{item.progress} / {item.challenge.target}</span><span>+{item.challenge.xpReward} XP</span></p>
      <p className={item.completed ? 'challenge-done' : 'muted'}>{item.completed ? <><CheckCircle2 size={16} /> Completed By Verified Activity</> : <><Lock size={16} /> Progress Comes From Programmed Workouts, Sports Sessions, Tests, And Wearable Syncs.</>}</p>
    </Panel>
  );
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Verified XP Objectives</p><h1>Objectives</h1></div><span className="score-chip">{done} / {items.length || 0} Complete</span></div><Panel title="No Manual Claims"><p className="muted">Objectives cannot be typed in by hand. XP is only awarded when MatchFit records a completed programme workout, sport session, fitness test, or Google Health wearable sync.</p></Panel><div className="grid-2"><Panel title="Daily Reset"><strong>{timeLeft(resets.daily)}</strong><p className="muted">Daily objectives reset at midnight UK time.</p></Panel><Panel title="Weekly Reset"><strong>{timeLeft(resets.weekly)}</strong><p className="muted">Weekly objectives run Monday to Sunday and reset at midnight UK time.</p></Panel></div><h2>Daily Objectives</h2><div className="grid-2">{daily.map((item) => <Card item={item} key={item.id} />)}</div><h2>Weekly Objectives</h2><div className="grid-2">{weekly.map((item) => <Card item={item} key={item.id} />)}</div><h2>Campaign Objectives</h2><div className="grid-2">{campaign.map((item) => <Card item={item} key={item.id} />)}</div></div>;
}
