"""FastAPI backend for independent academic demo using public Volvo facts."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
from .agent import OPENING, OLLAMA_MODEL, chat  # noqa: E402
from .db import connection, init_db  # noqa: E402
from .rag import load_index, RagNotReady  # noqa: E402

app = FastAPI(title="DriveMate Volvo Academic Demo API", version="0.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.on_event("startup")
def startup():
    init_db()


class ChatMessage(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=2500)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)


class DemoBooking(BaseModel):
    model: str
    nickname: str = Field(min_length=1, max_length=24)
    scheduled_at: str = Field(description="Future Taipei local time YYYY-MM-DDTHH:MM")
    confirmed: bool


@app.get("/health")
def health():
    return {"status": "ok", "app": "DriveMate", "model": OLLAMA_MODEL, "official_volvo_app": False}


@app.get("/api/rag/status")
def rag_status():
    try:
        index = load_index()
        return {"ready": True, "embedding_model": index["embedding_model"],
                "chunks": len(index["chunks"])}
    except (RagNotReady, ValueError, KeyError):
        return {"ready": False, "message": "請先下載 Embedding 模型並執行 python -m backend.app.rag --build"}


@app.get("/api/catalog")
def catalog():
    with connection() as db:
        cars = [dict(r) for r in db.execute("SELECT * FROM vehicles ORDER BY price_from_twd, model").fetchall()]
    return {"vehicles": cars, "disclaimer": "車型與起售價來源為 Volvo 台灣公開網站；庫存與預約為課堂模擬。"}


@app.get("/api/demo-bookings")
def demo_bookings():
    with connection() as db:
        rows = db.execute("SELECT id, model, nickname, scheduled_at, status FROM demo_test_drives ORDER BY id DESC LIMIT 20").fetchall()
    return {"records": [dict(row) for row in rows], "is_simulated": True}


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if request.messages[-1].role != "user" or any(m.role not in ("user", "assistant") for m in request.messages):
        raise HTTPException(400, "只接受 user/assistant 對話，最後一則必須是 user")
    try:
        reply, tools_used, routing_mode = await chat([m.model_dump() for m in request.messages])
    except Exception as exc:
        # Do not turn service failure into a fabricated sales answer.
        raise HTTPException(503, "無法連接 Ollama。請確認 ollama serve 已啟動且模型已下載。") from exc
    return {"reply": reply, "tools_used": tools_used, "routing_mode": routing_mode,
            "model": OLLAMA_MODEL, "opening": OPENING}


@app.post("/api/demo-bookings", status_code=201)
def create_demo_booking(data: DemoBooking):
    if not data.confirmed:
        raise HTTPException(400, "必須勾選確認：這只是課堂模擬預約")
    if any(ch.isdigit() for ch in data.nickname) and len(data.nickname) >= 10:
        raise HTTPException(400, "僅需虛構暱稱，請勿填寫真實電話或身分證")
    try:
        selected = datetime.fromisoformat(data.scheduled_at)
    except ValueError as exc:
        raise HTTPException(400, "預約時間格式錯誤") from exc
    if selected.tzinfo is not None:
        raise HTTPException(400, "請使用台灣當地時間，不需時區後綴")
    now = datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None)
    if selected <= now:
        raise HTTPException(400, "模擬預約時間必須在未來")
    if selected > now.replace(year=now.year + 2):
        raise HTTPException(400, "模擬預約日期距今不可超過兩年")
    with connection() as db:
        exists = db.execute("SELECT 1 FROM vehicles WHERE model = ?", (data.model.upper(),)).fetchone()
        if not exists:
            raise HTTPException(404, "車型不在本專題的資料庫中")
        result = db.execute("INSERT INTO demo_test_drives(model, nickname, scheduled_at) VALUES (?, ?, ?)",
                            (data.model.upper(), data.nickname.strip(), selected.isoformat(timespec="minutes")))
        booking_id = result.lastrowid
    return {"id": booking_id, "status": "已建立模擬試乘需求（非正式預約，沒有保留真實時段）", "is_simulated": True}
