# ASGI entrypoint for Render when using gunicorn + uvicorn worker
# Command example:
# gunicorn -k uvicorn.workers.UvicornWorker -w 2 -t 120 -b 0.0.0.0:$PORT server_render:app

from app.main import app  # FastAPI() instance named 'app'
