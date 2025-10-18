# tools/augment_yaml_from_db_comments.py
"""
Atualiza os YAMLs em data/views com metadados vindos dos COMMENTs do Postgres.

O que faz:
- Lê COMMENT da *view* (tabelas/materialized views):
    <descricao humana> ||ask:key1=v1,v2; key2=x,y
  -> Salva:
       doc["description"] = <descricao humana>
       doc["ask"] = {"key1": [...], "key2": [...]}
- Lê COMMENT das *colunas*:
    "Descrição da coluna | Alias"
  -> Salva em cada item de doc["columns"]:
       {"name": "...", "description": "...", "alias": "..."}

Não mexe em "name". Mantém metadados existentes (synonyms etc.).

Uso:
  $env:EXECUTOR_MODE="read-only"
  $env:DATABASE_URL="postgresql://user:pass@host:5432/db"
  python tools/augment_yaml_from_db_comments.py              # dry-run
  python tools/augment_yaml_from_db_comments.py --write      # grava alterações
  python tools/augment_yaml_from_db_comments.py --entity view_fiis_info --write

Flags:
  --overwrite-view-desc   : força reescrever doc['description'] mesmo se já existir
  --overwrite-columns     : força reescrever description/alias das colunas
"""

import argparse
import copy
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import psycopg
import yaml

VIEWS_DIR = os.environ.get("VIEWS_DIR", os.path.abspath("data/views"))
SCHEMA = os.environ.get("DB_SCHEMA", "public")


# ----------------------- Postgres readers -----------------------


def get_view_comment(conn, entity: str, schema: str) -> Optional[str]:
    """
    Lê o COMMENT da própria view/tabela (compatível com materialized views).
    """
    sql = """
    SELECT obj_description(c.oid, 'pg_class') AS view_comment
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relname = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (schema, entity))
        row = cur.fetchone()
    return row[0] if row else None


def get_col_comments(conn, entity: str, schema: str) -> Dict[str, Optional[str]]:
    """
    Lê comentários de colunas direto do pg_catalog (compatível com materialized views).
    """
    sql = """
    SELECT
      a.attname AS column_name,
      pgd.description AS comment
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
    LEFT JOIN pg_catalog.pg_description pgd
           ON pgd.objoid = a.attrelid AND pgd.objsubid = a.attnum
    WHERE n.nspname = %s
      AND c.relname = %s
      AND a.attnum > 0
      AND NOT a.attisdropped
    ORDER BY a.attnum;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (schema, entity))
        rows = cur.fetchall()
    return {r[0]: r[1] for r in rows}


# ----------------------- Parsing helpers -----------------------


