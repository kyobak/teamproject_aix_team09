"""음성·진동 안내 테스트 (#8).

완료 조건: 상태 5개가 서로 다른 문구로 상태 변화 후 1초 이내에 재생되고, 같은 상태는 반복 안내하지 않는다.
실제 음성 엔진 대신 시간이 걸리는 가짜 엔진(FakeSpeaker)을 넣어 확인한다.
"""

from __future__ import annotations

import threading
import time

from walkaid.logic.signal_fsm import State
from walkaid.present.announcer import MESSAGES, VIBRATIONS, Announcer


class FakeSpeaker:
    """한 문구를 말하는 데 speak_sec 초가 걸리는 가짜 엔진. should_stop() 이 True 면 중간에 멈춘다."""

    def __init__(self, speak_sec: float = 0.0) -> None:
        self.speak_sec = speak_sec
        self.started: list[str] = []
        self.finished: list[str] = []
        self.interrupted: list[str] = []
        self.first_started = threading.Event()

    def say(self, text, should_stop) -> None:
        self.started.append(text)
        self.first_started.set()
        end = time.monotonic() + self.speak_sec
        while time.monotonic() < end:
            if should_stop():
                self.interrupted.append(text)
                return
            time.sleep(0.005)
        self.finished.append(text)


class FakeVibrator:
    def __init__(self) -> None:
        self.patterns: list[tuple[int, ...]] = []

    def vibrate(self, pattern) -> None:
        self.patterns.append(pattern)


def wait_until(cond, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return cond()


def test_every_state_has_distinct_message_and_vibration():
    assert set(MESSAGES) == set(State)
    assert set(VIBRATIONS) == set(State)
    assert len(set(MESSAGES.values())) == len(State)
    assert len(set(VIBRATIONS.values())) == len(State)


def test_same_state_is_not_repeated_but_returning_state_is():
    a = Announcer()
    assert a.announce(State.WAIT) == MESSAGES[State.WAIT]
    assert a.announce(State.WAIT) is None
    assert a.announce(State.CROSS) == MESSAGES[State.CROSS]
    assert a.announce(State.WAIT) == MESSAGES[State.WAIT]


def test_announce_returns_immediately_while_speaking():
    """말하는 데 2초 걸려도 announce() 는 바로 돌아와야 프레임 처리가 멈추지 않는다."""
    speaker = FakeSpeaker(speak_sec=2.0)
    a = Announcer(speaker=speaker)
    try:
        t0 = time.monotonic()
        a.announce(State.WAIT)
        assert time.monotonic() - t0 < 0.05
    finally:
        a.close()


def test_each_state_starts_within_one_second():
    speaker = FakeSpeaker()
    vibrator = FakeVibrator()
    a = Announcer(speaker=speaker, vibrator=vibrator)
    try:
        for state in State:
            a.announce(state)
            assert wait_until(lambda s=state: MESSAGES[s] in speaker.finished)
        assert [d.state for d in a.deliveries] == list(State)
        assert all(d.latency is not None and d.latency < 1.0 for d in a.deliveries)
        assert vibrator.patterns == [VIBRATIONS[s] for s in State]
    finally:
        a.close()


def test_state_change_interrupts_current_speech():
    """'건널 수 있습니다'를 말하는 중에 UNKNOWN 이 되면 끝까지 말하지 않고 바로 새 안내로 넘어간다."""
    speaker = FakeSpeaker(speak_sec=3.0)
    a = Announcer(speaker=speaker)
    try:
        a.announce(State.CROSS)
        assert speaker.first_started.wait(1.0)
        a.announce(State.UNKNOWN)
        assert wait_until(lambda: MESSAGES[State.UNKNOWN] in speaker.started)
        assert speaker.interrupted == [MESSAGES[State.CROSS]]
        assert MESSAGES[State.CROSS] not in speaker.finished
        assert a.deliveries[-1].latency < 1.0
    finally:
        a.close()


def test_stale_announcements_are_dropped():
    """말하는 동안 상태가 여러 번 바뀌면 중간 것은 버리고 가장 최신 것만 말한다."""
    speaker = FakeSpeaker(speak_sec=3.0)
    a = Announcer(speaker=speaker)
    try:
        a.announce(State.WAIT)
        assert speaker.first_started.wait(1.0)
        a.announce(State.CROSS)
        a.announce(State.BLINK)
        a.announce(State.UNKNOWN)
        assert wait_until(lambda: MESSAGES[State.UNKNOWN] in speaker.started)
        assert speaker.started[-1] == MESSAGES[State.UNKNOWN]
        # 중간 안내는 시작조차 안 되는 게 보통이지만, 스레드 타이밍상 시작 직후 끊길 수는 있다. 끝까지 말하면 안 된다
        assert MESSAGES[State.CROSS] not in speaker.finished
        assert MESSAGES[State.BLINK] not in speaker.finished
    finally:
        a.close()


def test_default_speaker_matches_os(monkeypatch):
    """Windows 에서는 SAPI 를 직접, 그 밖에서는 pyttsx3 를 쓴다 (엔진은 처음 말할 때 만들어지므로 여기선 안 켜짐)."""
    from walkaid.present import announcer

    monkeypatch.setattr(announcer.sys, "platform", "win32")
    assert isinstance(announcer.default_speaker(), announcer.SapiSpeaker)
    monkeypatch.setattr(announcer.sys, "platform", "darwin")
    assert isinstance(announcer.default_speaker(), announcer.PyttsxSpeaker)


def test_close_stops_worker():
    speaker = FakeSpeaker(speak_sec=3.0)
    a = Announcer(speaker=speaker)
    a.announce(State.WAIT)
    assert speaker.first_started.wait(1.0)
    t0 = time.monotonic()
    a.close()
    assert time.monotonic() - t0 < 0.5
    assert speaker.interrupted == [MESSAGES[State.WAIT]]


def test_wait_idle_waits_until_last_speech_finishes():
    """#34: 영상이 끝나도 마지막 안내를 끝까지 말한다."""
    speaker = FakeSpeaker(speak_sec=0.3)
    a = Announcer(speaker=speaker)
    try:
        a.announce(State.WAIT)
        assert a.wait_idle(timeout=2.0)
        assert speaker.finished == [MESSAGES[State.WAIT]]
    finally:
        a.close()


def test_wait_idle_without_worker_returns_immediately():
    assert Announcer().wait_idle(timeout=0.1)
