import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests, re
from bs4 import BeautifulSoup
from pathlib import Path
import pandas as pd

app = FastAPI()

# ✅ CORS (웹 API 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 정적 파일 경로
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ✅ 최신 회차 크롤링
def get_latest():
    r = requests.get("https://www.dhlottery.co.kr/gameResult.do?method=byWin")
    s = BeautifulSoup(r.text, "html.parser")
    t = s.select_one("meta[property='og:title']")["content"]
    m = re.search(r"제(\d+)회", t)
    return int(m.group(1)) if m else 0

# ✅ 특정 회차 크롤링
def fetch_round(n):
    url = f"https://www.dhlottery.co.kr/gameResult.do?method=byWin&drwNo={n}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    nums = [int(x.text) for x in soup.select(".nums .num")]
    bonus = int(soup.select_one(".num.bonus").text)
    date = soup.select_one(".desc").text.strip().split(" ")[0]
    return {"round": n, "date": date, "nums": nums, "bonus": bonus}

@app.get("/api/latest")
def latest():
    return {"latest": get_latest()}

@app.get("/api/all")
def all_data(start: int = 1, end: int = None):
    if end is None:
        end = get_latest()
    results = []
    for i in range(start, end + 1):
        try:
            results.append(fetch_round(i))
        except Exception:
            continue
    return {"rows": results}

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

# ✅ Render 환경 포트 적용
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server_render:app", host="0.0.0.0", port=port)
