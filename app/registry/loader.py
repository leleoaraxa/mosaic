import os, yaml
from typing import Dict, Any

def load_views(views_dir: str) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(views_dir):
        return result
    for name in os.listdir(views_dir):
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(views_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            entity = data.get("entity") or os.path.splitext(name)[0]
            result[entity] = data
            result[entity]["__file__"] = path
    return result
