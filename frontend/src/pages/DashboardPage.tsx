import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PlayerCard from '../components/card/PlayerCard';
import ReadinessRing from '../components/dashboard/ReadinessRing';
import XPBar from '../components/dashboard/XPBar';
import { Empty, Panel, Tier } from '../components/ui';
import api from '../lib/api';

export default function DashboardPage() {
  const [data, setData] = useState<any>();
  const load = () => api.get('/dashboard').then((response) => setData(response.data));
  useEffect(() => { load(); }, []);
  async function markRead(id: string) {
    await api.put(`/notifications/${id}/read`);
    setData((current: any) => ({ ...current, notifications: current.notifications.map((note: any) => note.id === id ? { ...note, read: true } : note) }));
  }
  if (!data) return <div className="splash">Loading</div>;
  const unread = data.notifications.filter((note: any) => !note.read).length;
  return (
    <div className="page">
      <div className="page-head"><div><p className="eyebrow">Level {data.user.level}</p><h1>{data.user.displayName || data.user.username}</h1></div><Tier value={data.user.tier} /></div>
      <div className="grid-2">
        <Panel title="Match Readiness"><ReadinessRing score={data.readiness.score} /><div className="stat-grid">{Object.entries(data.readiness.factors).map(([label, value]) => <div className="stat" key={label}><strong>{String(value)}%</strong><small>{label}</small></div>)}</div></Panel>
        <Panel title="Level Progress" action={<Link className="button secondary" to="/workout-planner">Log workout</Link>}><XPBar xp={data.user.xp} floor={data.xp.levelFloorXp} next={data.xp.nextLevelXp} /><div className="stat-grid" style={{ marginTop: '1rem' }}><div className="stat"><strong>{data.stats.totalXp}</strong><small>Total XP</small></div><div className="stat"><strong>{data.stats.workoutsThisWeek}</strong><small>Workouts this week</small></div><div className="stat"><strong>{data.stats.streak}</strong><small>Day streak</small></div></div></Panel>
      </div>
      <div className="grid-2">
        <Panel title="Recent Workouts">{data.recentWorkouts.length ? <ul className="list">{data.recentWorkouts.map((workout: any) => <li className="between" key={workout.id}><span><b>{workout.type}</b><br /><small>{workout.duration} min {workout.intensity}</small></span><b>+{workout.xpEarned} XP</b></li>)}</ul> : <Empty>Your first session will land here.</Empty>}</Panel>
        <Panel title="Notifications" action={unread ? <span className="score-chip">{unread} unread</span> : undefined}>{data.notifications.length ? <ul className="list">{data.notifications.map((note: any) => <li className={`notification ${note.read ? 'read' : ''}`} key={note.id}><span>{note.message}<br /><small>{new Date(note.createdAt).toLocaleDateString()}</small></span>{!note.read && <button className="ghost compact" onClick={() => markRead(note.id)}>Mark read</button>}</li>)}</ul> : <Empty>No new notifications.</Empty>}</Panel>
      </div>
      <Panel title="Player Card"><PlayerCard card={{ ...data.user.playerCard, user: data.user }} /></Panel>
    </div>
  );
}
