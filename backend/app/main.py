"""FastAPI backend for independent academic demo using public Volvo facts."""
from __future__ import annotations

import os
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
from .agent import OPENING, OLLAMA_MODEL, chat  # noqa: E402
from .components import load_components  # noqa: E402
from .db import connection, init_db, record_route_event, route_metrics  # noqa: E402
from .rag import load_index, RagNotReady  # noqa: E402

logger = logging.getLogger("drivemate")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    load_components()
    yield


app = FastAPI(title="DriveMate Volvo Academic Demo API", version="0.5.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

def save_route_event(request_id: str, routing_mode: str, tools_used: list[str],
                     started_at: float, success: bool, error_code: str | None = None) -> None:
    """Metrics must never make an otherwise valid chat request fail."""
    try:
        record_route_event(request_id, routing_mode, tools_used,
                           (perf_counter() - started_at) * 1000, success, error_code)
    except sqlite3.Error:
        logger.warning("Unable to save route metric for request_id=%s", request_id, exc_info=True)


def service_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, {"code": code, "message": message})


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


@app.get("/api/system/components")
def system_components():
    """Public, non-secret architecture metadata for audit and reporting."""
    return load_components()


@app.get("/api/metrics/routes")
def routing_metrics():
    return route_metrics()


@app.get("/api/demo-bookings")
def demo_bookings():
    with connection() as db:
        rows = db.execute("SELECT id, model, nickname, scheduled_at, status FROM demo_test_drives ORDER BY id DESC LIMIT 20").fetchall()
    return {"records": [dict(row) for row in rows], "is_simulated": True}


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    if request.messages[-1].role != "user" or any(m.role not in ("user", "assistant") for m in request.messages):
        raise HTTPException(400, "只接受 user/assistant 對話，最後一則必須是 user")
    request_id = str(uuid4())
    started_at = perf_counter()
    try:
        reply, tools_used, routing_mode = await chat([m.model_dump() for m in request.messages])
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        save_route_event(request_id, "error", [], started_at, False, "OLLAMA_UNAVAILABLE")
        logger.warning("Ollama unavailable request_id=%s", request_id, exc_info=True)
        raise service_error(503, "OLLAMA_UNAVAILABLE", "無法連接 Ollama，請確認服務與模型已啟動。") from exc
    except httpx.HTTPStatusError as exc:
        save_route_event(request_id, "error", [], started_at, False, "MODEL_API_ERROR")
        logger.warning("Ollama returned an error request_id=%s", request_id, exc_info=True)
        raise service_error(502, "MODEL_API_ERROR", "本地模型服務回傳錯誤，請查看後端紀錄。") from exc
    except RagNotReady as exc:
        save_route_event(request_id, "error", [], started_at, False, "RAG_NOT_READY")
        raise service_error(503, "RAG_NOT_READY", str(exc)) from exc
    except sqlite3.Error as exc:
        save_route_event(request_id, "error", [], started_at, False, "DATABASE_ERROR")
        logger.exception("Database error request_id=%s", request_id)
        raise service_error(500, "DATABASE_ERROR", "資料庫暫時無法使用。") from exc
    except Exception as exc:
        save_route_event(request_id, "error", [], started_at, False, "INTERNAL_ERROR")
        logger.exception("Unexpected chat error request_id=%s", request_id)
        raise service_error(500, "INTERNAL_ERROR", "系統發生未預期錯誤，請提供請求編號給開發者。") from exc
    save_route_event(request_id, routing_mode, tools_used, started_at, True)
    return {"reply": reply, "tools_used": tools_used, "routing_mode": routing_mode,
            "model": OLLAMA_MODEL, "opening": OPENING, "request_id": request_id}


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
