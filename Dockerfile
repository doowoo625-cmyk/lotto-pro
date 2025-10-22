# ---- base image ----
FROM python:3.11-slim

# ---- working directory ----
WORKDIR /app

# ---- copy project ----
COPY . /app

# ---- install dependencies ----
RUN pip install --no-cache-dir -r requirements.txt

# ---- expose port (Render uses $PORT env) ----
EXPOSE 8000

# ---- start command ----
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-t", "60", "-b", "0.0.0.0:$PORT", "app.main:app"]
