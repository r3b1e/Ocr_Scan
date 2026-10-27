/**
 * Reminder sounds via WebAudio (no audio files, no network). Browsers only
 * allow audio after a user gesture, so the context is unlocked on first tap.
 */
let ctx: AudioContext | null = null;
let loop: number | null = null;
let idle: number | null = null;

/** Suspend once quiet: a running context keeps an audio stream (and battery) busy on phones. */
function suspendSoon(ms: number) {
    if (idle != null) window.clearTimeout(idle);
    idle = window.setTimeout(() => {
        idle = null;
        if (loop == null && ctx?.state === 'running') void ctx.suspend();
    }, ms);
}

function audio(): AudioContext | null {
    try {
        ctx ??= new (window.AudioContext || (window as any).webkitAudioContext)();
        if (idle != null) { window.clearTimeout(idle); idle = null; }
        if (ctx.state === 'suspended') void ctx.resume();
        return ctx;
    } catch {
        return null;
    }
}

export function unlockAudio() {
    const unlock = () => {
        audio();
        suspendSoon(500);
        window.removeEventListener('pointerdown', unlock);
        window.removeEventListener('keydown', unlock);
    };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('keydown', unlock);
}

function tone(c: AudioContext, freq: number, start: number, dur: number, gain = 0.18) {
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = 'sine';
    o.frequency.value = freq;
    g.gain.setValueAtTime(0, start);
    g.gain.linearRampToValueAtTime(gain, start + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
    o.connect(g).connect(c.destination);
    o.start(start);
    o.stop(start + dur + 0.05);
}

/** A soft three-note chime. */
export function chime() {
    const c = audio();
    if (!c) return;
    const t = c.currentTime + 0.02;
    tone(c, 880, t, 0.5);
    tone(c, 1174.66, t + 0.18, 0.5);
    tone(c, 1567.98, t + 0.36, 0.7);
    suspendSoon(2000);
}

/** Urgent alarm: repeats until stopAlarm(). */
export function startAlarm() {
    if (loop != null) return;
    const ring = () => {
        const c = audio();
        if (!c) return;
        const t = c.currentTime + 0.02;
        for (let i = 0; i < 4; i++) {
            tone(c, 988, t + i * 0.22, 0.16, 0.22);
            tone(c, 1318.5, t + i * 0.22 + 0.08, 0.12, 0.16);
        }
    };
    ring();
    loop = window.setInterval(ring, 1800);
}

export function stopAlarm() {
    if (loop != null) window.clearInterval(loop);
    loop = null;
    suspendSoon(1000);
}
