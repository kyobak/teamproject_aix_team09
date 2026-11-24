"""#45 웹앱 정적 파일 검사.

웹앱(JavaScript)과 노트북 안내(announcer.py)가 같은 상태에 다른 말·진동을 내지 않게,
app.js 의 MESSAGES·VIBRATIONS 가 announcer.py 와 같은지 확인한다.
"""

import json
import re
from pathlib import Path

from walkaid.present.announcer import MESSAGES, VIBRATIONS

WEBAPP = Path(__file__).resolve().parents[1] / "webapp"


def js_object(name: str) -> dict:
    """app.js 의 `const NAME = { KEY: 값, ... };` 를 dict 로 읽는다."""
    source = (WEBAPP / "app.js").read_text(encoding="utf-8")
    match = re.search(rf"const {name} = \{{(.*?)\}};", source, re.DOTALL)
    assert match, f"{name} not found in app.js"
    body = re.sub(r"(\w+):", r'"\1":', match.group(1)).rstrip().rstrip(",")
    return json.loads("{" + body + "}")


def test_messages_match_announcer():
    assert js_object("MESSAGES") == {state.value: text for state, text in MESSAGES.items()}


def test_vibrations_match_announcer():
    assert js_object("VIBRATIONS") == {state.value: list(pattern) for state, pattern in VIBRATIONS.items()}


def test_three_areas_have_aria_labels():
    html = (WEBAPP / "index.html").read_text(encoding="utf-8")
    for area in ("walk", "info", "call"):
        assert re.search(rf'<button id="{area}" type="button" aria-label="[^"]+"', html), area


def test_settings_uses_same_storage_key():
    app = (WEBAPP / "app.js").read_text(encoding="utf-8")
    settings = (WEBAPP / "settings.html").read_text(encoding="utf-8")
    key = re.search(r'const CONTACTS_KEY = "([^"]+)"', app).group(1)
    assert f'const KEY = "{key}"' in settings
