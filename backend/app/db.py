"""SQLite schema and seed: official public car facts + separately labeled synthetic demo stock."""
from __future__ import annotations

import csv
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("DRIVEMATE_DB_PATH", ROOT / "backend" / "drivemate.db"))


def connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db() -> None:
    with connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS vehicles (
              model TEXT PRIMARY KEY, category TEXT NOT NULL, powertrain TEXT NOT NULL,
              example_variant TEXT NOT NULL, price_from_twd INTEGER NOT NULL,
              seats INTEGER NOT NULL, drive TEXT NOT NULL, horsepower_hp INTEGER,
              official_range_km INTEGER, range_test_standard TEXT,
              efficiency_km_l REAL, model_source_url TEXT NOT NULL,
              spec_source_url TEXT NOT NULL, price_source_url TEXT NOT NULL,
              checked_at TEXT NOT NULL, notes TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS demo_stock (
              model TEXT PRIMARY KEY REFERENCES vehicles(model),
              quantity INTEGER NOT NULL CHECK (quantity >= 0),
              is_simulated INTEGER NOT NULL DEFAULT 1 CHECK (is_simulated = 1)
            );
            CREATE TABLE IF NOT EXISTS demo_test_drives (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              model TEXT NOT NULL REFERENCES vehicles(model),
              nickname TEXT NOT NULL,
              scheduled_at TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              status TEXT NOT NULL DEFAULT '模擬預約需求（不會傳送給經銷商）'
            );
            CREATE TABLE IF NOT EXISTS route_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              request_id TEXT NOT NULL UNIQUE,
              routing_mode TEXT NOT NULL,
              tools_used_json TEXT NOT NULL DEFAULT '[]',
              latency_ms REAL NOT NULL CHECK (latency_ms >= 0),
              success INTEGER NOT NULL CHECK (success IN (0, 1)),
              error_code TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        with (DATA_DIR / "vehicles.csv").open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                db.execute("""
                  INSERT INTO vehicles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(model) DO UPDATE SET
                    category=excluded.category,powertrain=excluded.powertrain,
                    example_variant=excluded.example_variant,price_from_twd=excluded.price_from_twd,
                    seats=excluded.seats,drive=excluded.drive,horsepower_hp=excluded.horsepower_hp,
                    official_range_km=excluded.official_range_km,
                    range_test_standard=excluded.range_test_standard,
                    efficiency_km_l=excluded.efficiency_km_l,
                    model_source_url=excluded.model_source_url,spec_source_url=excluded.spec_source_url,
                    price_source_url=excluded.price_source_url,
                    checked_at=excluded.checked_at,notes=excluded.notes
                """, (
                    row["model"], row["category"], row["powertrain"], row["example_variant"],
                    int(row["price_from_twd"]), int(row["seats"]), row["drive"],
                    int(row["horsepower_hp"]) if row["horsepower_hp"] else None,
                    int(row["official_range_km"]) if row["official_range_km"] else None,
                    row["range_test_standard"] or None,
                    float(row["efficiency_km_l"]) if row["efficiency_km_l"] else None,
                    row["model_source_url"], row["spec_source_url"], row["price_source_url"],
                    row["checked_at"], row["notes"]
                ))
        # Do not overwrite demo inventory changed during a run.
        with (DATA_DIR / "demo_stock.csv").open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                db.execute("INSERT OR IGNORE INTO demo_stock(model, quantity, is_simulated) VALUES (?, ?, 1)",
                           (row["model"], int(row["quantity"])))


def record_route_event(request_id: str, routing_mode: str, tools_used: list[str],
                       latency_ms: float, success: bool, error_code: str | None = None) -> None:
    """Store anonymous operational metadata; never store prompts or replies."""
    with connection() as db:
        db.execute(
            "INSERT INTO route_events(request_id, routing_mode, tools_used_json, latency_ms, success, error_code) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (request_id, routing_mode, json.dumps(tools_used, ensure_ascii=False),
             max(0.0, float(latency_ms)), int(success), error_code),
        )


def route_metrics() -> dict:
    """Aggregate routing counts without exposing conversation content."""
    with connection() as db:
        total = db.execute("SELECT count(*) FROM route_events").fetchone()[0]
        successful = db.execute("SELECT count(*) FROM route_events WHERE success = 1").fetchone()[0]
        rows = db.execute(
            "SELECT routing_mode, count(*) AS count, round(avg(latency_ms), 2) AS avg_latency_ms "
            "FROM route_events GROUP BY routing_mode ORDER BY count DESC, routing_mode"
        ).fetchall()
        tools = db.execute("SELECT tools_used_json FROM route_events WHERE success = 1").fetchall()
    tool_counts: dict[str, int] = {}
    for row in tools:
        for tool in json.loads(row["tools_used_json"]):
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
    return {
        "total_requests": total,
        "successful_requests": successful,
        "success_rate": round(successful / total, 4) if total else None,
        "routes": [dict(row) for row in rows],
        "tool_counts": tool_counts,
        "privacy": "Only route metadata is stored; prompts and replies are not logged.",
    }
