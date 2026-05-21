import { useEffect, useState } from 'react';
import { AvatarMark, Panel, Tier } from '../components/ui';
import api from '../lib/api';

function Board({ rows }: { rows: any[] }) {
  return <ul className="list">{rows.map((row, index) => <li className="table-row" key={row.id}><b>#{index + 1}</b><span className="inline"><AvatarMark id={row.avatarId} /><span>{row.displayName || row.username}<br /><small>Level {row.level}</small></span></span><Tier value={row.tier} /><strong>{row.xp} XP</strong></li>)}</ul>;
}
export default function LeaderboardPage() {
  const [global, setGlobal] = useState<any[]>([]);
  const [friends, setFriends] = useState<any[]>([]);
  useEffect(() => { api.get('/leaderboard').then((response) => setGlobal(response.data)); api.get('/leaderboard/friends').then((response) => setFriends(response.data)); }, []);
  return <div className="page"><h1>Leaderboard</h1><div className="grid-2"><Panel title="Global"><Board rows={global} /></Panel><Panel title="Friends"><Board rows={friends} /></Panel></div></div>;
}
