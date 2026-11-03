"""Small, auditable tool API. Actual price specs from public source; stocks are fake."""
import json
from .db import connection


def search_vehicles(max_price_twd: int = 0, powertrain: str = "") -> dict:
    """Find Volvo models within a budget and/or by powertrain. 0 means any budget."""
    max_price_twd = int(max_price_twd or 0)
    if max_price_twd < 0:
        return {"error": "預算不能為負數"}
    with connection() as db:
        rows = db.execute(
            "SELECT model, category, powertrain, price_from_twd, price_source_url, checked_at FROM vehicles "
            "WHERE (? = 0 OR price_from_twd <= ?) AND (? = '' OR powertrain LIKE ?) ORDER BY price_from_twd, model",
            (max_price_twd, max_price_twd, powertrain, f"%{powertrain}%"),
        ).fetchall()
    return {"results": [dict(r) for r in rows], "price_type": "官方車系建議起售價；不是特定配備最終成交價",
            "no_results": len(rows) == 0}


def get_vehicle_details(model: str) -> dict:
    """Get official public price and specs for a specific model: EX30, XC40, EX40, XC60."""
    with connection() as db:
        row = db.execute("SELECT * FROM vehicles WHERE model = ?", (model.strip().upper(),)).fetchone()
    return ({"vehicle": dict(row), "price_type": "官方車系建議起售價；規格為 example_variant 指定版本"}
            if row else {"error": f"找不到車型 {model}；目前資料僅含 EX30、XC40、EX40、XC60"})


def check_demo_stock(model: str) -> dict:
    """Query synthetic inventory used ONLY for the assignment. NOT Volvo's live stock."""
    with connection() as db:
        row = db.execute("SELECT model, quantity FROM demo_stock WHERE model = ?", (model.strip().upper(),)).fetchone()
    return ({"inventory": dict(row), "is_simulated": True, "warning": "這是期中專題虛構庫存，非 Volvo 真實庫存。"}
            if row else {"error": "找不到模擬庫存資料", "is_simulated": True})


TOOL_FUNCTIONS = {
    "search_vehicles": search_vehicles,
    "get_vehicle_details": get_vehicle_details,
    "check_demo_stock": check_demo_stock,
}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "search_vehicles", "description": "Search public Volvo models by maximum TWD budget and/or exact powertrain tag. Call this for a list of models or price budget.",
        "parameters": {"type": "object", "properties": {
            "max_price_twd": {"type": "integer", "description": "Maximum budget in Taiwan dollars, 0 = no budget filter"},
            "powertrain": {"type": "string", "description": "Optional match: 純電動 / 高效輕油電, blank for all"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_vehicle_details", "description": "Look up official Volvo car information and price for model EX30, XC40, EX40 or XC60. Required for exact specs and price.",
        "parameters": {"type": "object", "properties": {"model": {"type": "string"}}, "required": ["model"]}}},
    {"type": "function", "function": {
        "name": "check_demo_stock", "description": "Look up DEMO SIMULATED vehicle stock only; never claim it is real dealer availability.",
        "parameters": {"type": "object", "properties": {"model": {"type": "string"}}, "required": ["model"]}}},
]


def execute(name: str, arguments: dict) -> str:
    if name not in TOOL_FUNCTIONS:
        return json.dumps({"error": "未知工具"}, ensure_ascii=False)
    try:
        fn = TOOL_FUNCTIONS[name]
        clean = {k: v for k, v in arguments.items() if k in fn.__code__.co_varnames[:fn.__code__.co_argcount]}
        return json.dumps(fn(**clean), ensure_ascii=False)
    except (TypeError, ValueError, OverflowError) as exc:
        return json.dumps({"error": f"參數有誤：{exc}"}, ensure_ascii=False)
