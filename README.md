# Lotto Prediction System v3.1-final (Render 전용)

Render 무료플랜 기준, 단 1분만에 바로 실행 가능한 완성판입니다.

## 주요 특징
- FastAPI 기반 API + HTML/JS UI
- 보수형, 균형형, 고위험형 3가지 전략 예측
- score 낮을수록 확률 높음
- 상단 상태 카드에 직전 회차 숫자 표시
- Render 환경 자동 배포 지원 (render.yaml 포함)

## 배포 방법
1. GitHub에 이 폴더 전체 업로드
2. Render Dashboard → **Blueprint Deploy**
3. 자동으로 빌드 및 실행
4. 완료 후 발급 도메인 접속

## API
- GET /api/health
- GET /api/last_draw
- POST /api/last_draw
- POST /api/predict

## 수동 실행 테스트 (선택)
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
