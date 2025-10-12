# Lotto Predictor — 최종본

## 배포 (3단계)
1) ZIP 압축을 풀어 **리포지토리 루트**에 그대로 업로드(덮어쓰기) → 커밋/푸시
2) Render:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -t 120 -b 0.0.0.0:$PORT server_render:app`
   - (서브폴더라면 Settings → Root Directory 지정)
3) 점검:
   - `/health` → `{ "ok": true }`
   - `/api/stats?last=20` → JSON
   - `/` → UI

## 구성
- server_render.py — FastAPI 서버(Fail-Open)
- static/index.html — 프론트엔드
- requirements.txt — 패키지
- render.yaml — Render 설정
