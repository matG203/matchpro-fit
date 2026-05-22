import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PlayerCard from '../components/card/PlayerCard';
import ReadinessRing from '../components/dashboard/ReadinessRing';
import XPBar from '../components/dashboard/XPBar';
import { Empty, Panel, Tier } from '../components/ui';
import api, { errorMessage } from '../lib/api';

export default function DashboardPage() {
  const [data, setData] = useState<any>();
  const [error, setError] = useState('');
  const load = () => api.get('/dashboard').then((response) => setData(response.data)).catch((requestError) => setError(errorMessage(requestError)));
  useEffect(() => { load(); }, []);
  async function markRead(id: string) {
    await api.put(`/notifications/${id}/read`);
    setData((current: any) => ({ ...current, notifications: (current.notifications || []).map((note: any) => note.id === id ? { ...note, read: true } : note) }));
  }
  if (error) return <div className="page"><Panel title="Dashboard unavailable"><p className="error">{error}</p><button onClick={() => { setError(''); load(); }}>Try again</button></Panel></div>;
  if (!data) return <div className="splash">Loading</div>;
  const user = data.user || {};
  const notifications = Array.isArray(data.notifications) ? data.notifications : [];
  const recentWorkouts = Array.isArray(data.recentWorkouts) ? data.recentWorkouts : [];
  const readiness = data.readiness || { score: user.matchReadiness || 0, factors: {} };
  const factors = readiness.factors || {};
  const xp = data.xp || { levelFloorXp: Math.max(0, ((user.level || 1) - 1) * 500), nextLevelXp: (user.level || 1) * 500 };
  const stats = data.stats || { totalXp: user.xp || 0, workoutsThisWeek: 0, streak: 0 };
  const unread = notifications.filter((note: any) => !note.read).length;
  return (
    <div className="page">
      <div className="page-head"><div><p className="eyebrow">Level {user.level || 1}</p><h1>{user.displayName || user.username || 'MatchFit Player'}</h1></div><Tier value={user.tier || 'Bronze'} /></div>
      <div className="grid-2">
        <Panel title="Match Readiness"><ReadinessRing score={readiness.score || 0} /><div className="stat-grid">{Object.entries(factors).map(([label, value]) => <div className="stat" key={label}><strong>{String(value)}%</strong><small>{label}</small></div>)}</div></Panel>
        <Panel title="Level Progress" action={<Link className="button secondary" to="/workout-planner">Log workout</Link>}><XPBar xp={user.xp || 0} floor={xp.levelFloorXp} next={xp.nextLevelXp} /><div className="stat-grid" style={{ marginTop: '1rem' }}><div className="stat"><strong>{stats.totalXp}</strong><small>Total XP</small></div><div className="stat"><strong>{stats.workoutsThisWeek}</strong><small>Workouts this week</small></div><div className="stat"><strong>{stats.streak}</strong><small>Day streak</small></div></div></Panel>
      </div>
      <div className="grid-2">
        <Panel title="Recent Workouts">{recentWorkouts.length ? <ul className="list">{recentWorkouts.map((workout: any) => <li className="between" key={workout.id}><span><b>{workout.type}</b><br /><small>{workout.duration} min {workout.intensity}</small></span><b>+{workout.xpEarned} XP</b></li>)}</ul> : <Empty>Your first session will land here.</Empty>}</Panel>
        <Panel title="Notifications" action={unread ? <span className="score-chip">{unread} unread</span> : undefined}>{notifications.length ? <ul className="list">{notifications.map((note: any) => <li className={`notification ${note.read ? 'read' : ''}`} key={note.id}><span>{note.message}<br /><small>{new Date(note.createdAt).toLocaleDateString()}</small></span>{!note.read && <button className="ghost compact" onClick={() => markRead(note.id)}>Mark read</button>}</li>)}</ul> : <Empty>No new notifications.</Empty>}</Panel>
      </div>
      <Panel title="Player Card"><PlayerCard card={{ ...user.playerCard, user }} /></Panel>
    </div>
  );
}
