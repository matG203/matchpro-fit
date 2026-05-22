import { useEffect } from 'react';
import { Activity, Award, CalendarDays, Dumbbell, HeartPulse, Home, LogOut, Medal, Settings, Shirt, Users, Watch, Zap } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import { AvatarMark, Tier } from '../ui';
import api from '../../lib/api';
import { useAuthStore } from '../../store/authStore';

const links = [
  ['/dashboard', 'Dashboard', Home],
  ['/player-card', 'Player Card', Shirt],
  ['/avatar', 'Avatars', Award],
  ['/workout-planner', 'Log Workout', Dumbbell],
  ['/workouts', 'History', Activity],
  ['/challenges', 'Challenges', Zap],
  ['/leaderboard', 'Leaderboard', Medal],
  ['/friends', 'Friends', Users],
  ['/health', 'Health', HeartPulse],
  ['/routine', 'Routine', CalendarDays],
  ['/wearables', 'Wearables', Watch],
  ['/tests', 'Tests', Activity],
  ['/settings', 'Settings', Settings],
] as const;

export default function Layout() {
  const { user, logout } = useAuthStore();
  useEffect(() => {
    api.get('/settings').then(({ data }) => { document.documentElement.dataset.theme = data.theme || 'dark'; });
  }, []);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/dashboard" className="brand">MatchFit <b>Pro</b></NavLink>
        <div className="profile-chip"><AvatarMark id={user?.avatarId} /><div><strong>{user?.displayName || user?.username}</strong><Tier value={user?.tier || 'Bronze'} /></div></div>
        <nav>{links.map(([to, label, Icon]) => <NavLink key={to} to={to}><Icon size={18} /><span>{label}</span></NavLink>)}</nav>
        <button className="ghost logout" onClick={logout}><LogOut size={18} /> Sign out</button>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  );
}