def parse_view_comment(
    raw: Optional[str],
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Separa a descrição da view e o bloco 'ask' do COMMENT de view.
    Formato esperado:
        "<descricao humana> ||ask:key1=v1,v2; key2=x,y"
    Retorna (descricao, {...}) com suporte a chaves aninhadas tipo "synonyms.dividends".
    """
    if not raw:
        return None, {}
    parts = raw.split("||ask:", 1)
    desc = parts[0].strip() if parts[0] else None

    def _assign_nested(d: Dict[str, Any], path: List[str], value: Any):
        """
        Atribui em d[path[0]]...[path[-1]] = values (criando dicts no caminho).
        Mantém listas no nível folha.
        """
        cur = d
        for i, key in enumerate(path):
            is_last = i == len(path) - 1
            if is_last:
                # se já existir algo, sobrescreve de forma idempotente
                cur[key] = value
            else:
                nxt = cur.get(key)
                if not isinstance(nxt, dict):
                    nxt = {}
                    cur[key] = nxt
                cur = nxt

    ask: Dict[str, Any] = {}

    def _parse_value(raw_value: str) -> Any:
        value = raw_value.strip()
        if not value:
            return None
        if (value.startswith("{") and value.endswith("}")) or (
            value.startswith("[") and value.endswith("]")
        ):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        values = [x.strip() for x in value.split(",") if x.strip()]
        return values

    if len(parts) > 1:
        tail = parts[1].strip()
        for part in tail.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            key = k.strip()
            parsed = _parse_value(v)
            if not key or parsed is None:
                continue

            # Suporta "a.b.c" -> ask["a"]["b"]["c"] = vals
            if "." in key:
                path = [p.strip() for p in key.split(".") if p.strip()]
                if path:
                    _assign_nested(ask, path, parsed)
            else:
                # nível plano
                ask[key] = parsed

    return (desc if desc else None), ask


def ensure_columns_objects(columns) -> List[Dict[str, Any]]:
    """
    Normaliza doc['columns'] para lista de dicts {name, alias?, description?}
    """
    out: List[Dict[str, Any]] = []
    for c in columns or []:
        if isinstance(c, str):
            out.append({"name": c})
        elif isinstance(c, dict):
            d = dict(c)
            # garante name
            name = d.get("name") or d.get("alias")
            if name and not d.get("name"):
                d["name"] = name
            out.append(d)
    return out


# ----------------------- Apply functions -----------------------


def apply_view_comment(
    doc: Dict[str, Any],
    view_comment: Optional[str],
    overwrite_desc: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    """
    Aplica:
      - description da view (antes do ||ask:)
      - bloco ask (após o ||ask:)
    """
    changed = False
    desc, ask = parse_view_comment(view_comment)

    # description (view-level)
    if desc:
        if overwrite_desc or not doc.get("description"):
            if doc.get("description") != desc:
                doc["description"] = desc
                changed = True

    # ask (view-level)
    if ask:
        # mescla preservando chaves existentes (deep merge raso para dicts simples)
        def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    _deep_merge(dst[k], v)
                else:
                    dst[k] = v

        before = (
            yaml.safe_dump(doc.get("ask", {}), allow_unicode=True, sort_keys=True)
            if doc.get("ask")
            else ""
        )
        new = dict(doc.get("ask", {}))
        _deep_merge(new, ask)
        after = yaml.safe_dump(new, allow_unicode=True, sort_keys=True)
        if before != after:
            doc["ask"] = new
            changed = True

    return doc, changed


def apply_col_comments(
    doc: Dict[str, Any],
    comments: Dict[str, Optional[str]],
    overwrite_cols: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    """
    Aplica description/alias nas colunas a partir do COMMENT:
      "Descrição | Alias"  -> description, alias
      "Descrição"          -> description
    """
    cols = ensure_columns_objects(doc.get("columns"))
    name_to_idx = {c.get("name"): i for i, c in enumerate(cols) if c.get("name")}
    changed = False

    for name, comment in comments.items():
        if name not in name_to_idx:
            # coluna existe no DB mas não no YAML — snapshot deve cuidar disso
            continue
        if not comment:
            continue

        i = name_to_idx[name]
        cur = cols[i]

        desc, alias, col_meta = _split_col_comment(str(comment))

        if desc and (overwrite_cols or not cur.get("description")):
            if cur.get("description") != desc:
                cur["description"] = desc
                changed = True

        if alias and (overwrite_cols or not cur.get("alias")):
            if cur.get("alias") != alias:
                cur["alias"] = alias
                changed = True

        if col_meta is not None:
            if _merge_column_ask(cur, col_meta, overwrite_cols):
                changed = True

    if changed:
        doc["columns"] = cols
    return doc, changed


def _split_col_comment(comment: str) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    meta: Optional[Dict[str, Any]] = None
    base = comment
    if "||col" in base:
        base, raw_meta = base.split("||col", 1)
        meta_str = raw_meta.lstrip(":=").strip()
        if meta_str:
            try:
                meta = json.loads(meta_str)
            except json.JSONDecodeError:
                meta = None
    parts = [p.strip() for p in base.split("|", 1)]
    desc = parts[0] if parts else None
    alias = parts[1] if len(parts) > 1 else None
    return desc, alias, meta


def _merge_column_ask(
    column: Dict[str, Any], meta: Dict[str, Any], overwrite: bool
) -> bool:
    if not isinstance(meta, dict):
        return False
    existing = column.get("ask")
    if not isinstance(existing, dict) or overwrite:
        new_meta = copy.deepcopy(meta)
        if existing != new_meta:
            column["ask"] = new_meta
            return True
        return False
    return _merge_dict_preserving(existing, meta, overwrite)


def _merge_dict_preserving(
    dst: Dict[str, Any], src: Dict[str, Any], overwrite: bool
) -> bool:
    changed = False
    for key, value in src.items():
        if isinstance(value, dict):
            current = dst.get(key)
            if isinstance(current, dict):
                if _merge_dict_preserving(current, value, overwrite):
                    changed = True
            elif overwrite or key not in dst:
                new_val = copy.deepcopy(value)
                if dst.get(key) != new_val:
                    dst[key] = new_val
                    changed = True
        else:
            if overwrite or key not in dst:
                if dst.get(key) != value:
                    dst[key] = value
                    changed = True
    return changed


# ----------------------- IO helpers -----------------------


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


# ----------------------- Main -----------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--write",
        action="store_true",
        help="Aplica e salva alterações (sem isso é dry-run).",
    )
    ap.add_argument(
        "--entity", type=str, help="Rodar apenas para uma entity específica."
    )
    ap.add_argument(
        "--overwrite-view-desc",
        action="store_true",
        help="Reescreve a description da view no YAML.",
    )
    ap.add_argument(
        "--overwrite-columns",
        action="store_true",
        help="Reescreve description/alias das colunas no YAML.",
    )
    args = ap.parse_args()

    if os.environ.get("EXECUTOR_MODE", "dummy") == "dummy":
        print("ERRO: EXECUTOR_MODE=dummy — aponte para Postgres real.", file=sys.stderr)
        sys.exit(2)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERRO: DATABASE_URL não configurado.", file=sys.stderr)
        sys.exit(2)

    if args.entity:
        paths = [os.path.join(VIEWS_DIR, f"{args.entity}.yaml")]
        if not os.path.exists(paths[0]):
            print(f"ERRO: YAML não encontrado: {paths[0]}", file=sys.stderr)
            sys.exit(2)
    else:
        paths = [
            os.path.join(VIEWS_DIR, f)
            for f in os.listdir(VIEWS_DIR)
            if f.endswith(".yaml")
        ]

    total_changed = 0

    with psycopg.connect(dsn, autocommit=True) as conn:
        for path in sorted(paths):
            doc = load_yaml(path)
            entity = doc.get("entity")
            if not entity:
                print(f"[skip] sem entity: {path}")
                continue
            try:
                # view-level (description + ask)
                vcomment = get_view_comment(conn, entity, SCHEMA)
                doc, ch1 = apply_view_comment(
                    doc, vcomment, overwrite_desc=args.overwrite_view_desc
                )

                # columns-level (description + alias)
                ccomments = get_col_comments(conn, entity, SCHEMA)
                doc, ch2 = apply_col_comments(
                    doc, ccomments, overwrite_cols=args.overwrite_columns
                )

                changed = bool(ch1 or ch2)
            except Exception as ex:
                print(f"[err ] {entity}: {ex}")
                continue

            if changed:
                total_changed += 1
                if args.write:
                    save_yaml(path, doc)
                    print(f"[ok  ] wrote → {os.path.relpath(path)}")
                else:
                    print(f"[diff] would write → {os.path.relpath(path)}")
            else:
                print(f"[same] {os.path.relpath(path)}")

    if not args.write:
        print("\n(dry-run) Use --write para salvar alterações.")
    else:
        print(f"\nFeito. Arquivos alterados: {total_changed}")


if __name__ == "__main__":
    main()
