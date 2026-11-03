"""Auditable safety net when a small LLM does not issue a needed tool call.

Important: this is deterministic Python routing, NOT an LLM-issued tool call.
It executes the same audited tools and reports routing_mode='backend_fallback'.
It only handles narrow, well-understood patterns; ambiguous requests are rejected.
"""
from __future__ import annotations

import re
from typing import Any

from .tools import check_demo_stock, get_vehicle_details, search_vehicles

MODEL_PATTERN = re.compile(r"(?<![A-Z0-9])(?:EX|XC)\d{2,4}(?![A-Z0-9])", re.I)


def models_in(text: str) -> list[str]:
    return list(dict.fromkeys(m.upper() for m in MODEL_PATTERN.findall(text)))


def _budget(text: str) -> int | None:
    """Recognize 200萬, 200 萬元, NT$2,000,000, 2000000 元 etc."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*萬", text)
    if match:
        return int(float(match.group(1)) * 10000)
    match = re.search(r"(?:NT\$|新台幣|預算|售價|價格)?\s*\$?\s*([\d,]{6,10})\s*(?:元|塊|以下|以內|內)?", text, re.I)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def _money(value: int) -> str:
    return f"NT${value:,}"


def _vehicle_line(car: dict[str, Any]) -> str:
    line = f"- **{car['model']}**：{_money(car['price_from_twd'])} 起（{car['powertrain']}，{car['category']}）"
    if car.get('price_source_url'):
        line += f" [官方售價來源]({car['price_source_url']})"
    return line


def route_and_answer(query: str, previous_messages: list[dict] | None = None) -> tuple[str, list[str]] | None:
    """Return (grounded_reply, executed_tool_names), or None for unsupported cases."""
    models = models_in(query)
    # Contextual follow-up only when previous user turns clearly refer to one model.
    if not models and re.search(r"那(?:它|這台|這款)|它的|這台的", query):
        for m in reversed(previous_messages or []):
            if m.get('role') != 'user':
                continue
            prior = models_in(m.get('content', ''))
            if len(prior) == 1:
                models = prior
                break
            if len(prior) > 1:
                break

    if re.search(r"(?:庫存|現車|有幾台|剩幾台)", query):
        if len(models) != 1:
            return ("請指定一款車型（EX30、EX40、XC40 或 XC60），才能查詢**課堂模擬庫存**。", [])
        result = check_demo_stock(models[0])
        if "error" in result:
            return (f"找不到 {models[0]} 的模擬庫存資料。這不代表真實 Volvo 庫存。", ["check_demo_stock"])
        return (f"**{models[0]} 課堂模擬庫存：{result['inventory']['quantity']} 台。**\n\n"
                "此數量為專題虛構資料，**不是 Volvo 經銷商的實際庫存或現車數量**。",
                ["check_demo_stock"])

    if len(models) >= 2:
        results = [get_vehicle_details(m) for m in models]
        names = ["get_vehicle_details"] * len(models)
        missing = [m for m, r in zip(models, results) if "error" in r]
        if missing:
            return (f"無法比較：資料庫找不到 {', '.join(missing)}。目前僅收錄 EX30、EX40、XC40、XC60。", names)
        cars = [r["vehicle"] for r in results]
        if "馬力" in query:
            if any(c.get("horsepower_hp") is None for c in cars):
                return ("資料庫缺少部分車型的馬力規格，無法比較。", names)
            lines = [f"- **{c['model']}（{c['example_variant']}）**：{c['horsepower_hp']} hp "
                     f"[官方規格來源]({c['spec_source_url']})" for c in cars]
            top = max(cars, key=lambda x: x['horsepower_hp'])
            bottom = min(cars, key=lambda x: x['horsepower_hp'])
            difference = top['horsepower_hp'] - bottom['horsepower_hp']
            summary = f"**{top['model']} 的示例版本馬力較高**" + (f"，比 {bottom['model']} 高 {difference} hp。" if difference else "（兩者相同）。")
            return ("依資料庫收錄的**指定版本**比較：\n\n" + "\n".join(lines) + "\n\n" + summary
                    + "\n\n請注意不同配備版本可能有不同動力，以上並非車系所有版本比較。", names)
        if any(k in query for k in ("售價", "價格", "便宜", "貴", "預算")):
            lines = [_vehicle_line(c) for c in cars]
            lowest = min(cars, key=lambda c: c["price_from_twd"])
            return ("**公開車系建議起售價比較：**\n\n" + "\n".join(lines)
                    + f"\n\n**起售價最低：{lowest['model']}。** 起售價不是指定動力版本的成交價。", names)
        lines = [f"- **{c['model']}（{c['example_variant']}）**：{c['powertrain']}、"
                 f"{c['horsepower_hp']} hp、車系建議起售價 {_money(c['price_from_twd'])} 起"
                 for c in cars]
        return ("以下是資料庫收錄車型的基本比較：\n\n" + "\n".join(lines)
                + "\n\n馬力為指定示例版本規格；起售價不代表該版本成交價。", names)

    if models:
        data = get_vehicle_details(models[0])
        if "error" in data:
            return (f"查無 **{models[0]}** 的車型資料。\n\n目前資料庫只有 EX30、EX40、XC40、XC60，無法提供未收錄車型的售價或規格。", ["get_vehicle_details"])
        c = data["vehicle"]
        lines = [f"**{c['model']}** 車型資訊：",
                 f"- 車系建議起售價：**{_money(c['price_from_twd'])} 起**（非成交價）",
                 f"- 車型／能源：{c['category']}／{c['powertrain']}",
                 f"- 示範動力版本：{c['example_variant']}",
                 f"- 馬力：{c['horsepower_hp']} hp",
                 f"- 座位：{c['seats']} 人座"]
        if c.get("official_range_km") is not None:
            lines.append(f"- 官方標示最高續航：{c['official_range_km']} km（{c.get('range_test_standard') or '依官網標準'}）")
        lines.append(f"\n[Volvo 官方規格來源]({c['spec_source_url']})")
        lines.append("\n車系起售價與示例版本規格分開列示，請勿把起售價當成該示例版本的報價。")
        return ("\n".join(lines), ["get_vehicle_details"])

    if re.search(r"車型|有哪些車|車款|預算|萬(?:元)?以內|萬(?:元)?以下|純電|休旅|便宜", query):
        money = _budget(query)
        if money is not None and money < 0:
            return ("預算不能是負數。", [])
        kw = "純電動" if "純電" in query else "高效輕油電" if "輕油電" in query else ""
        result = search_vehicles(max_price_twd=money or 0, powertrain=kw)
        rows = result["results"]
        if not rows:
            return ("目前本專題收錄的車型中，找不到符合條件的資料。", ["search_vehicles"])
        budget_note = f"在 **{_money(money)}** 預算以內" if money else "在目前資料庫中"
        return (f"{budget_note}，找到 **{len(rows)} 款**車型：\n\n" + "\n".join(_vehicle_line(c) for c in rows)
                + "\n\n價格為 Volvo 公開車系建議起售價，非實際成交價；是否可購得特定配置仍須向經銷商確認。",
                ["search_vehicles"])
    return None


def covers_query(query: str, executed_calls: list[tuple[str, dict]]) -> bool:
    """Did LLM actually invoke the specific tool(s) required by this query?

    This is a *coverage* check, not a correctness score for the model's prose.
    """
    models = models_in(query)
    def used(name: str, model: str | None = None) -> bool:
        return any(tool == name and (model is None or str(args.get('model', '')).strip().upper() == model)
                   for tool, args in executed_calls)
    if re.search(r"(?:庫存|現車|有幾台|剩幾台)", query) and models:
        return len(models) == 1 and used('check_demo_stock', models[0])
    if models:
        return all(used('get_vehicle_details', m) for m in models)
    if re.search(r"車型|有哪些車|車款|預算|萬(?:元)?以內|萬(?:元)?以下|純電|休旅|便宜", query):
        if not used('search_vehicles'):
            return False
        budget = _budget(query)
        if budget is not None:
            return any(name == 'search_vehicles'
                       and int(args.get('max_price_twd', 0) or 0) == budget
                       for name, args in executed_calls
                       if str(args.get('max_price_twd', 0) or 0).isdigit())
    return True
