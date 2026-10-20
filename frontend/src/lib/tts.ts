import type { Lang } from '../i18n';

/**
 * Spoken alerts (HANDOFF §8.4): template text, never an LLM. Picks a voice for the language,
 * de-duplicates repeats, keeps the queue short (newest wins), and reports when speech isn't
 * possible so the caller shows the text instead (SRS UC-04 exceptional flow).
 */
export type SpeakResult = 'spoken' | 'duplicate' | 'unavailable';

const DEDUPE_MS = 8000;
const recent = new Map<string, number>();

function synth(): SpeechSynthesis | null {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
    ? window.speechSynthesis
    : null;
}

export function voiceFor(lang: Lang): SpeechSynthesisVoice | null {
  const voices = synth()?.getVoices() ?? [];
  const want = lang === 'ur' ? ['ur'] : ['en'];
  return voices.find((v) => want.some((w) => v.lang.toLowerCase().startsWith(w))) ?? null;
}

export function canSpeak(lang: Lang): boolean {
  const s = synth();
  if (!s) return false;
  // English falls back to the default voice; Urdu needs a real Urdu voice.
  return lang === 'en' ? true : voiceFor('ur') !== null;
}

export function speak(text: string, lang: Lang): SpeakResult {
  const s = synth();
  if (!s || !canSpeak(lang)) return 'unavailable';
  const now = Date.now();
  if ((recent.get(text) ?? 0) > now - DEDUPE_MS) return 'duplicate';
  recent.set(text, now);
  if (s.pending || s.speaking) {
    // Keep only the newest alert waiting; a stale one is worse than none.
    s.cancel();
  }
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang === 'ur' ? 'ur-PK' : 'en-GB';
  const v = voiceFor(lang);
  try {
    if (v) u.voice = v;
    u.rate = 1.0;
    s.speak(u);
  } catch {
    return 'unavailable';
  }
  return 'spoken';
}

/** Voices load asynchronously in some browsers. */
export function onVoicesChanged(cb: () => void): () => void {
  const s = synth();
  if (!s) return () => undefined;
  s.addEventListener('voiceschanged', cb);
  return () => s.removeEventListener('voiceschanged', cb);
}
