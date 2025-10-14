# Lotto Prediction System v3.1-final — Render 전용(파이썬 3.13 호환)

- gunicorn + uvicorn worker
- pydantic v2 문법(`conlist(min_length, max_length)`) 반영
- Start/Build 커맨드 Render 로그 기준으로 맞춤

## 배포
- Blueprint 또는 일반 Web Service로 배포
- / → index.html, /api/health, /api/last_draw, /api/predict
