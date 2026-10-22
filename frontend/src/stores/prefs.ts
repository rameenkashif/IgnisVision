import { create } from 'zustand';

/** Per-device preferences (not security-relevant, so localStorage is fine). */
const KEY = 'iv.prefs';

type Prefs = { voiceAlerts: boolean; soundAlerts: boolean };
const DEFAULTS: Prefs = { voiceAlerts: true, soundAlerts: true };

function load(): Prefs {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) ?? '{}') };
  } catch {
    return DEFAULTS;
  }
}

type PrefsState = Prefs & { set: (p: Partial<Prefs>) => void };

export const usePrefs = create<PrefsState>((set, get) => ({
  ...load(),
  set: (p) => {
    set(p);
    const { voiceAlerts, soundAlerts } = { ...get(), ...p };
    try {
      localStorage.setItem(KEY, JSON.stringify({ voiceAlerts, soundAlerts }));
    } catch {
      /* ignore */
    }
  },
}));
