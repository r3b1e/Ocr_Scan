"""Audio feedback through pygame; degrades to a silent no-op when audio is unavailable."""

from __future__ import annotations

import os

import numpy as np

from utils.logger import get_logger

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

log = get_logger("core.audio")


class AudioFeedback:
    """Play short beeps for scan success/failure without ever raising."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._available = False
        self._sample_rate = 44100
        self._channels = 1

    @property
    def available(self) -> bool:
        """True when the mixer initialised and beeps will be audible."""
        return self._available

    def init(self) -> bool:
        """Initialise the pygame mixer. Returns False (and stays silent) on any failure."""
        if not self.enabled:
            return False
        try:
            import pygame

            pygame.mixer.init(frequency=self._sample_rate, size=-16, channels=1)
            state = pygame.mixer.get_init()
            if not state:
                raise RuntimeError("pygame mixer reported no active device")
            self._sample_rate, _, self._channels = int(state[0]), state[1], int(state[2])
            self._available = True
        except Exception as exc:
            log.warning("Audio disabled: pygame mixer could not start (%s)", exc)
            self._available = False
        return self._available

    def _tone(self, frequency: float, duration_ms: int, volume: float = 0.4) -> np.ndarray:
        samples = max(1, int(self._sample_rate * duration_ms / 1000))
        t = np.arange(samples) / self._sample_rate
        wave = np.sin(2 * np.pi * frequency * t)
        fade = min(samples // 2, int(self._sample_rate * 0.005))
        if fade > 0:
            ramp = np.linspace(0.0, 1.0, fade)
            wave[:fade] *= ramp
            wave[-fade:] *= ramp[::-1]
        pcm = (wave * volume * 32767).astype(np.int16)
        if self._channels > 1:
            pcm = np.repeat(pcm[:, None], self._channels, axis=1)
        return np.ascontiguousarray(pcm)

    def _play(self, frequency: float, duration_ms: int) -> None:
        if not self._available:
            return
        try:
            import pygame

            pygame.sndarray.make_sound(self._tone(frequency, duration_ms)).play()
        except Exception:
            log.warning("Could not play beep", exc_info=True)

    def beep_success(self) -> None:
        """Short high beep after a successful scan."""
        self._play(880.0, 150)

    def beep_error(self) -> None:
        """Longer low beep when a scan fails or finds nothing."""
        self._play(220.0, 300)

    def shutdown(self) -> None:
        """Release the mixer; safe to call when audio never initialised."""
        if not self._available:
            return
        try:
            import pygame

            pygame.mixer.quit()
        except Exception:
            log.warning("Error while closing the audio mixer", exc_info=True)
        finally:
            self._available = False
