import { create } from ''zustand'';
import api from ''../lib/api'';

interface User {
  id: string;
  email: string;
  username: string;
  friendCode: string;
  profile?: {
    displayName: string;
    onboardingDone: boolean;
    position: string;
    footballLevel: string;
  };
  playerCard?: {
    overall: number;
    tier: string;
    totalXp: number;
    xpLevel: number;
  };
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem(''token''),
  loading: false,

  login: async (email, password) => {
    const { data } = await api.post(''/auth/login'', { email, password });
    localStorage.setItem(''token'', data.token);
    set({ token: data.token });
    const me = await api.get(''/auth/me'');
    set({ user: me.data });
  },

  register: async (email, username, password) => {
    const { data } = await api.post(''/auth/register'', { email, username, password });
    localStorage.setItem(''token'', data.token);
    set({ token: data.token });
    const me = await api.get(''/auth/me'');
    set({ user: me.data });
  },

  logout: () => {
    localStorage.removeItem(''token'');
    set({ user: null, token: null });
  },

  fetchMe: async () => {
    try {
      set({ loading: true });
      const { data } = await api.get(''/auth/me'');
      set({ user: data, loading: false });
    } catch {
      localStorage.removeItem(''token'');
      set({ user: null, token: null, loading: false });
    }
  },
}));
