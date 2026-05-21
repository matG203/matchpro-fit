import { FormEvent, useEffect, useState } from 'react';
import PlayerCard from '../components/card/PlayerCard';
import { Panel } from '../components/ui';
import api from '../lib/api';

const keys = ['pace', 'shooting', 'passing', 'dribbling', 'defending', 'physical'];
export default function PlayerCardPage() {
  const [card, setCard] = useState<any>();
  useEffect(() => { api.get('/playerCard').then((response) => setCard(response.data)); }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    const { data } = await api.put('/playerCard', Object.fromEntries(keys.map((key) => [key, Number(card[key])])));
    setCard({ ...card, ...data });
  }
  return <div className="page"><h1>Player Card</h1>{card && <div className="grid-2"><PlayerCard card={card} /><Panel title="Tune Stats"><form className="form-grid" onSubmit={save}>{keys.map((key) => <div key={key}><label>{key}</label><input type="number" min={1} max={99} value={card[key]} onChange={(e) => setCard({ ...card, [key]: +e.target.value })} /></div>)}<button>Save card</button></form></Panel></div>}</div>;
}
