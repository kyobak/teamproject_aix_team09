# 2026-11-20 블러 처리 버전과 검증 범위

## 확인 범위

- 이번 카톡 영상 24개: PR #39, `fix/4-yunet-only`, 커밋 `5680c60ff2dd60e2daafc398065b6a91d80f3c04`의 YuNet 단독 처리입니다. 이후 이 PR의 문서 수정은 영상 처리 버전을 바꾸지 않습니다.
- 실행 시 기록한 tools/blur.py SHA-256: `d8a5d7ffa0fa49f97c14ece79c61d9a4898fd29f6ad4b5fd6e4fae53fda002cc`. 해당 브랜치 파일과 일치함을 확인했습니다.
- YuNet 신뢰도 0.75 / NMS 0.3 / 보호 영역 없음 / Haar 얼굴·번호판 검출 없음. 원본 해상도 1080×1920, 총 55,431프레임, 1fps 사진 1,857장.
- 얼굴·번호판 육안 검수: 담당자별 검수 완료 범위와 제외 파일명 보고를 아직 확인하지 못했습니다. 추출 수와 자동 비교 수치를 육안 검수 수로 세지 않습니다.
- 이번 24개 원본은 보존 중입니다. 이전 PR #33의 50장 검수·원본 삭제 기록은 이 배치의 완료 증거가 아닙니다.

## Drive 영상 20개: 파일별 처리 버전

