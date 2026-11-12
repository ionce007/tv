# backend/src/api/schemas.py
from pydantic import BaseModel

class KlineRequest(BaseModel):
    symbol: str = "sh600000"
    limit: int = 200
    anchor_date: str | None = None
    show_sma: bool = True
    show_kama: bool = False
    show_boll: bool = False
    show_avwap: bool = False