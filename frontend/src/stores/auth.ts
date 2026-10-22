import { create } from 'zustand';
import type { components } from '../api/schema';

type User = components['schemas']['UserOut'];
export type AuthStatus = 'unknown' | 'authenticated' | 'anonymous';

type AuthState = {
  status: AuthStatus;
  accessToken: string | null;
  user: User | null;
  idleTimeoutS: number;
  /** Why the user was last signed out (backend error code), shown on the sign-in screen. */
  signedOutReason: string | null;
  setSession: (token: string, user: User, idleTimeoutS: number) => void;
  setUser: (user: User) => void;
  signedOut: (reason?: string | null) => void;
  clearReason: () => void;
};

export const useAuth = create<AuthState>((set) => ({
  status: 'unknown',
  accessToken: null,
  user: null,
  idleTimeoutS: 30 * 60,
  signedOutReason: null,
  setSession: (accessToken, user, idleTimeoutS) =>
    set({ status: 'authenticated', accessToken, user, idleTimeoutS, signedOutReason: null }),
  setUser: (user) => set({ user }),
  signedOut: (reason = null) =>
    set({ status: 'anonymous', accessToken: null, user: null, signedOutReason: reason }),
  clearReason: () => set({ signedOutReason: null }),
}));
