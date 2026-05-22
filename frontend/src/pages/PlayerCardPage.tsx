import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PlayerCard from '../components/card/PlayerCard';
import { Panel } from '../components/ui';
import api from '../lib/api';

const labels = [['pace', 'Pace'], ['shooting', 'Shooting'], ['passing', 'Passing'], ['dribbling', 'Dribbling'], ['defending', 'Defending'], ['physical', 'Physical']];
export default function PlayerCardPage() {
  const [card, setCard] = useState<any>();
  useEffect(() => { api.get('/playerCard').then((response) => setCard(response.data)); }, []);
  return <div className="page"><div className="page-head"><div><p className="eyebrow">Earn ratings</p><h1>Player Card</h1></div><div className="actions"><Link className="button" to="/workout-planner">Train</Link><Link className="button secondary" to="/tests">Test</Link></div></div>{card && <div className="grid-2"><PlayerCard card={card} /><div className="stack"><Panel title="Rating Breakdown"><div className="stack">{labels.map(([key, label]) => <div key={key}><p className="between muted"><span>{label}</span><b>{card[key]}</b></p><progress value={card[key]} max={99} /></div>)}</div></Panel><Panel title="Progression"><div className="stat-grid"><div className="stat"><strong>{card.progression.workouts}</strong><small>Training sessions</small></div><div className="stat"><strong>{card.progression.tests}</strong><small>Test blocks</small></div><div className="stat"><strong>{card.overall}</strong><small>Overall rating</small></div></div><p style={{ marginTop: '1rem' }}>{card.progression.nextFocus}</p></Panel></div></div>}</div>;
}
