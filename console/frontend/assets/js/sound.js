// Voidz UI sound feedback — tiny synthesized tones via Web Audio API.
// No audio files, no CDN: everything here must keep working offline.
const STORAGE_KEY = "voidz.sound";
let ctx = null;
let enabled = localStorage.getItem(STORAGE_KEY) !== "off";

function ensureCtx() {
  if (!enabled) return null;
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

function tone({ freq = 440, duration = 0.12, type = "sine", gain = 0.045, delay = 0, glideTo = null }) {
  const c = ensureCtx();
  if (!c) return;
  const t0 = c.currentTime + delay;
  const osc = c.createOscillator();
  const g = c.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (glideTo) osc.frequency.exponentialRampToValueAtTime(Math.max(glideTo, 1), t0 + duration);
  g.gain.setValueAtTime(0.0001, t0);
  g.gain.linearRampToValueAtTime(gain, t0 + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
  osc.connect(g).connect(c.destination);
  osc.start(t0);
  osc.stop(t0 + duration + 0.03);
}

export const sound = {
  isEnabled: () => enabled,
  setEnabled(v) {
    enabled = v;
    localStorage.setItem(STORAGE_KEY, v ? "on" : "off");
    if (v) tone({ freq: 660, duration: .06, type: "sine", gain: .04 });
  },
  click() { tone({ freq: 720, duration: .05, type: "sine", gain: .035 }); },
  nav() { tone({ freq: 460, duration: .1, type: "triangle", gain: .03, glideTo: 660 }); },
  success() {
    tone({ freq: 520, duration: .1, type: "sine", gain: .05 });
    tone({ freq: 780, duration: .18, type: "sine", gain: .05, delay: .09 });
  },
  error() { tone({ freq: 200, duration: .24, type: "sawtooth", gain: .045, glideTo: 85 }); },
  toggle() { tone({ freq: 600, duration: .06, type: "square", gain: .022 }); },
};
