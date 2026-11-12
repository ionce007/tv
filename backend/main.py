# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import api_router

app = FastAPI(title="A股量化终端 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载聚合后的路由
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"msg": "欢迎使用量化终端 API"}