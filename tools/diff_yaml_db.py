#!/usr/bin/env python3
"""
Diff YAML x DB para o Sirios Mosaic.

- Lista todas as views conhecidas pelo Registry (YAML em data/views).
- Para cada view, compara colunas do YAML (usando "name") com as colunas reais da view no Postgres.
- Imprime um resumo por view + um diff detalhado (faltando no DB / sobrando no DB).
- Opções:
    --json           : imprime resultado em JSON (stdout)
    --only-mismatch  : oculta views "ok"
    --entity NAME    : filtra para uma única entity
    --no-detail      : suprime o bloco detalhado, mostra só o resumo

Uso:
    # PowerShell (Windows)
    $env:EXECUTOR_MODE="read-only"
    $env:DATABASE_URL="postgresql://user:pass@host:5432/db"
    python tools/diff_yaml_db.py

    # Somente mismatches, em JSON
    python tools/diff_yaml_db.py --only-mismatch --json
"""
import os
import sys
import json
import argparse
from typing import Dict, Any, List

# Importa serviços do app
# Precisa que o projeto esteja no PYTHONPATH (rodar da raiz do projeto).
from app.registry.service import registry_service
from app.executor.service import executor_service


def yaml_colnames(entity: str) -> List[str]:
    """Colunas do YAML (Registry), considerando 'name'."""
    meta = registry_service.get(entity) or {}
    cols = meta.get("columns") or []
    out: List[str] = []
    for c in cols:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, dict):
            name = c.get("name")
            if name:
                out.append(name)
    return out


def compute_diff(entity: str) -> Dict[str, Any]:
    yaml_cols = yaml_colnames(entity)
    db_cols = executor_service.columns_for(entity)

    status = "ok"
    missing_in_db: List[str] = []
    extra_in_db: List[str] = []

    if not db_cols:
        status = "skipped (dummy or no DB)"
    else:
        missing_in_db = [c for c in yaml_cols if c not in db_cols]
        extra_in_db = [c for c in db_cols if c not in yaml_cols]
        if missing_in_db or extra_in_db:
            status = "mismatch"

    return {
        "entity": entity,
        "status": status,
        "yaml": yaml_cols,
        "db": db_cols,
        "diff": {
            "missing_in_db": missing_in_db,
            "extra_in_db": extra_in_db,
        },
    }


def print_human(results: List[Dict[str, Any]], no_detail: bool):
    # Resumo
    print("\n=== RESUMO ===")
    for r in results:
        print(f"- {r['entity']}: {r['status']}")

    # Detalhe
    if no_detail:
        return

    print("\n=== DETALHES ===")
    for r in results:
        print(f"\n[{r['entity']}]  status: {r['status']}")
        if r["status"] == "skipped (dummy or no DB)":
            continue
        mi = r["diff"]["missing_in_db"]
        ei = r["diff"]["extra_in_db"]

        if not mi and not ei:
            print("  ✓ Sem diferenças.")
            continue

        if mi:
            print("  - No YAML mas NÃO no DB (ajuste view OU remova do YAML):")
            for c in mi:
                print(f"      • {c}")
        if ei:
            print("  - No DB mas NÃO no YAML (considere adicionar no YAML):")
            for c in ei:
                print(f"      • {c}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Imprime em JSON")
    parser.add_argument(
        "--only-mismatch",
        action="store_true",
        help="Mostrar apenas views com diferenças",
    )
    parser.add_argument(
        "--entity", type=str, default=None, help="Filtra para uma única entity"
    )
    parser.add_argument(
        "--no-detail",
        action="store_true",
        help="Oculta bloco detalhado (mostra só resumo)",
    )
    args = parser.parse_args()

    if os.environ.get("EXECUTOR_MODE", "dummy") == "dummy":
        print(
            "ERRO: EXECUTOR_MODE=dummy — aponte para Postgres real (read-only).",
            file=sys.stderr,
        )
        sys.exit(2)
    if not os.environ.get("DATABASE_URL"):
        print("ERRO: DATABASE_URL não configurado.", file=sys.stderr)
        sys.exit(2)

    # Garante que o Registry está carregando dos YAMLs atuais
    registry_service.reload()

    entities = []
    if args.entity:
        entities = [args.entity]
    else:
        entities = [i["entity"] for i in registry_service.list_all()]

    results: List[Dict[str, Any]] = []
    for e in entities:
        try:
            r = compute_diff(e)
        except Exception as ex:
            r = {
                "entity": e,
                "status": f"error: {ex}",
                "yaml": [],
                "db": [],
                "diff": {"missing_in_db": [], "extra_in_db": []},
            }
        results.append(r)

    if args.only_mismatch:
        results = [
            r for r in results if r["status"] not in ("ok", "skipped (dummy or no DB)")
        ]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_human(results, no_detail=args.no_detail)


if __name__ == "__main__":
    main()
