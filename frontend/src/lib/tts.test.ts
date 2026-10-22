import { canSpeak, speak } from './tts';

function installSynth(voices: { lang: string; name: string }[]) {
  const spoken: string[] = [];
  const synth = {
    speaking: false,
    pending: false,
    getVoices: () => voices,
    speak: (u: { text: string }) => spoken.push(u.text),
    cancel: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
  Object.defineProperty(window, 'speechSynthesis', { value: synth, configurable: true });
  vi.stubGlobal(
    'SpeechSynthesisUtterance',
    class {
      lang = '';
      voice: unknown = null;
      rate = 1;
      constructor(public text: string) {}
    },
  );
  return spoken;
}

describe('tts', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('speaks English and de-duplicates repeats', () => {
    const spoken = installSynth([{ lang: 'en-GB', name: 'English' }]);
    expect(speak('Zone F1-Z1 is unsafe. Turn back.', 'en')).toBe('spoken');
    expect(speak('Zone F1-Z1 is unsafe. Turn back.', 'en')).toBe('duplicate');
    expect(spoken).toEqual(['Zone F1-Z1 is unsafe. Turn back.']);
  });

  it('reports Urdu as unavailable without an Urdu voice, so the UI shows text instead', () => {
    installSynth([{ lang: 'en-US', name: 'English' }]);
    expect(canSpeak('ur')).toBe(false);
    expect(speak('زون غیر محفوظ ہے', 'ur')).toBe('unavailable');
  });

  it('uses an Urdu voice when present', () => {
    const spoken = installSynth([{ lang: 'ur-PK', name: 'Urdu' }]);
    expect(speak('زون F1-Z2 بند ہے', 'ur')).toBe('spoken');
    expect(spoken).toHaveLength(1);
  });
});
