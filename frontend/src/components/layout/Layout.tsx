import { Outlet, NavLink, useNavigate } from ''react-router-dom'';
import {
  LayoutDashboard, CreditCard, User, Dumbbell, Trophy,
  Users, Activity, Heart, ClipboardList, FlaskConical,
  Settings, Watch, Zap, Menu, X, Bell
} from ''lucide-react'';
import { useState } from ''react'';
import { useAuthStore } from ''../../store/authStore'';

const navItems = [
  { to: ''/dashboard'', icon: LayoutDashboard, label: ''Home'' },
  { to: ''/player-card'', icon: CreditCard, label: ''Card'' },
  { to: ''/workout-planner'', icon: Dumbbell, label: ''Train'' },
  { to: ''/challenges'', icon: Trophy, label: ''Goals'' },
  { to: ''/leaderboards'', icon: Zap, label: ''Ranks'' },
];

const moreItems = [
  { to: ''/avatar'', icon: User, label: ''Avatar'' },
  { to: ''/workouts'', icon: Activity, label: ''History'' },
  { to: ''/health'', icon: Heart, label: ''Health'' },
  { to: ''/routine'', icon: ClipboardList, label: ''Routine'' },
  { to: ''/tests'', icon: FlaskConical, label: ''Tests'' },
  { to: ''/friends'', icon: Users, label: ''Friends'' },
  { to: ''/wearables'', icon: Watch, label: ''Wearables'' },
  { to: ''/settings'', icon: Settings, label: ''Settings'' },
];

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { logout, user } = useAuthStore();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-pitch-900 flex flex-col max-w-md mx-auto relative">
      {/* Top bar */}
      <div className="sticky top-0 z-40 bg-pitch-900/95 backdrop-blur border-b border-pitch-700 px-4 py-3 flex items-center justify-between">
        <div className="font-display font-black text-xl tracking-wider text-white">
          MATCH<span className="text-electric-400">FIT</span>
          <span className="text-xs text-gray-500 font-body font-normal ml-1">PRO</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(''/dashboard'')}
            className="relative p-2 rounded-lg bg-pitch-700 text-gray-400 hover:text-white transition-colors"
          >
            <Bell size={18} />
          </button>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="p-2 rounded-lg bg-pitch-700 text-gray-400 hover:text-white transition-colors"
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {/* Slide-out menu */}
      {menuOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMenuOpen(false)} />
          <div className="absolute right-0 top-0 h-full w-72 bg-pitch-800 border-l border-pitch-600 p-4 flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="font-display font-bold text-white">{user?.profile?.displayName || user?.username}</div>
                <div className="text-xs text-gray-400">@{user?.username}</div>
              </div>
              <button onClick={() => setMenuOpen(false)} className="p-2 rounded-lg bg-pitch-700 text-gray-400">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 space-y-1">
              {moreItems.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm font-medium ${
                      isActive ? ''bg-electric-500/20 text-electric-400'' : ''text-gray-300 hover:bg-pitch-700 hover:text-white''
                    }`
                  }
                >
                  <Icon size={18} />
                  {label}
                </NavLink>
              ))}
            </div>
            <button
              onClick={() => { logout(); navigate(''/''); setMenuOpen(false); }}
              className="mt-4 w-full text-left px-3 py-2.5 rounded-lg text-red-400 hover:bg-red-400/10 transition-colors text-sm font-medium"
            >
              Sign Out
            </button>
          </div>
        </div>
      )}

      {/* Page content */}
      <main className="flex-1 pb-20 overflow-y-auto">
        <Outlet />
      </main>

      {/* Bottom nav */}
      <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md bg-pitch-900/95 backdrop-blur border-t border-pitch-700 px-2 py-1 flex justify-around z-40">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `nav-item ${isActive ? ''active'' : ''''}`
            }
          >
            <Icon size={20} />
            <span className="text-[10px] font-medium">{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
