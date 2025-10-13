
# Lotto Predictor — Feature Build

## 파일
- requirements.txt (httpx[http2] 포함)
- server_render.py (Fail-Open + /diag + /api/probe)
- static/index.html (기능 UI 복원: 예측번호/전략카드/최근10회/구간빈도/전략상세)

## Render 설정
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -t 120 -b 0.0.0.0:$PORT server_render:app`
- Root Directory: 정확히 설정

## 확인
- /health -> {"ok": true}
- /diag -> 정적/환경/DNS
- /api/probe -> 외부 통신 체크
- /api/stats?last=50 -> 항상 JSON
- / -> 전체 UI 로드
