#!/usr/bin/env python3
import os, sys, glob, yaml
from app.registry.service import registry_service
from app.executor.service import executor_service


def main():
    views_dir = os.environ.get("VIEWS_DIR", os.path.abspath("data/views"))
    registry_service.reload()
    yaml_entities = [i["entity"] for i in registry_service.list_all()]

    keep = []
    prune = []
    for e in yaml_entities:
        try:
            cols = executor_service.columns_for(e)
            if cols:
                keep.append(e)
            else:
                # se não conseguiu introspectar, ainda pode ser que o DB esteja vazio;
                # aqui consideramos "prune" apenas quando o DB responde "relation does not exist"
                # mas como o columns_for já levanta isso, se chegou vazio, tratamos como prune
                prune.append(e)
        except Exception as ex:
            # relação inexistente, vai para prune
            prune.append(e)

    print("=== PRUNE CANDIDATES (não existem no DB) ===")
    for e in prune:
        print(" -", e)

    # confirmar via input simples
    ans = (
        input(f"\nRemover {len(prune)} YAML(s) acima de {views_dir}? [y/N]: ")
        .strip()
        .lower()
    )
    if ans != "y":
        print("Abortado.")
        return

    removed = 0
    for e in prune:
        path = os.path.join(views_dir, f"{e}.yaml")
        if os.path.exists(path):
            os.remove(path)
            removed += 1
            print("[rm]", path)

    print(f"\nOK. Removidos {removed} YAML(s).")
    print("Dica: POST /views/reload para recarregar o catálogo no app.")


if __name__ == "__main__":
    if os.environ.get("EXECUTOR_MODE", "dummy") == "dummy":
        print("ERRO: EXECUTOR_MODE=dummy — aponte para Postgres real.", file=sys.stderr)
        sys.exit(2)
    if not os.environ.get("DATABASE_URL"):
        print("ERRO: DATABASE_URL não configurado.", file=sys.stderr)
        sys.exit(2)
    main()