[videos_blurred](https://drive.google.com/drive/folders/1dNp-GxfVsmov4Tm68wuoeeN2JR-Xg4Si)의 2026-11-20 리뷰 대응 시점 목록입니다. 이번 배치 출력과 파일명·크기·업로드 ID를 대조했습니다. 파일명만으로 처리 버전을 추정하지 않았습니다.

| Drive 파일 | 처리 버전 | 확인 범위 |
|---|---|---|
| [_talkv_dJMcaBvL4Yx_R8kVT9kTEKRm7H5VK7YfMk_talkv_high_yunet.mp4](https://drive.google.com/file/d/1T3p9pajbfkSvgnsQWT-6Pn805ZwhkvS_/view?usp=drivesdk) | PR #39 / `5680c60` / YuNet 단독 | 로컬 처리 기록·업로드 ID·파일 크기 일치 |
| [_talkv_dJMcazxWULn_q5JK7HHJf2A2859coJMsKK_talkv_high_yunet.mp4](https://drive.google.com/file/d/19jGcV_87O69uZCYEUx9AvUGiyImX47z8/view?usp=drivesdk) | PR #39 / `5680c60` / YuNet 단독 | 로컬 처리 기록·업로드 ID·파일 크기 일치 |
| [_talkv_dJMcawnBzW6_8OfKdQnyPi9KrIiffDBAZK_talkv_high_yunet.mp4](https://drive.google.com/file/d/1CflwjcsKN2zp2pAAOCzMPpU_cnUbNOW9/view?usp=drivesdk) | PR #39 / `5680c60` / YuNet 단독 | 로컬 처리 기록·업로드 ID·파일 크기 일치 |
| [_talkv_dJMcanK2R2l_ukYYaHCHPELj2DfJc1NKBK_talkv_high_yunet.mp4](https://drive.google.com/file/d/1t63VhldWiWoBEo2w5JgbC3SK5UPC07za/view?usp=drivesdk) | PR #39 / `5680c60` / YuNet 단독 | 로컬 처리 기록·업로드 ID·파일 크기 일치 |
| [IMG_6984_blurred.mp4](https://drive.google.com/file/d/1UVomM0ifEJYbGzZNUTBAyJqvCFLO6Pjv/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6983_blurred.mp4](https://drive.google.com/file/d/1OsXA2sFvOXs9u8AowiHEVJXbPedXv_oz/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6982_blurred.mp4](https://drive.google.com/file/d/1r__RqoXimE9QC2mKIo8KtfFIEhGc0MXy/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6981_blurred.mp4](https://drive.google.com/file/d/1OF_cNQGF7G1izsAl5BaVTDCqVlzGP9it/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6980_blurred.mp4](https://drive.google.com/file/d/1xK0ZwBdrTpZLzRXCfZ295q_e2BHXb6GO/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6979_blurred.mp4](https://drive.google.com/file/d/1ckhjs5XLcKXTrbYbgnxbGejjZttCpK0T/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6978_blurred.mp4](https://drive.google.com/file/d/1FHcVPtpH4MnPKeYiy5jG6V-E5984icAr/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6977_blurred.mp4](https://drive.google.com/file/d/1-Jp2NSQUVo9f1WLQFQDFS-mMQuqX5wTB/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6976_blurred.mp4](https://drive.google.com/file/d/1JjUlIBX1Zd2J1g4DjPRmqQUXfqbdcawB/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6975_blurred.mp4](https://drive.google.com/file/d/1K5w_2O6lT-us5MtHh0aB2QqwN-JZ_Fc7/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6973_blurred.mp4](https://drive.google.com/file/d/1Of6ca6Br11vIeX4ZQHiWysOAd4pesaOa/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6972_blurred.mp4](https://drive.google.com/file/d/1cFgOtQxatA6eWKN4PQrVSjJzwk_G2_Te/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6971_blurred.mp4](https://drive.google.com/file/d/1qwX0blaPAr4Zlh0lKvnsiamq67cvnoIt/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6970_blurred.mp4](https://drive.google.com/file/d/1nsTW8ejC-Y4vjPdP4W4koHWjZqW5QJKt/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6968_blurred.mp4](https://drive.google.com/file/d/1EmOEizWFiCoG4qIJzrBgk45_d9HX_Xj_/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |
| [IMG_6967_blurred.mp4](https://drive.google.com/file/d/1bMrLVudXLVZpoS3zqn99jDEvDSv8Ywug/view?usp=drivesdk) | **미확인** | 처리자의 코드 버전/커밋 확인 필요; main 사용 여부도 미확인 |

기존 `IMG_...` 16개는 이 배치에서 만든 파일이 아닙니다. main 또는 PR #39 처리본으로 단정할 근거가 없으므로 처리자 확인이 필요합니다. 이번 배치 나머지 20개는 로컬 처리 완료이며 위 조회 시점에는 Drive 목록에 없었습니다.

## 이번 카톡 영상 24개: 신호 비교

5fps 기준으로 같은 프레임 번호를 선택하고 양쪽에 같은 원본 시각을 전달했습니다. D0/FSM은 최신 main `43e5694` 기준의 독립 인스턴스입니다. 비교 통과는 위험 방향 두 종류가 각각 0건이고 신호 정보(present/color/pos_check) 차이가 3% 이하인 경우입니다. 이는 얼굴·번호판 검수 통과와 별개입니다.

| 결과 파일 | 비교 프레임 | 신호 차이 | 차이율 | 원본 red→결과 green | 결과에서만 CROSS | 신호 기준 |
|---|---:|---:|---:|---:|---:|---|
| _talkv_dJMcanK2R2l_ukYYaHCHPELj2DfJc1NKBK_talkv_high_yunet.mp4 | 154 | 2 | 1.30% | 0 | 0 | 통과 |
| _talkv_dJMcawnBzW6_8OfKdQnyPi9KrIiffDBAZK_talkv_high_yunet.mp4 | 202 | 16 | 7.92% | 0 | 0 | **미달** |
| _talkv_dJMcaA4vdRK_t119X4qBjxrL6aAbkxYaQk_talkv_high_yunet.mp4 | 214 | 8 | 3.74% | 0 | 0 | **미달** |
| _talkv_dJMcazxWULn_q5JK7HHJf2A2859coJMsKK_talkv_high_yunet.mp4 | 230 | 190 | 82.61% | 114 | 49 | **미달** |
| _talkv_dJMcaq1YwAB_hLc5JrWwrKA36fsbhKBc4K_talkv_high_yunet.mp4 | 234 | 9 | 3.85% | 0 | 0 | **미달** |
| _talkv_dJMcalTG1x7_yNI50u5JFkhzerVuk7oFKK_talkv_high_yunet.mp4 | 244 | 4 | 1.64% | 0 | 0 | 통과 |
| _talkv_dJMcaysdt68_qI7mgEP8Db5CEBv6frvJz1_talkv_high_yunet.mp4 | 255 | 13 | 5.10% | 0 | 0 | **미달** |
| _talkv_dJMcamZHxf7_a3ll9ymnZQRj1PQ3u5UQA0_talkv_high_yunet.mp4 | 263 | 2 | 0.76% | 0 | 0 | 통과 |
| _talkv_dJMcak1L11l_qbRD6ntbrCLf3KOsA9Gbc1_talkv_high_yunet.mp4 | 270 | 0 | 0.00% | 0 | 0 | 통과 |
| _talkv_dJMcaBvL4Yx_R8kVT9kTEKRm7H5VK7YfMk_talkv_high_yunet.mp4 | 272 | 6 | 2.21% | 0 | 0 | 통과 |
| _talkv_dJMcamrEXs0_m9ByykWkoNgd9YHTErIs31_talkv_high_yunet.mp4 | 296 | 133 | 44.93% | 110 | 115 | **미달** |
| _talkv_dJMcap9OFOM_Nniy81VPRJsCftDpqdXL80_talkv_high_yunet.mp4 | 312 | 1 | 0.32% | 0 | 0 | 통과 |
| _talkv_dJMcaxz4B4K_6feyFY4YukVXuH8kekBNEK_talkv_high_yunet.mp4 | 314 | 30 | 9.55% | 0 | 0 | **미달** |
| _talkv_dJMcap9OGkS_istUQWI8JUaWNsxhHrkgk0_talkv_high_yunet.mp4 | 321 | 2 | 0.62% | 0 | 0 | 통과 |
| _talkv_dJMcaCg2QBm_6RBJSy13mqIiIFQAdDKPA0_talkv_high_yunet.mp4 | 325 | 31 | 9.54% | 0 | 0 | **미달** |
| _talkv_dJMcarUhX8x_5JiVnl5bWeRxcp0DOYdu00_talkv_high_yunet.mp4 | 461 | 0 | 0.00% | 0 | 0 | 통과 |
| _talkv_dJMcasSZrxO_f780ilsKquwZtrr1hv66iK_talkv_high_yunet.mp4 | 518 | 0 | 0.00% | 0 | 0 | 통과 |
| _talkv_dJMcauJ4xpW_KNVjiFDzciHzkd8ts6KOv1_talkv_high_yunet.mp4 | 519 | 0 | 0.00% | 0 | 0 | 통과 |
| _talkv_dJMcalNsng2_cdsJzL59ciicUIH6FKhKa0_talkv_high_yunet.mp4 | 532 | 12 | 2.26% | 0 | 0 | 통과 |
| _talkv_dJMcapaRElR_Z0m3rZK3bektuxjrn2lj51_talkv_high_yunet.mp4 | 562 | 15 | 2.67% | 0 | 0 | 통과 |
| _talkv_dJMcat5sZTp_0b57XBdgxe6dvijkdRNih0_talkv_high_yunet.mp4 | 634 | 1 | 0.16% | 0 | 0 | 통과 |
| _talkv_dJMcaqOwqR4_5pufKjDlIFiIflRv4L1xZk_talkv_high_yunet.mp4 | 676 | 329 | 48.67% | 2 | 95 | **미달** |
| _talkv_dJMcayZ4UuL_iH8YmzCByuGX9b4NOGDQ40_talkv_high_yunet.mp4 | 685 | 36 | 5.26% | 0 | 0 | **미달** |
| _talkv_dJMcaoDfyYX_P2B3z65l3p6jeq6mna0m7k_talkv_high_yunet.mp4 | 754 | 11 | 1.46% | 0 | 0 | 통과 |

신호 기준 14개 통과 / 10개 미달. 미달 중 3개에서 위험 방향 차이가 있었으며, 전체 비교에서 원본 red→결과 green 226프레임, 결과에서만 CROSS 259프레임입니다. 두 종류는 같은 프레임에서 겹칠 수 있으므로 합쳐서 고유 프레임 수로 해석하지 않습니다.

신호 기준 미달 10개는 가림 영역·재인코딩 등 원인을 추가 확인할 대상으로 남깁니다. 담당자 개인정보 전수 검수와 신호 기준 확인이 끝나지 않은 상태를 라벨링 준비 완료로 표시하지 않습니다. 기존 Drive 16개도 처리 버전·검수 범위를 확인해야 합니다.

사진 검수 중 얼굴·번호판이 식별되는 프레임은 `frames/_reject/<clip_id>/`로 이동하고 원래 파일명·사유를 강태혁에게 공유합니다. 클립의 최초 사진 수 대비 고유 제외 사진이 10%를 초과하면 클립 전체를 보류합니다. 상세 절차는 [라벨링 가이드](labeling-guide.md#cvat-업로드-전-얼굴번호판-검수)를 따릅니다.

로컬 근거: `data/diagnostics/desktop24_yunet_20261120/`의 `status.json`, `signal_comparison.json`, 영상별 `*_aligned.csv`, `upload_status.json`, `drive-review-snapshot.json`. 이 문서에는 영상·사진을 포함하지 않습니다.
