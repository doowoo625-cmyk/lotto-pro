
from __future__ import annotations
import httpx
from typing import Dict, Any, List

API = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={no}"

async def fetch_draw(no: int) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(API.format(no=no))
        r.raise_for_status()
        data = r.json()
    nums = [data.get(f"drwtNo{i}") for i in range(1,7)]
    nums = [int(x) for x in nums if isinstance(x, int)]
    nums.sort()
    return {
        "draw_no": int(data.get("drwNo", no)),
        "numbers": nums,
        "bonus": int(data.get("bnusNo", 0)),
        "date": data.get("drwNoDate")
    }

async def fetch_recent(end_no: int, n: int = 10) -> List[Dict[str, Any]]:
    if end_no >= 9999:
        # try probing downwards to find the latest existing draw
        cur = end_no
        while cur > 0:
            try:
                d = await fetch_draw(cur)
                end_no = d["draw_no"]
                break
            except Exception:
                cur -= 1
    start = max(1, end_no - n + 1)
    items: List[Dict[str, Any]] = []
    for no in range(start, end_no+1):
        items.append(await fetch_draw(no))
    return items
