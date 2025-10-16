#!/usr/bin/env python3
"""Auditoria de colunas entre YAMLs e código/tests.

1. Gera inventário em tmp/schema_inventory.json.
2. Procura usos repo-wide para identificar lacunas.
3. Produz REPORT.md com tabelas solicitadas.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
VIEWS_DIR = ROOT / "data" / "views"
TMP_DIR = ROOT / "tmp"
REPORT_PATH = ROOT / "REPORT.md"
INVENTORY_PATH = TMP_DIR / "schema_inventory.json"
CODE_DIRS = [ROOT / "app", ROOT / "tests"]

SUFFIX_MAP = {
    "date": ("_date", "_until", "_at"),
    "amt": ("_amt",),
    "price": ("_price",),
    "pct": ("_pct",),
    "area": ("_area",),
    "value": ("_value",),
    "ratio": ("_ratio",),
    "rate": ("_rate",),
    "share": ("_share",),
    "alpha": ("_alpha",),
    "index": ("_index",),
    "count": ("_count",),
}

LEGACY_SUFFIXES = {"_amount"}


@dataclass
class ColumnMeta:
    view: str
    column: str
    declared_type: Optional[str]
    suffix_class: str


def infer_suffix(name: str) -> str:
    for suffix_class, suffixes in SUFFIX_MAP.items():
        for suf in suffixes:
            if name.endswith(suf):
                return suffix_class
    for suf in LEGACY_SUFFIXES:
        if name.endswith(suf):
            return f"legacy:{suf}"
    return "generic"


def iter_columns(meta: Dict[str, Any]) -> Iterable[str]:
    cols = meta.get("columns") or []
    for c in cols:
        if isinstance(c, str):
            name = c
        elif isinstance(c, dict):
            name = c.get("name") or c.get("alias")
        else:
            name = None
        if name:
            yield name


def load_inventory() -> List[ColumnMeta]:
    items: List[ColumnMeta] = []
    if not VIEWS_DIR.exists():
        return items
    for path in sorted(VIEWS_DIR.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        view = data.get("entity") or path.stem
        for col in iter_columns(data):
            suffix = infer_suffix(col)
            items.append(
                ColumnMeta(
                    view=view,
                    column=col,
                    declared_type=data.get("types", {}).get(col),
                    suffix_class=suffix,
                )
            )
    return items


def ensure_tmp_dir() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def write_inventory_json(inventory: List[ColumnMeta]) -> None:
    ensure_tmp_dir()
    payload = [
        {
            "view_name": item.view,
            "column_name": item.column,
            "declared_type_if_any": item.declared_type,
            "suffix_class": item.suffix_class,
        }
        for item in inventory
    ]
    INVENTORY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ripgrep(pattern: str, paths: List[Path]) -> List[str]:
    cmd = ["rg", "-n", pattern] + [str(p.relative_to(ROOT)) for p in paths]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []
    if proc.returncode not in (0, 1):
        return proc.stdout.strip().splitlines() + proc.stderr.strip().splitlines()
    return [line for line in proc.stdout.strip().splitlines() if line]


def collect_unreferenced_columns(inventory: List[ColumnMeta]) -> List[Dict[str, str]]:
    unused: List[Dict[str, str]] = []
    for item in inventory:
        hits = ripgrep(item.column, CODE_DIRS)
        if not hits:
            unused.append(
                {
                    "view": item.view,
                    "column": item.column,
                    "suffix": item.suffix_class,
                }
            )
    return unused


def collect_typed_tokens(paths: List[Path], pattern: str) -> Dict[str, List[tuple[str, int]]]:
    import re

    compiled = re.compile(pattern)
    found: Dict[str, List[tuple[str, int]]] = {}
    for base in paths:
        for file_path in base.rglob("*"):
            if file_path.is_dir():
                continue
            if file_path.suffix not in {".py", ".json", ".yaml", ".yml", ".txt"}:
                continue
            rel = file_path.relative_to(ROOT)
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for idx, line in enumerate(lines, start=1):
                for match in compiled.finditer(line):
                    token = match.group(1)
                    found.setdefault(token, []).append((str(rel), idx))
    return found


def collect_orphans(inventory: List[ColumnMeta]) -> List[Dict[str, str]]:
    all_columns = {item.column for item in inventory}
    typed_pattern = r"['\"]([a-zA-Z0-9_]+_(?:date|until|at|amt|price|pct|area|value|ratio|rate|share|alpha|index|count))['\"]"
    occurrences = collect_typed_tokens(CODE_DIRS, typed_pattern)
    rows: List[Dict[str, str]] = []
    for token, spots in sorted(occurrences.items()):
        if token in all_columns:
            continue
        for path, line in spots:
            rows.append(
                {
                    "token": token,
                    "path": path,
                    "line": str(line),
                }
            )
    return rows


def collect_suffix_mismatches(inventory: List[ColumnMeta]) -> List[Dict[str, str]]:
    legacy_pattern = r"['\"]([a-zA-Z0-9_]+_(?:amount))['\"]"
    occurrences = collect_typed_tokens(CODE_DIRS, legacy_pattern)
    rows: List[Dict[str, str]] = []
    for token, spots in sorted(occurrences.items()):
        for path, line in spots:
            rows.append(
                {
                    "token": token,
                    "path": path,
                    "line": str(line),
                    "note": "Sufixo legado detectado (_amount → _amt)",
                }
            )
    return rows


def build_report(unused: List[Dict[str, str]], orphans: List[Dict[str, str]], mismatches: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    lines.append("# Auditoria de colunas (YAML x Código)")
    lines.append("")

    lines.append("## Novas colunas não referenciadas")
    lines.append("| View | Coluna | Sufixo |")
    lines.append("| --- | --- | --- |")
    if not unused:
        lines.append("| ✓ | Nenhuma pendência | ✓ |")
    else:
        for row in unused:
            lines.append(f"| {row['view']} | `{row['column']}` | {row['suffix']} |")
    lines.append("")

    lines.append("## Referências órfãs (não presentes nos YAMLs)")
    lines.append("| Token | Arquivo | Linha |")
    lines.append("| --- | --- | --- |")
    if not orphans:
        lines.append("| ✓ | Nenhuma ocorrência | ✓ |")
    else:
        for row in orphans:
            lines.append(f"| `{row['token']}` | {row['path']} | {row['line']} |")
    lines.append("")

    lines.append("## Quebras por sufixo / convenções")
    lines.append("| Token | Arquivo | Linha | Observação |")
    lines.append("| --- | --- | --- | --- |")
    if not mismatches:
        lines.append("| ✓ | Nenhuma inconsistência detectada | ✓ | ✓ |")
    else:
        for row in mismatches:
            lines.append(
                f"| `{row['token']}` | {row['path']} | {row['line']} | {row['note']} |"
            )
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    inventory = load_inventory()
    write_inventory_json(inventory)

    unused = collect_unreferenced_columns(inventory)
    orphans = collect_orphans(inventory)
    mismatches = collect_suffix_mismatches(inventory)

    report = build_report(unused, orphans, mismatches)
    REPORT_PATH.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
