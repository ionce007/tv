# backend/src/api/routes/__init__.py
from fastapi import APIRouter
from .kline import router as kline_router

api_router = APIRouter()
api_router.include_router(kline_router, tags=["K线数据"])
# 未来新增其他接口（如 CVD、选股、回测），只需在这里 include_router 即可
# api_router.include_router(orderflow_router, tags=["订单流"])