import { useEffect } from ''react'';
import { BrowserRouter, Routes, Route, Navigate } from ''react-router-dom'';
import { useAuthStore } from ''./store/authStore'';
import Layout from ''./components/layout/Layout'';
import LandingPage from ''./pages/LandingPage'';
import LoginPage from ''./pages/LoginPage'';
import RegisterPage from ''./pages/RegisterPage'';
import OnboardingPage from ''./pages/OnboardingPage'';
import DashboardPage from ''./pages/DashboardPage'';
import PlayerCardPage from ''./pages/PlayerCardPage'';
import AvatarPage from ''./pages/AvatarPage'';
import WorkoutPlannerPage from ''./pages/WorkoutPlannerPage'';
import WorkoutsPage from ''./pages/WorkoutsPage'';
import ChallengesPage from ''./pages/ChallengesPage'';
import LeaderboardPage from ''./pages/LeaderboardPage'';
import FriendsPage from ''./pages/FriendsPage'';
import WearablesPage from ''./pages/WearablesPage'';
import HealthPage from ''./pages/HealthPage'';
import RoutinePage from ''./pages/RoutinePage'';
import TestsPage from ''./pages/TestsPage'';
import SettingsPage from ''./pages/SettingsPage'';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, user } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  if (user && !user.profile?.onboardingDone) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

function OnboardingRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { token, fetchMe, loading } = useAuthStore();

  useEffect(() => {
    if (token) fetchMe();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-pitch-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl font-display font-black text-electric-400 mb-2 animate-pulse">MATCHFIT PRO</div>
          <div className="text-gray-400 text-sm">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={token ? <Navigate to="/dashboard" /> : <LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/onboarding" element={<OnboardingRoute><OnboardingPage /></OnboardingRoute>} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/player-card" element={<ProtectedRoute><PlayerCardPage /></ProtectedRoute>} />
          <Route path="/avatar" element={<ProtectedRoute><AvatarPage /></ProtectedRoute>} />
          <Route path="/workout-planner" element={<ProtectedRoute><WorkoutPlannerPage /></ProtectedRoute>} />
          <Route path="/workouts" element={<ProtectedRoute><WorkoutsPage /></ProtectedRoute>} />
          <Route path="/challenges" element={<ProtectedRoute><ChallengesPage /></ProtectedRoute>} />
          <Route path="/leaderboards" element={<ProtectedRoute><LeaderboardPage /></ProtectedRoute>} />
          <Route path="/friends" element={<ProtectedRoute><FriendsPage /></ProtectedRoute>} />
          <Route path="/wearables" element={<ProtectedRoute><WearablesPage /></ProtectedRoute>} />
          <Route path="/health" element={<ProtectedRoute><HealthPage /></ProtectedRoute>} />
          <Route path="/routine" element={<ProtectedRoute><RoutinePage /></ProtectedRoute>} />
          <Route path="/tests" element={<ProtectedRoute><TestsPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
