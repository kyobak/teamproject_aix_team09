# 팀 데이터 위치

2026-11-15 사용자가 지정한 팀 공유 Drive입니다. 앞으로 이 프로젝트의 Drive 자료는 아래 폴더를 기준으로 조회합니다.

- 팀 루트: https://drive.google.com/drive/folders/1krzxkkxWZMVfu9W4U1cQXEakXyZtXege
- 원본: original_videos/Priginal video
  - https://drive.google.com/drive/folders/1P3IUmqeOpTKuQDeGmzM4huuZoNAIB26y
- 블러 영상 보관 폴더: videos_blurred (폴더에 있다는 사실만으로 검수 완료를 뜻하지 않습니다)
  - https://drive.google.com/drive/folders/1dNp-GxfVsmov4Tm68wuoeeN2JR-Xg4Si
- 추출 사진: frames
  - https://drive.google.com/drive/folders/1chG89hFXAChhxicm-UzZgHAqbTLVIHbm
- 가중치: models
  - https://drive.google.com/drive/folders/1NWcv6sAb8Ie6chwcdaHbVK_3FINTPi-W

## 2026-11-15 조회 결과

원본 하위 폴더에서 MP4/MOV 영상 목록을 확인했습니다. frames, videos_blurred, models는 현재 연결 계정의 폴더 목록 조회 결과가 비어 있었습니다.

D0 평가에 쓴 12개 영상의 파일명 대응표, 프레임별 정답/박스, 평가 제외 구간은 이 폴더 조회와 저장소에서 찾지 못했습니다. 원본 폴더의 영상이 바로 동일 테스트셋이라는 뜻은 아닙니다.

원본은 AI에 이미지로 전달하거나 자동 테스트에 넣지 않습니다. 비식별 검수가 끝난 데이터와 정답표를 확보해 D0/D1을 같은 자료로 비교합니다. 기존 평가 수치로 새 모델의 정확도를 추정하지 않습니다.

## 2026-11-20 평가 자료 갱신

#38이 main에 머지되어 data/labels/signal_eval_gt.json에 평가 영상 12개 파일명과 정답·박스가 있고, tools/eval_signal.py에 공통 채점 및 제외 규칙이 있습니다. 위 11월 15일의 자료 미확인 기록은 당시 조회 결과입니다. 현재는 실제 평가 영상 파일과 정답 파일명의 대응 및 동일 자료에서의 D0·D1 평가가 남았습니다.
