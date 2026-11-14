"""#34: 음성을 켜고 영상 파일을 넣으면 실제 속도로 재생하고, 안내가 끊기지 않는다."""

from __future__ import annotations

import time

import cv2

import walkaid.present.announcer as announcer_mod
from tests.test_announcer import FakeSpeaker
from tests.test_opencv_rule import signal, street
from walkaid.main import run


def make_video(path, plan, fps=10):
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1080, 1920))
    for state, n in plan:
        for _ in range(n):
            out.write(signal(street(), 500, 600, state))
    out.release()
    return path


def test_file_with_tts_plays_in_realtime_and_speaks_every_announcement(tmp_path, monkeypatch):
    speaker = FakeSpeaker(speak_sec=0.3)  # 실제 음성처럼 한 문구에 시간이 걸린다
    monkeypatch.setattr(announcer_mod, "default_speaker", lambda: speaker)
    video = make_video(tmp_path / "v.mp4", [("red", 15), ("green", 15)])  # 3초
    t0 = time.monotonic()
    said = run(str(video), tts=True)
    elapsed = time.monotonic() - t0
    assert said == ["판단할 수 없습니다", "빨간불, 기다리세요", "초록불, 건널 수 있습니다"]
    assert elapsed >= 2.5  # 실제 속도로 재생 (처리만 하면 1초도 안 걸림)
    assert speaker.finished == said  # 하나도 끊기지 않고, 마지막 안내까지 끝까지 말함
    assert speaker.interrupted == []


def test_file_without_tts_is_not_slowed_down(tmp_path):
    video = make_video(tmp_path / "v.mp4", [("red", 30)])  # 3초
    t0 = time.monotonic()
    run(str(video))
    assert time.monotonic() - t0 < 2.5
