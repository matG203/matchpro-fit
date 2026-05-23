import { useEffect, useState } from 'react';
import { CheckCircle2, Gift, Lock } from 'lucide-react';
import { Panel, Tier } from '../components/ui';
import api from '../lib/api';

export default function CampaignPage() {
  const [sections, setSections] = useState<any[]>([]);
  useEffect(() => { api.get('/campaign').then((response) => setSections(response.data.sections)); }, []);
  const total = sections.reduce((sum, section) => sum + section.challenges.length, 0);
  const done = sections.reduce((sum, section) => sum + section.challenges.filter((item: any) => item.completed).length, 0);
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Permanent Progression</p><h1>Campaign</h1></div><span className="score-chip">{done} / {total} Complete</span></div><Panel title="How Campaigns Work"><p className="muted">Campaign objectives do not reset. Each section pushes a different part of your football fitness, and completed sections usually award a custom player item plus a large XP bonus.</p></Panel>{sections.map((section) => <div className="stack" key={section.name}><div className="page-head"><h2>{section.name}</h2>{section.reward && <span className="score-chip"><Gift size={16} /> Section Reward: {section.reward.name} + {section.reward.xp} XP</span>}</div><div className="grid-2">{section.challenges.map((item: any) => <Panel key={item.id} title={item.challenge.title} action={<Tier value={item.challenge.tier} />}><p>{item.challenge.description}</p><progress value={item.progress} max={item.challenge.target} /><p className="between muted"><span>{item.progress} / {item.challenge.target}</span><span>{item.challenge.rewardType === 'cosmetic' ? 'Item Reward' : `+${item.challenge.xpReward} XP`}</span></p><p className={item.completed ? 'challenge-done' : 'muted'}>{item.completed ? <><CheckCircle2 size={16} /> Complete</> : <><Lock size={16} /> Progress comes from verified activity.</>}</p></Panel>)}</div></div>)}</div>;
}
