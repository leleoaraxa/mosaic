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
) -> Tuple[Optional[str], Dict[str, List[str]]]:
    """
    Separa a descrição da view e o bloco 'ask' do COMMENT de view.
    Formato esperado:
        "<descricao humana> ||ask:key1=v1,v2; key2=x,y"
    Retorna (descricao, {"key1":[v1,v2], "key2":[x,y]})
    """
    if not raw:
        return None, {}
    parts = raw.split("||ask:", 1)
    desc = parts[0].strip() if parts[0] else None

    ask: Dict[str, List[str]] = {}
    if len(parts) > 1:
        tail = parts[1].strip()
        for part in tail.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            key = k.strip()
            vals = [x.strip() for x in v.split(",") if x.strip()]
            if key and vals:
                ask[key] = vals
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
        before = (
            yaml.safe_dump(doc.get("ask", {}), allow_unicode=True, sort_keys=True)
            if doc.get("ask")
            else ""
        )
        new = dict(doc.get("ask", {}))
        new.update(ask)
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

        parts = [p.strip() for p in str(comment).split("|", 1)]
        desc = parts[0] if parts else None
        alias = parts[1] if len(parts) > 1 else None

        if desc and (overwrite_cols or not cur.get("description")):
            if cur.get("description") != desc:
                cur["description"] = desc
                changed = True

        if alias and (overwrite_cols or not cur.get("alias")):
            if cur.get("alias") != alias:
                cur["alias"] = alias
                changed = True

    if changed:
        doc["columns"] = cols
    return doc, changed


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
