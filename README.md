# Lotto Predictor

완전 실행형 로또 예측 시스템 (웹).

## 실행 방법

```bash
pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

브라우저: http://127.0.0.1:8000

## 기능
- ① 예측 번호 → ② 이번 주 추천 전략 카드 → ③ 최근 결과/회차 점프 → ④ 구간별 번호 빈도 → ⑤ 전략별 추천(상세)
- 동행복권 JSON API를 통해 실데이터 자동 수집
- 색상 일관(1~10 노랑, 11~20 파랑, 21~30 빨강, 31~40 보라, 41~45 초록)
- Adaptive 전략 자동 추천
- 최근 10회만 테이블에 표시, 전체 데이터는 분석용으로만 사용
