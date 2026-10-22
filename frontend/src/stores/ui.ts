import { create } from 'zustand';

const COLLAPSE_KEY = 'iv.sidebarCollapsed';

function read(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v === '1';
  } catch {
    return fallback;
  }
}

export type LinkState = 'none' | 'connecting' | 'open' | 'lost';
export type CameraState = 'off' | 'on' | 'blocked';

type UiState = {
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  /** Realtime (WebSocket) link state, set by live screens from Phase 3. */
  link: LinkState;
  camera: CameraState;
  /** Set by live/capture screens of an active incident: heartbeat continuously. */
  keepAlive: boolean;
  toggleSidebar: () => void;
  setMobileNav: (open: boolean) => void;
  setLink: (s: LinkState) => void;
  setCamera: (s: CameraState) => void;
  setKeepAlive: (v: boolean) => void;
};

export const useUi = create<UiState>((set, get) => ({
  sidebarCollapsed: read(COLLAPSE_KEY, false),
  mobileNavOpen: false,
  link: 'none',
  camera: 'off',
  keepAlive: false,
  toggleSidebar: () => {
    const next = !get().sidebarCollapsed;
    try {
      localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0');
    } catch {
      /* ignore */
    }
    set({ sidebarCollapsed: next });
  },
  setMobileNav: (mobileNavOpen) => set({ mobileNavOpen }),
  setLink: (link) => set({ link }),
  setCamera: (camera) => set({ camera }),
  setKeepAlive: (keepAlive) => set({ keepAlive }),
}));
