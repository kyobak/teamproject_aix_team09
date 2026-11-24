"use strict";
// #45 비시각 3분할 웹앱. 위 = 보행 안내, 왼쪽 아래 = 시간·배터리, 오른쪽 아래 = 긴급 전화.
// 안내 문구·진동 패턴은 walkaid/present/announcer.py 의 MESSAGES·VIBRATIONS 와 같아야 한다 (tests/test_webapp.py 가 검사).

const MESSAGES = {
  NO_SIGNAL: "신호등이 보이지 않습니다",
  WAIT: "빨간불, 기다리세요",
  CROSS: "초록불, 건널 수 있습니다",
  BLINK: "곧 바뀝니다, 새로 출발하지 마세요",
  UNKNOWN: "판단할 수 없습니다",
};
const VIBRATIONS = {
  NO_SIGNAL: [100],
  WAIT: [800],
  CROSS: [150, 100, 150, 100, 150],
  BLINK: [400, 150, 400],
  UNKNOWN: [100, 100, 600],
};
// 영역을 눌렀을 때 손으로 구분되는 짧은 진동 (상태 진동보다 훨씬 짧게)
const AREA_VIBRATIONS = { walk: [30], info: [30, 80, 30], call: [30, 80, 30, 80, 30] };

const INTRO = "위는 보행 안내, 왼쪽 아래는 시간, 오른쪽 아래는 긴급 전화입니다";
const BASE_CONTACTS = [
  { name: "119 소방 구급", number: "119" },
  { name: "112 경찰", number: "112" },
];
const CONTACTS_KEY = "walkaid.contacts"; // settings.html 과 같은 키
const LONG_PRESS_MS = 2000;
const FRAME_TIMEOUT_MS = 1000; // 1초 안에 응답이 없으면 UNKNOWN
const FRAME_INTERVAL_MS = 200; // 프레임 사이 최소 간격 (서버 부담 줄이기)
const CONTACT_RESET_MS = 10000; // 10초 넘게 안 누르면 다시 119부터

const $ = (id) => document.getElementById(id);
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let introduced = false;

// ---- 음성·진동 (없는 기기에서는 조용히 건너뛴다) ----
function speak(text) {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel(); // 말하던 것을 끊고 새 안내를 낸다
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "ko-KR";
  speechSynthesis.speak(utterance);
}

function vibrate(pattern) {
  if (typeof navigator.vibrate === "function") navigator.vibrate(pattern);
}

// ---- 누르기: 짧게(onShort) / 2초 길게(onLong) ----
// 브라우저는 사용자가 화면을 만지기 전에는 소리를 막는다. 그래서 첫 터치는 안내 음성에만 쓴다.
function bindPress(el, area, onShort, onLong) {
  let timer = null;
  let longFired = false;
  let pressed = false;
  let handledByPointer = false;
  const shortPress = () => {
    if (!introduced) {
      introduced = true;
      speak(INTRO);
      return;
    }
    vibrate(AREA_VIBRATIONS[area]);
    onShort();
  };
  const cancel = () => {
    clearTimeout(timer);
    timer = null;
    pressed = false;
  };
  el.addEventListener("contextmenu", (event) => event.preventDefault());
  el.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    pressed = true;
    longFired = false;
    handledByPointer = false;
    if (introduced && onLong) {
      timer = setTimeout(() => {
        longFired = true;
        onLong();
      }, LONG_PRESS_MS);
    }
  });
  el.addEventListener("pointerup", () => {
    if (!pressed) return;
    cancel();
    handledByPointer = true; // 뒤따라오는 click 은 무시
    if (!longFired) shortPress();
  });
  el.addEventListener("pointercancel", cancel);
  el.addEventListener("pointerleave", cancel);
  // TalkBack 두 번 탭·키보드 Enter 는 pointer 이벤트 없이 click 만 올 수 있다
  el.addEventListener("click", () => {
    if (handledByPointer) {
      handledByPointer = false;
      return;
    }
    shortPress();
  });
}

// ---- 위: 보행 안내 ----
const walk = {
  running: false,
  run: 0, // 시작할 때마다 1씩 늘린다. 멈춘 뒤 늦게 온 응답을 버리는 데 쓴다.
  lastState: null,
  stream: null,
  wakeLock: null,
};
const canvas = document.createElement("canvas");

function announce(state) {
  if (state === walk.lastState) return; // 상태가 바뀔 때만 안내
  walk.lastState = state;
  $("walk").textContent = MESSAGES[state];
  speak(MESSAGES[state]);
  vibrate(VIBRATIONS[state]);
}

