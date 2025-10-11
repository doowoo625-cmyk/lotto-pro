# Lotto Predictor — Render One-Click Package

## Deploy (Render)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python server_render.py`

After deploy:
- `/` → dashboard (static/index.html)
- `/api/latest` → latest round JSON
- `/api/all?start=1&end=100` → rounds JSON

CORS enabled (allow all). Uses official JSON endpoint. PORT auto-detected.
