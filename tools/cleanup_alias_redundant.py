#!/usr/bin/env python3
import os

import yaml

VIEWS_DIR = os.environ.get("VIEWS_DIR", os.path.abspath("data/views"))


def main():
    changed_total = 0
    for fn in sorted(os.listdir(VIEWS_DIR)):
        if not fn.endswith(".yaml"):
            continue
        path = os.path.join(VIEWS_DIR, fn)
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        cols = doc.get("columns") or []
        changed = False
        for col in cols:
            if isinstance(col, dict):
                name = col.get("name")
                alias = col.get("alias")
                # remove alias se for redundante (igual ao name) ou vazio
                if alias is not None and (alias == name or str(alias).strip() == ""):
                    col.pop("alias", None)
                    changed = True
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
            print(f"[ok ] cleaned aliases → {os.path.relpath(path)}")
            changed_total += 1
        else:
            print(f"[same] {os.path.relpath(path)}")
    print(f"\nFeito. Arquivos alterados: {changed_total}")


if __name__ == "__main__":
    main()
