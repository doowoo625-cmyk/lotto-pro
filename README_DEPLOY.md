
# Lotto Predictor — Full UI Build

## 무엇이 포함되나
- /api/analysis: 
  - ① 예측 5세트 + 각 번호 근거(%) 
  - ② 이번주 전략카드(전략명/평균 Score/RR/추정 승률)
  - ③ 최근 10회 데이터 (회차점프는 프런트 입력으로 이동)
  - ④ 구간별 번호 빈도(1~10, 11~20, 21~30, 31~40, 41~45 + 합계)
  - ⑤ 전략별 추천 상세(보수/균형/고위험 각 Top 5)

## Render 설정
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -t 120 -b 0.0.0.0:$PORT server_render:app`

## 점검
- /api/analysis -> 위 필드 모두 포함한 JSON
- / -> 풀 UI 화면 로드
