
from __future__ import annotations
import httpx
from typing import Optional, Dict, Any

LOTTO_API = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={no}"

async def fetch_draw(drw_no: int) -> Optional[Dict[str, Any]]:
    url = LOTTO_API.format(no=drw_no)
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        data = r.json()
        if data.get("returnValue") != "success":
            return None
        nums = [data.get(f"drwtNo{i}") for i in range(1,7)]
        if None in nums:
            return None
        return {
            "draw_no": data.get("drwNo"),
            "numbers": sorted([int(x) for x in nums]),
            "bonus": int(data.get("bnusNo", 0) or 0),
            "date": data.get("drwNoDate"),
        }
