# lotto_render_full_fixed (v2.1-fix)

Render + 로컬 실행 모두 지원하는 완성본.

## 구조
```
lotto_render_full_fixed/
├── server_render.py
├── requirements.txt
├── static/
│   ├── index.html
│   └── sample_results.csv
└── README_DEPLOY.md
```

## 로컬 실행
```bash
pip install -r requirements.txt
uvicorn server_render:app --host 0.0.0.0 --port 8000
# 브라우저에서 http://localhost:8000
```

## API
- `GET /api/analysis?last=10&high_cut=23`
  - `last`: 최근 N회 분석 (기본 10)
  - `high_cut`: 고번호 기준 (기본 23, 1~45)
  - 응답: 최근 N회(합/홀/고번호), 구간별 빈도, 예측 조합(가중치/랜덤)
