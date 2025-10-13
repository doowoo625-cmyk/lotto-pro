
# Lotto Predictor — Render 최종 안정판

## 파일
- requirements.txt
- server_render.py
- static/index.html

## Render 설정
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -t 120 -b 0.0.0.0:$PORT server_render:app`
- Root Directory: (코드가 루트면 비워두기 / 서브폴더면 정확히 지정)

## 점검
- /health -> {"ok": true}
- /diag -> 정적/환경/DNS 확인
- /api/probe -> 동행복권 통신 체크
- /api/stats?last=20 -> 항상 JSON (외부 실패 시 데모 JSON)
- / -> UI 로드 + 상태 표시
