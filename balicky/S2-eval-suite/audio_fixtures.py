# -*- coding: utf-8 -*-
"""
Synthetic stereo audio fixtures for the Polarita Eval Suite (package S2, Version 3.22).
Syntetické stereo zvukové makety pro Eval Suite Polarita (balíček S2, Verze 3.22).

EN: Generates deterministic 16-bit PCM stereo WAV files (Channel L = external caller,
    Channel R = Polarita employee) from tone-burst profiles and measures a simple acoustic
    urgency on Channel L only. These are tone mock-ups, not speech: the transcript of a call
    is supplied separately in the dataset (field "transcript_mock") as a stand-in for WhisperX.
    Reading Channel R for analysis is refused by design (FAIL_CLOSED).
CZ: Generuje deterministické 16bitové PCM stereo WAV soubory (Kanál L = vnější volající,
    Kanál R = pracovník Polarity) z tónových profilů a měří jednoduchou akustickou urgenci
    výhradně na Kanálu L. Jde o tónové makety, nikoli řeč: přepis hovoru se dodává zvlášť
    v datové sadě (pole "transcript_mock") jako náhrada WhisperX.
    Čtení Kanálu R pro analýzu je záměrně odmítnuto (FAIL_CLOSED).
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 8000
MAX_AMPLITUDE = 32767

# profile -> (amplitude 0..1, base frequency Hz, burst seconds, gap seconds, frequency sweep Hz)
# profil -> (amplituda 0..1, základní frekvence Hz, délka shluku s, mezera s, rozmítání Hz)
PROFILES = {
    "silence": (0.0, 0.0, 0.0, 1.0, 0.0),
    "calm": (0.18, 180.0, 0.60, 0.50, 0.0),
    "urgent": (0.75, 320.0, 0.18, 0.07, 200.0),
}

URGENCY_RMS_THRESHOLD = 0.30
URGENCY_BURST_RATE_THRESHOLD = 2.0


class ChannelRProhibitedError(PermissionError):
    """
    EN: Raised when any analysis of Channel R (employee voice) is requested.
    CZ: Vyvolá se při požadavku na jakoukoli analýzu Kanálu R (hlas zaměstnance).
    """


def _profile_samples(profile: str, seconds: float) -> list[int]:
    """Render one mono channel for a profile. / Vyrenderuje jeden mono kanál podle profilu."""
    if profile not in PROFILES:
        raise ValueError(f"unknown audio profile: {profile}")
    amplitude, base_hz, burst_s, gap_s, sweep_hz = PROFILES[profile]
    total = int(seconds * SAMPLE_RATE)
    if amplitude == 0.0:
        return [0] * total
    period = burst_s + gap_s
    samples = []
    phase = 0.0
    for index in range(total):
        t = index / SAMPLE_RATE
        position = t % period
        if position < burst_s:
            frequency = base_hz + sweep_hz * (position / burst_s)
            phase += 2.0 * math.pi * frequency / SAMPLE_RATE
            samples.append(int(MAX_AMPLITUDE * amplitude * math.sin(phase)))
        else:
            samples.append(0)
    return samples


def generate(path: Path, seconds: float, left: str, right: str) -> Path:
    """
    EN: Write a deterministic stereo WAV (L = caller profile, R = employee profile).
    CZ: Zapíše deterministický stereo WAV (L = profil volajícího, R = profil pracovníka).
    """
    left_samples = _profile_samples(left, seconds)
    right_samples = _profile_samples(right, seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for l_value, r_value in zip(left_samples, right_samples):
            frames += struct.pack("<hh", l_value, r_value)
        handle.writeframes(bytes(frames))
    return path


def inspect(path: Path) -> dict[str, float | int]:
    """Return basic WAV properties. / Vrátí základní vlastnosti WAV souboru."""
    with wave.open(str(path), "rb") as handle:
        return {
            "channels": handle.getnchannels(),
            "sample_rate": handle.getframerate(),
            "sample_width": handle.getsampwidth(),
            "seconds": handle.getnframes() / float(handle.getframerate()),
        }


def read_channel(path: Path, channel: str) -> list[float]:
    """
    EN: Return normalized samples of Channel L. Channel R is refused (FAIL_CLOSED).
    CZ: Vrátí normalizované vzorky Kanálu L. Kanál R je odmítnut (FAIL_CLOSED).
    """
    if channel == "R":
        raise ChannelRProhibitedError("analysis is allowed on Channel L only / analýza je povolena pouze na Kanálu L")
    if channel != "L":
        raise ValueError(f"unknown audio channel: {channel!r} (expected 'L' or 'R')")
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 2 or handle.getsampwidth() != 2:
            raise ValueError("expected 16-bit stereo WAV / očekáván 16bitový stereo WAV")
        raw = handle.readframes(handle.getnframes())
    return [struct.unpack_from("<h", raw, offset)[0] / MAX_AMPLITUDE for offset in range(0, len(raw), 4)]


def urgency_features(path: Path, channel: str = "L") -> dict[str, float]:
    """
    EN: Acoustic urgency features (RMS energy and burst rate) measured on Channel L only.
    CZ: Rysy akustické urgence (RMS energie a četnost shluků) měřené výhradně na Kanálu L.
    """
    samples = read_channel(path, channel)
    if not samples:
        return {"rms": 0.0, "burst_rate": 0.0}
    active = [abs(value) > 0.02 for value in samples]
    window = SAMPLE_RATE // 100  # 10 ms
    states = [any(active[start:start + window]) for start in range(0, len(active), window)]
    bursts = sum(1 for previous, current in zip([False] + states, states) if current and not previous)
    voiced = [value for value, is_active in zip(samples, active) if is_active]
    rms = math.sqrt(sum(value * value for value in voiced) / len(voiced)) if voiced else 0.0
    return {"rms": round(rms, 4), "burst_rate": round(bursts / (len(samples) / SAMPLE_RATE), 3)}


def urgency_level(path: Path, channel: str = "L") -> str:
    """Classify urgency as "high" or "low". / Zařadí urgenci jako "high" nebo "low"."""
    features = urgency_features(path, channel)
    is_high = features["rms"] >= URGENCY_RMS_THRESHOLD and features["burst_rate"] >= URGENCY_BURST_RATE_THRESHOLD
    return "high" if is_high else "low"
