
# Lotto Prediction System v3.1-final (Render + Local)

완성형 배포본입니다. Render(무료 플랜)와 로컬 실행을 모두 지원합니다.

## 특징
- FastAPI 기반 백엔드 + 순수 HTML/JS 정적 프런트
- **상단 상태 카드에 직전 회차 숫자 표기**
- **"예측 번호 뽑기" (자동 생성이 아닌 버튼 클릭식)**
- **보수형 / 균형형 / 고위험형 전략별 최고 조합 1개씩 + 우선순위 오름차순 정렬**
- **label: "Lower score = higher probability" 포함**
- 전략별 전체 후보 리스트 및 score/근거 제공
- `data/last_draw.json` 파일로 직전 회차 결과 관리 (UI에서도 수정 가능)

## 로컬 실행
```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# 브라우저에서 http://127.0.0.1:8000 접속
```

## Render 배포
1. 이 리포를 GitHub에 업로드
2. Render에서 **New > Web Service** 선택 → 연결
3. Root: `/` , Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. 배포 완료 후 도메인 접속

또는 `render.yaml`을 사용해 **Blueprint**로 배포 가능합니다.

## API 개요
- `GET /api/health` → 상태 확인
- `GET /api/last_draw` → 직전 회차 조회
- `POST /api/last_draw` → 직전 회차 저장 (body: `{draw_no, numbers[6], bonus}`)
- `POST /api/predict` → 예측 생성 (body: `{seed?, count=5}`)

## 점수(Score) 기준
- 마지막 회차와의 **중복 최소화**
- **합계가 중간대(≈138)** 에 근접
- **숫자 분포(최대-최소)**, **홀짝 균형**, **연속 숫자 패턴** 및 **끝자리 중복** 등을 고려
- **점수 낮을수록 유리**하다고 해석

## 테스트
```bash
pytest -q
```

## 라이선스
MIT
