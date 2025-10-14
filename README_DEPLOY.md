# Lotto Predictor — v3.0-final (Render-ready)
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn -k uvicorn.workers.UvicornWorker -w 2 -t 120 -b 0.0.0.0:$PORT server_render:app`
- Health: `/health`
- Data: `/api/analysis?last=10` or `/api/analysis?last=10&anchor=1200`
