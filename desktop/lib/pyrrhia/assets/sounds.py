"""Synthesised freedesktop sound themes. Each tribe has a "voice" (how a note sounds) and a root
pitch; every event plays a short motif in that voice. Pure stdlib so it runs anywhere."""
import math
import random
import struct
import textwrap
import wave
from pathlib import Path

RATE = 22050

# Event -> list of (semitones above root, start seconds, length seconds, volume).
MOTIFS = {
    "desktop-login": [(0, 0.0, 0.5, 0.8), (4, 0.14, 0.5, 0.8), (7, 0.28, 0.5, 0.8), (12, 0.42, 0.9, 0.9)],
    "desktop-logout": [(12, 0.0, 0.45, 0.8), (7, 0.14, 0.45, 0.8), (4, 0.28, 0.45, 0.8), (0, 0.42, 0.8, 0.8)],
    "dialog-information": [(7, 0.0, 0.35, 0.7), (12, 0.1, 0.5, 0.7)],
    "dialog-warning": [(5, 0.0, 0.3, 0.8), (1, 0.16, 0.5, 0.8)],
    "dialog-error": [(0, 0.0, 0.5, 0.9), (-5, 0.0, 0.5, 0.6), (-12, 0.18, 0.6, 0.8)],
    "dialog-question": [(4, 0.0, 0.3, 0.7), (9, 0.12, 0.45, 0.7)],
    "message-new-instant": [(12, 0.0, 0.25, 0.7), (16, 0.09, 0.4, 0.7)],
    "message-new-email": [(7, 0.0, 0.25, 0.7), (12, 0.09, 0.25, 0.7), (16, 0.18, 0.4, 0.7)],
    "complete": [(0, 0.0, 0.3, 0.7), (7, 0.1, 0.3, 0.7), (12, 0.2, 0.6, 0.8)],
    "bell": [(12, 0.0, 0.3, 0.6)],
    "window-attention": [(9, 0.0, 0.25, 0.6), (9, 0.18, 0.3, 0.6)],
    "device-added": [(0, 0.0, 0.25, 0.6), (7, 0.08, 0.35, 0.7)],
    "device-removed": [(7, 0.0, 0.25, 0.7), (0, 0.08, 0.35, 0.6)],
    "audio-volume-change": [(12, 0.0, 0.12, 0.5)],
    "trash-empty": [(0, 0.0, 0.2, 0.6), (-5, 0.06, 0.3, 0.5)],
}
ALIASES = {"bell": ("bell-window-system", "bell-terminal")}


def _env(t, length, attack=0.005, decay=None):
    decay = decay or length
    if t < attack:
        return t / attack
    return math.exp(-4.5 * (t - attack) / decay)


def _pluck(freq, length, rng):
    """Karplus-Strong string."""
    period = max(2, int(RATE / freq))
    buf = [rng.uniform(-1, 1) for _ in range(period)]
    out = []
    for i in range(int(length * RATE)):
        v = buf[i % period]
        buf[i % period] = 0.996 * 0.5 * (v + buf[(i + 1) % period])
        out.append(v)
    return out


def _voice(voice, freq, length, rng):
    n = int(length * RATE)
    if voice in ("pluck", "harp"):
        s = _pluck(freq, length, rng)
        if voice == "harp":
            s2 = _pluck(freq * 2, length, rng)
            s = [a + 0.35 * b for a, b in zip(s, s2)]
        return s
    out = []
    phase = 0.0
    noise_state = 0.0
    for i in range(n):
        t = i / RATE
        if voice == "ice":  # glassy bell: inharmonic partials
            v = (math.sin(math.tau * freq * t) + 0.5 * math.sin(math.tau * freq * 2.76 * t)
                 + 0.25 * math.sin(math.tau * freq * 5.4 * t)) * _env(t, length, decay=length * 0.8)
        elif voice == "water":  # bubbly: pitch rises inside each note
            f = freq * (1 + 0.25 * min(1, t / 0.08))
            phase += math.tau * f / RATE
            v = math.sin(phase) * _env(t, length, attack=0.01, decay=length * 0.5)
        elif voice == "wind":  # breathy flute over filtered noise
            noise_state += 0.08 * (rng.uniform(-1, 1) - noise_state)
            vib = 1 + 0.006 * math.sin(math.tau * 5 * t)
            phase += math.tau * freq * vib / RATE
            v = (0.8 * math.sin(phase) + 1.5 * noise_state) * min(1, t / 0.04) * math.exp(-3 * t / length)
        elif voice == "night":  # soft pad with a fifth
            v = (math.sin(math.tau * freq * t) + 0.4 * math.sin(math.tau * freq * 1.5 * t)
                 + 0.2 * math.sin(math.tau * freq * 0.5 * t)) * min(1, t / 0.06) * math.exp(-2.5 * t / length)
        elif voice == "rain":  # short droplets
            v = math.sin(math.tau * freq * (1 + 2 * math.exp(-t * 60)) * t) * math.exp(-t * 14)
        elif voice == "drum":  # pitched thump
            phase += math.tau * freq * (1 + 1.5 * math.exp(-t * 30)) / RATE
            v = math.sin(phase) * math.exp(-t * 9)
        elif voice == "buzz":  # soft saw with vibrato
            vib = 1 + 0.02 * math.sin(math.tau * 7 * t)
            phase += freq * vib / RATE
            saw = 2 * (phase % 1) - 1
            noise_state += 0.15 * (saw - noise_state)
            v = noise_state * 1.6 * min(1, t / 0.02) * math.exp(-3.5 * t / length)
        else:  # plain sine
            v = math.sin(math.tau * freq * t) * _env(t, length)
        out.append(v)
    return out


def render(voice, root, event):
    rng = random.Random(f"{voice}{root}{event}")
    notes = MOTIFS[event]
    total = max(start + length for _, start, length, _ in notes) + 0.05
    mix = [0.0] * int(total * RATE)
    for semis, start, length, vol in notes:
        freq = root * 2 ** (semis / 12)
        offset = int(start * RATE)
        for i, v in enumerate(_voice(voice, freq, length, rng)):
            if offset + i < len(mix):
                mix[offset + i] += v * vol
    peak = max(1e-6, max(abs(v) for v in mix))
    fade = int(0.02 * RATE)
    for i in range(fade):
        mix[-1 - i] *= i / fade
    return [v / peak * 0.7 for v in mix]


def write_wav(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32767)) for v in samples))


def write(tribe, theme_dir):
    theme_dir = Path(theme_dir)
    stereo = theme_dir / "stereo"
    stereo.mkdir(parents=True, exist_ok=True)
    voice = tribe.sounds.get("voice", "pluck")
    root = float(tribe.sounds.get("root", 440.0))
    for event in MOTIFS:
        path = stereo / f"{event}.wav"
        write_wav(path, render(voice, root, event))
        for alias in ALIASES.get(event, ()):
            link = stereo / f"{alias}.wav"
            link.unlink(missing_ok=True)
            link.symlink_to(path.name)
    (theme_dir / "index.theme").write_text(textwrap.dedent(f"""\
    [Sound Theme]
    Name=Wings of Fire - {tribe.name}
    Comment=Sounds of the {tribe.name}s
    Inherits=freedesktop
    Directories=stereo

    [stereo]
    OutputProfile=stereo
    """))