function timeoutSignal(ms) {
  if (AbortSignal.timeout) return AbortSignal.timeout(ms);
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

async function sendFrame(session) {
  const video = $("camera");
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  const jpeg = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.75));
  if (!jpeg) return "UNKNOWN";
  const response = await fetch("/api/frame", {
    method: "POST",
    headers: { "X-Walkaid-Session": session, "Content-Type": "image/jpeg" },
    body: jpeg,
    signal: timeoutSignal(FRAME_TIMEOUT_MS),
  });
  const data = await response.json();
  return response.ok && data.state in MESSAGES ? data.state : "UNKNOWN";
}

async function frameLoop(run, session) {
  while (walk.running && run === walk.run) {
    const startedAt = performance.now();
    let state;
    try {
      state = await sendFrame(session);
    } catch {
      state = "UNKNOWN"; // 오류·1초 초과·연결 끊김
    }
    if (!walk.running || run !== walk.run) return;
    announce(state);
    await pause(Math.max(0, FRAME_INTERVAL_MS - (performance.now() - startedAt)));
  }
}

async function startWalk() {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    speak("카메라를 쓸 수 없습니다. 인증서가 있는 HTTPS 주소로 열어 주세요");
    return;
  }
  walk.running = true;
  walk.lastState = null;
  const run = ++walk.run;
  $("walk").textContent = "카메라 준비 중";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: "environment" }, width: { ideal: 640 }, height: { ideal: 480 } },
    });
    if (run !== walk.run) {
      stream.getTracks().forEach((track) => track.stop()); // 준비 중에 멈춤을 눌렀다
      return;
    }
    walk.stream = stream;
    const video = $("camera");
    video.srcObject = stream;
    await video.play();
    const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
  } catch {
    stopWalk(false);
    speak("카메라를 켤 수 없습니다");
    return;
  }
  try {
    walk.wakeLock = await navigator.wakeLock?.request("screen"); // 안내 중 화면 꺼짐 방지 (지원 기기만)
  } catch {
    walk.wakeLock = null;
  }
  frameLoop(run, crypto.randomUUID());
}

function stopWalk(sayIt) {
  walk.running = false;
  walk.run += 1;
  walk.lastState = null;
  walk.stream?.getTracks().forEach((track) => track.stop());
  walk.stream = null;
  walk.wakeLock?.release().catch(() => {});
  walk.wakeLock = null;
  $("walk").textContent = "보행 안내";
  if (sayIt) speak("보행 안내를 멈춥니다");
}

// ---- 왼쪽 아래: 시간·배터리 ----
function timeText(now) {
  const hour = now.getHours();
  return `${hour < 12 ? "오전" : "오후"} ${hour % 12 || 12}시 ${now.getMinutes()}분`;
}

async function batteryText() {
  try {
    const battery = await navigator.getBattery();
    return `배터리 ${Math.round(battery.level * 100)}퍼센트`;
  } catch {
    return "배터리 정보를 읽을 수 없습니다"; // getBattery 가 없는 기기(아이폰 등)
  }
}

async function tellTimeAndBattery() {
  speak(`${timeText(new Date())}, ${await batteryText()}`);
}

// ---- 오른쪽 아래: 긴급 전화 ----
function loadContacts() {
  try {
    const saved = JSON.parse(localStorage.getItem(CONTACTS_KEY) || "[]");
    const valid = saved.filter((c) => typeof c?.name === "string" && /^[0-9+]{2,20}$/.test(c?.number));
    return BASE_CONTACTS.concat(valid);
  } catch {
    return BASE_CONTACTS;
  }
}

const call = { index: 0, lastShortAt: 0 };

function nextContact() {
  const contacts = loadContacts();
  const now = Date.now();
  // 처음 누르면(또는 10초 넘게 쉬었다 누르면) 119부터 읽고, 이어서 누르면 다음 연락처로 넘어간다
  call.index = now - call.lastShortAt > CONTACT_RESET_MS ? 0 : (call.index + 1) % contacts.length;
  call.lastShortAt = now;
  const contact = contacts[call.index];
  $("call").textContent = contact.name;
  speak(`${contact.name}. 전화하려면 2초 동안 길게 누르세요`);
}

function placeCall() {
  const contacts = loadContacts();
  const contact = contacts[call.index] ?? contacts[0];
  vibrate([300, 100, 300]);
  window.location.href = `tel:${contact.number}`;
}

// ---- 연결 ----
bindPress($("walk"), "walk", () => (walk.running ? stopWalk(true) : startWalk()));
bindPress($("info"), "info", tellTimeAndBattery);
bindPress($("call"), "call", nextContact, placeCall);

// 화면을 벗어나면(전화 앱 열림, 홈 버튼) 카메라를 끈다. 돌아오면 다시 눌러 시작한다.
document.addEventListener("visibilitychange", () => {
  if (document.hidden && walk.running) stopWalk(false);
});
window.addEventListener("pagehide", () => stopWalk(false));
