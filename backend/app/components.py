"""Validated architecture metadata used by the API and project report."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS_PATH = ROOT / "config" / "agent_components.json"


@lru_cache(maxsize=1)
def load_components() -> dict:
    data = json.loads(COMPONENTS_PATH.read_text(encoding="utf-8"))
    if data.get("architecture") != "hybrid_single_agent":
        raise ValueError("agent_components.json architecture must be hybrid_single_agent")
    components = data.get("components")
    if not isinstance(components, list) or not components:
        raise ValueError("agent_components.json must contain components")
    required = {"id", "name_zh", "responsibility", "implementation", "tools", "data_source"}
    ids = set()
    for component in components:
        missing = required - component.keys()
        if missing:
            raise ValueError(f"component is missing fields: {sorted(missing)}")
        if component["id"] in ids:
            raise ValueError(f"duplicate component id: {component['id']}")
        if not isinstance(component["tools"], list):
            raise ValueError(f"component tools must be a list: {component['id']}")
        ids.add(component["id"])
    return data
