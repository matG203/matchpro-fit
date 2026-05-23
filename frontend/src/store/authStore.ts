import { create } from 'zustand';
import api from '../lib/api';

export type MatchUser = {
  id: string;
  email: string;
  username: string;
  displayName?: string | null;
  position?: string | null;
  teamName?: string | null;
  age?: number | null;
  height?: number | null;
  weight?: number | null;
  xp: number;
  level: number;
  tier: string;
  avatarId?: string | null;
  matchReadiness: number;
  isAdmin?: boolean;
};

type AuthState = {
  token: string | null;
  user: MatchUser | null;
  checking: boolean;
  onboardingComplete: boolean;
  register: (email: string, username: string, password: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  hydrate: () => Promise<void>;
  completeOnboarding: (payload: Record<string, unknown>) => Promise<void>;
  logout: () => void;
  setUser: (user: MatchUser) => void;
};

const saveToken = (token: string) => localStorage.setItem('matchfit-token', token);

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('matchfit-token'),
  user: null,
  checking: Boolean(localStorage.getItem('matchfit-token')),
  onboardingComplete: false,
  async register(email, username, password) {
    const { data } = await api.post('/auth/register', { email, username, password });
    saveToken(data.token);
    set({ token: data.token, user: data.user, onboardingComplete: false, checking: false });
  },
  async login(email, password) {
    const { data } = await api.post('/auth/login', { email, password });
    saveToken(data.token);
    const me = await api.get('/auth/me', { headers: { Authorization: `Bearer ${data.token}` } });
      set({ token: data.token, user: { ...me.data.user, isAdmin: me.data.isAdmin }, onboardingComplete: me.data.onboardingComplete, checking: false });
  },
  async hydrate() {
    try {
      const { data } = await api.get('/auth/me');
      set({ user: { ...data.user, isAdmin: data.isAdmin }, onboardingComplete: data.onboardingComplete, checking: false });
    } catch {
      localStorage.removeItem('matchfit-token');
      set({ token: null, user: null, checking: false, onboardingComplete: false });
    }
  },
  async completeOnboarding(payload) {
    const { data } = await api.post('/onboarding', payload);
    set({ user: data, onboardingComplete: true });
  },
  logout() {
    localStorage.removeItem('matchfit-token');
    set({ token: null, user: null, onboardingComplete: false, checking: false });
  },
  setUser: (user) => set({ user }),
}));
