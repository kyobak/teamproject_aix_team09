"""음성·진동 안내 (#8 에서 구현). 상태가 바뀔 때만 안내한다.

표현 계층: 검출 방법이나 HSV 값은 모른다. 상태(State)만 받는다.
"""
# Issue #8 구현 확인
from __future__ import annotations

from walkaid.logic.signal_fsm import State

MESSAGES = {
    State.NO_SIGNAL: "신호등이 보이지 않습니다",
    State.WAIT: "빨간불, 기다리세요",
    State.CROSS: "초록불, 건널 수 있습니다",
    State.BLINK: "곧 바뀝니다, 새로 출발하지 마세요",
    State.UNKNOWN: "판단할 수 없습니다",
}


class Announcer:
    def __init__(self, use_tts: bool = False) -> None:
        self.last: State | None = None
        self.engine = None
        if use_tts:
            import pyttsx3  # 실제 기기에서만 불러온다 (CI 에는 음성 엔진이 없음)

            self.engine = pyttsx3.init()

    def announce(self, state: State) -> str | None:
        """새 상태일 때만 문구를 돌려주고(그리고 말하고), 같은 상태면 None."""
        if state == self.last:
            return None
        self.last = state
        text = MESSAGES[state]
        if self.engine is not None:
            self.engine.say(text)
            self.engine.runAndWait()
        return text
