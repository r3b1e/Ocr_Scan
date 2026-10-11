"""Tests for core.audio - beeps must never break the app."""

from __future__ import annotations

from core.audio import AudioFeedback


def test_disabled_audio_is_a_no_op(mocker):
    init = mocker.patch("pygame.mixer.init")
    audio = AudioFeedback(enabled=False)
    assert audio.init() is False
    assert audio.available is False
    audio.beep_success()
    audio.beep_error()
    audio.shutdown()
    init.assert_not_called()


def test_mixer_failure_degrades_gracefully(mocker):
    import pygame

    mocker.patch("pygame.mixer.init", side_effect=pygame.error("No available audio device"))
    audio = AudioFeedback(enabled=True)
    assert audio.init() is False
    assert audio.available is False
    audio.beep_success()  # must not raise
    audio.shutdown()


def test_successful_init_plays_sound(mocker):
    mocker.patch("pygame.mixer.init")
    mocker.patch("pygame.mixer.get_init", return_value=(44100, -16, 1))
    fake_sound = mocker.Mock()
    make_sound = mocker.patch("pygame.sndarray.make_sound", return_value=fake_sound)
    quit_ = mocker.patch("pygame.mixer.quit")

    audio = AudioFeedback(enabled=True)
    assert audio.init() is True
    assert audio.available is True
    audio.beep_success()
    audio.beep_error()
    assert make_sound.call_count == 2
    assert fake_sound.play.call_count == 2
    audio.shutdown()
    quit_.assert_called_once()
    assert audio.available is False


def test_play_failure_is_swallowed(mocker):
    mocker.patch("pygame.mixer.init")
    mocker.patch("pygame.mixer.get_init", return_value=(44100, -16, 1))
    mocker.patch("pygame.sndarray.make_sound", side_effect=RuntimeError("mixer gone"))
    audio = AudioFeedback(enabled=True)
    audio.init()
    audio.beep_success()  # must not raise
