import { useEffect } from 'react';
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import AppErrorBoundary from './components/AppErrorBoundary';
import Layout from './components/layout/Layout';
import { useAuthStore } from './store/authStore';
import AvatarPage from './pages/AvatarPage';
import AdminPage from './pages/AdminPage';
import ChallengesPage from './pages/ChallengesPage';
import CampaignPage from './pages/CampaignPage';
import DashboardPage from './pages/DashboardPage';
import FriendsPage from './pages/FriendsPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import HealthPage from './pages/HealthPage';
import LandingPage from './pages/LandingPage';
import LeaderboardPage from './pages/LeaderboardPage';
import LoginPage from './pages/LoginPage';
import OnboardingPage from './pages/OnboardingPage';
import PlayerCardPage from './pages/PlayerCardPage';
import RegisterPage from './pages/RegisterPage';
import RoutinePage from './pages/RoutinePage';
import SettingsPage from './pages/SettingsPage';
import TestsPage from './pages/TestsPage';
import WearablesPage from './pages/WearablesPage';
import WorkoutPlannerPage from './pages/WorkoutPlannerPage';
import WorkoutsPage from './pages/WorkoutsPage';

function SessionGate() {
  const { token, checking, onboardingComplete } = useAuthStore();
  if (checking) return <div className="splash">MATCHFIT PRO</div>;
  if (!token) return <Navigate to="/login" replace />;
  if (!onboardingComplete) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}

function OnboardingGate() {
  const { token, checking, onboardingComplete } = useAuthStore();
  if (checking) return <div className="splash">MATCHFIT PRO</div>;
  if (!token) return <Navigate to="/login" replace />;
  if (onboardingComplete) return <Navigate to="/dashboard" replace />;
  return <OnboardingPage />;
}

export default function App() {
  const { token, hydrate } = useAuthStore();
  useEffect(() => { if (token) hydrate(); }, [token, hydrate]);

  return (
    <BrowserRouter>
      <AppErrorBoundary><Routes>
        <Route path="/" element={token ? <Navigate to="/dashboard" replace /> : <LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/onboarding" element={<OnboardingGate />} />
        <Route element={<SessionGate />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/player-card" element={<PlayerCardPage />} />
            <Route path="/avatar" element={<AvatarPage />} />
            <Route path="/workout-planner" element={<WorkoutPlannerPage />} />
            <Route path="/workouts" element={<WorkoutsPage />} />
            <Route path="/challenges" element={<ChallengesPage />} />
            <Route path="/campaign" element={<CampaignPage />} />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
            <Route path="/friends" element={<FriendsPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route path="/routine" element={<RoutinePage />} />
            <Route path="/wearables" element={<WearablesPage />} />
            <Route path="/tests" element={<TestsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes></AppErrorBoundary>
    </BrowserRouter>
  );
}
