"""음성·진동 안내 (#8). 상태가 바뀔 때만 안내한다.

표현 계층: 검출 방법이나 HSV 값은 모른다. 상태(State)만 받는다.

- announce() 는 바로 돌아온다. 음성·진동은 별도 스레드(worker)가 낸다.
  음성 엔진이 말하는 1~2초 동안 프레임 처리가 멈추면, 웹캠 입력에서는 프레임 간격이
  frame_gap_sec 을 넘어 상태 머신이 UNKNOWN 으로 바뀌기 때문이다.
- 기다리는 안내는 가장 최신 것 하나만 남긴다. 밀린 옛 안내는 버린다.
- 말하는 도중 상태가 바뀌면 지금 말을 끊고 새 안내를 낸다.
  (예: "건널 수 있습니다"를 말하는 중에 UNKNOWN 이 되면 끝까지 말하지 않는다)
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from walkaid.logic.signal_fsm import State

MESSAGES = {
    State.NO_SIGNAL: "신호등이 보이지 않습니다",
    State.WAIT: "빨간불, 기다리세요",
    State.CROSS: "초록불, 건널 수 있습니다",
    State.BLINK: "곧 바뀝니다, 새로 출발하지 마세요",
    State.UNKNOWN: "판단할 수 없습니다",
}

# 진동 패턴: 밀리초 단위 (진동, 쉼, 진동, 쉼, ...). 상태마다 손으로 구분되게 서로 다르게 둔다.
VIBRATIONS: dict[State, tuple[int, ...]] = {
    State.NO_SIGNAL: (100,),  # 짧게 1번
    State.WAIT: (800,),  # 길게 1번
    State.CROSS: (150, 100, 150, 100, 150),  # 짧게 3번
    State.BLINK: (400, 150, 400),  # 중간 길이 2번
    State.UNKNOWN: (100, 100, 600),  # 짧게-길게
}


class Speaker(Protocol):
    def say(self, text: str, should_stop: Callable[[], bool]) -> None:
        """text 를 말한다. 말하는 동안 should_stop() 이 True 가 되면 바로 멈춘다."""


class Vibrator(Protocol):
    def vibrate(self, pattern: tuple[int, ...]) -> None:
        """패턴을 내보낸다. 오래 걸리면 음성이 늦어지므로 바로 돌아와야 한다."""


class PyttsxSpeaker:
    """pyttsx3 음성 엔진. 엔진은 처음 말할 때 worker 스레드 안에서 만든다(엔진은 만든 스레드에서만 써야 함)."""

    def __init__(self) -> None:
        self._engine = None
        self._should_stop: Callable[[], bool] = lambda: False

    def say(self, text: str, should_stop: Callable[[], bool]) -> None:
        if self._engine is None:
            import pyttsx3  # 실제 기기에서만 불러온다 (CI 에는 음성 엔진이 없음)

            self._engine = pyttsx3.init()
            self._engine.connect("started-word", self._on_word)
        self._should_stop = should_stop
        self._engine.say(text)
        self._engine.runAndWait()

    def _on_word(self, name, location, length) -> None:
        if self._should_stop():
            self._engine.stop()


class SapiSpeaker:
    """Windows 음성(SAPI)을 직접 쓴다.

    Windows 에서 pyttsx3 로 말을 중간에 멈추면(stop) 그 뒤 다음 말이 나오지 않았다 (2026-11-11 실기기 확인).
    SAPI 는 '지금 말을 버리고 새 말 하기(PURGE)'를 직접 지원하므로 끊고 이어 말하기가 안정적이다.
    comtypes 는 pyttsx3 가 Windows 에서 이미 쓰는 패키지라 새로 추가하지 않는다.
    """

    _ASYNC = 1  # 말을 시작만 하고 바로 돌아온다
    _PURGE = 2  # 하던 말을 버린다

    def __init__(self) -> None:
        self._voice = None

    def say(self, text: str, should_stop: Callable[[], bool]) -> None:
        if self._voice is None:
            import comtypes
            import comtypes.client

            comtypes.CoInitialize()  # worker 스레드에서 COM 을 쓰기 위한 준비
            self._voice = comtypes.client.CreateObject("SAPI.SpVoice")
        self._voice.Speak(text, self._ASYNC | self._PURGE)
        while not self._voice.WaitUntilDone(50):  # 0.05초마다 끊어야 하는지 확인
            if should_stop():
                self._voice.Speak("", self._ASYNC | self._PURGE)  # 빈 말로 덮어써서 멈춘다
                return


def default_speaker() -> Speaker:
    """실행 중인 운영체제에 맞는 음성 엔진."""
    return SapiSpeaker() if sys.platform == "win32" else PyttsxSpeaker()


@dataclass
class Delivery:
    """안내 한 건의 기록. 지연 시간 확인용 (시각은 time.monotonic 기준)."""

    state: State
    requested_at: float
    started_at: float | None = None  # 진동·음성을 내기 시작한 시각, 버려졌으면 None

    @property
    def latency(self) -> float | None:
        return None if self.started_at is None else self.started_at - self.requested_at


class Announcer:
    def __init__(
        self,
        use_tts: bool = False,
        speaker: Speaker | None = None,
        vibrator: Vibrator | None = None,
    ) -> None:
        self.last: State | None = None
        if speaker is None and use_tts:
            speaker = default_speaker()
        self._speaker = speaker
        self._vibrator = vibrator
        self.deliveries: list[Delivery] = []

        self._cond = threading.Condition()
        self._pending: tuple[int, Delivery] | None = None
        self._gen = 0  # 새 안내가 들어올 때마다 1 증가. 말하는 중인 안내의 번호와 다르면 끊는다
        self._closed = False
        self._thread: threading.Thread | None = None
        if speaker is not None or vibrator is not None:
            self._thread = threading.Thread(target=self._run, name="announcer", daemon=True)
            self._thread.start()

    def announce(self, state: State) -> str | None:
        """새 상태일 때만 문구를 돌려주고(음성·진동은 worker 에 맡김), 같은 상태면 None. 바로 돌아온다."""
        if state == self.last:
            return None
        self.last = state
        delivery = Delivery(state=state, requested_at=time.monotonic())
        self.deliveries.append(delivery)
        if self._thread is not None:
            with self._cond:
                self._gen += 1
                self._pending = (self._gen, delivery)  # 밀려 있던 옛 안내는 덮어써서 버린다
                self._cond.notify()
        return MESSAGES[state]

    def close(self, timeout: float = 2.0) -> None:
        """worker 를 멈춘다. 말하던 것도 끊는다."""
        if self._thread is None:
            return
        with self._cond:
            self._closed = True
            self._gen += 1
            self._cond.notify()
        self._thread.join(timeout)

    def _run(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and not self._closed:
                    self._cond.wait()
                if self._closed:
                    return
                gen, delivery = self._pending
                self._pending = None

            def stale(gen: int = gen) -> bool:
                return self._gen != gen

            delivery.started_at = time.monotonic()
            if self._vibrator is not None:
                self._vibrator.vibrate(VIBRATIONS[delivery.state])
            if self._speaker is not None and not stale():
                self._speaker.say(MESSAGES[delivery.state], stale)
