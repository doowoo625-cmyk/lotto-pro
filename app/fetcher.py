# app/fetcher.py
from __future__ import annotations
import asyncio, time
import httpx
from typing import Dict, Any, List

API = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={no}"

_TTL = 300  # 5분
_cache: dict[str, tuple[float, Any]] = {}

def _get_cache(k: str):
    v = _cache.get(k)
    if not v: return None
    ts, data = v
    if time.time() - ts > _TTL:
        _cache.pop(k, None)
        return None
    return data

def _set_cache(k: str, val: Any):
    _cache[k] = (time.time(), val)
    return val

async def _request_json(url: str, client: httpx.AsyncClient, retries: int = 1, timeout: float = 3.0):
    last = None
    for _ in range(retries+1):
        try:
            r = await client.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0 LottoFetcher"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            await asyncio.sleep(0.15)
    raise last

async def fetch_draw(no: int) -> Dict[str, Any]:
    key = f"draw:{no}"
    hit = _get_cache(key)
    if hit: return hit
    async with httpx.AsyncClient(http2=True) as client:
        data = await _request_json(API.format(no=no), client)
    nums = [data.get(f"drwtNo{i}") for i in range(1,7)]
    nums = [int(x) for x in nums if isinstance(x, int)]
    nums.sort()
    out = {
        "draw_no": int(data.get("drwNo", no)),
        "numbers": nums,
        "bonus": int(data.get("bnusNo", 0)),
        "date": data.get("drwNoDate")
    }
    return _set_cache(key, out)

async def fetch_recent(end_no: int, n: int = 10) -> List[Dict[str, Any]]:
    key = f"recent:{end_no}:{n}"
    hit = _get_cache(key)
    if hit: return hit
    start = max(1, end_no - n + 1)
    async with httpx.AsyncClient(http2=True) as client:
        datas = await asyncio.gather(*[
            _request_json(API.format(no=no), client) for no in range(start, end_no+1)
        ])
    items = []
    for d in datas:
        nums = [d.get(f"drwtNo{i}") for i in range(1,7)]
        nums = [int(x) for x in nums if isinstance(x, int)]
        nums.sort()
        items.append({
            "draw_no": int(d.get("drwNo", 0)),
            "numbers": nums,
            "bonus": int(d.get("bnusNo", 0)),
            "date": d.get("drwNoDate")
        })
    items.sort(key=lambda x: x["draw_no"])
    return _set_cache(key, items)

async def latest_draw_no(probe_start: int = 9999) -> int:
    key = "latest_no"
    hit = _get_cache(key)
    if hit: return hit
    no = probe_start
    async with httpx.AsyncClient(http2=True) as client:
        while no > 0:
            try:
                d = await _request_json(API.format(no=no), client)
                if d.get("returnValue") == "success":
                    return _set_cache(key, int(d.get("drwNo", no)))
            except Exception:
                pass
            no -= 1
    return _set_cache(key, 1)
