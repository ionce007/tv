# backend/src/api/routes/kline.py
from fastapi import APIRouter, HTTPException, Query
from ..controllers.kline_controller import get_kline_data

router = APIRouter()

@router.get("/kline")
async def get_kline(
    symbol: str = Query(..., description="股票代码，如 sh600000"),
    limit: int = Query(300, ge=50, le=5000, description="每次加载数量"),
    before_date: str | None = Query(None, description="获取该日期之前的数据"),
    anchor_date: str | None = Query(None, description="AVWAP锚定日期"),
):
    """获取股票历史 K 线及计算好的指标数据"""
    try:
        data = get_kline_data(symbol, limit, before_date, anchor_date)
        
        if data is None:
            raise HTTPException(status_code=404, detail="未找到该股票数据")
            
        if len(data) == 0:
            return {"code": 200, "msg": "no more data", "data": []}
            
        return {"code": 200, "msg": "success", "data": data}
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))