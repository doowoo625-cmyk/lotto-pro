# Lotto Prediction System v3.1-final (Render 전용, Fix)

이 패키지는 Render에서 'Exited with status 127' (명령을 찾을 수 없음) 문제를 피하기 위해
`startCommand`를 `python -m uvicorn` 방식으로 고정했습니다.

## 배포
1) GitHub 업로드 후 Render Blueprint Deploy
2) buildCommand: `pip install --upgrade pip && pip install -r requirements.txt`
3) startCommand: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## 점검
- Deploy logs에서 'Uvicorn running on' 메시지 확인
- 접속: https://<service>.onrender.com (루트 경로는 index.html)
