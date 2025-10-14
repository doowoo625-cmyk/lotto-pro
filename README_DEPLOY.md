# lotto_render_stable (v2.1-stable)

의존성 최소화(표준 csv 사용)로 Render 빌드 실패(metadata-generation-failed) 원천 차단.

## 구조
```
lotto_render_stable/
├── server_render.py
├── requirements.txt
├── static/
│   ├── index.html
│   └── sample_results.csv
└── README_DEPLOY.md
```

## Render 설정
Build Command
```
pip install -r requirements.txt
```
Start Command
```
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -t 120 -b 0.0.0.0:$PORT server_render:app
```

## 로컬 실행
```
pip install -r requirements.txt
uvicorn server_render:app --host 0.0.0.0 --port 8000
# http://localhost:8000
```
