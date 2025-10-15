# app/registry/loader.py
import os, yaml
from typing import Dict, Any
import logging
from app.registry.validator import validate_yaml_structure, verify_signature
from app.core.settings import settings

logger = logging.getLogger("registry.loader")


def load_views(views_dir: str) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(views_dir):
        return result
    for name in os.listdir(views_dir):
        if not name.endswith(".yaml"):
            continue
        path = os.path.join(views_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
            data = yaml.safe_load(raw) or {}
            entity = data.get("entity") or os.path.splitext(name)[0]
            result[entity] = data
            result[entity]["__file__"] = path
            # valida estrutura mínima
            errs = validate_yaml_structure(data)
            if errs:
                result[entity]["__validation_errors__"] = errs
                logger.warning(f"YAML inválido: {name} -> {errs}")
            # verificação opcional de assinatura (não bloqueia por padrão)
            sig_err = verify_signature(raw, data)
            if sig_err:
                result[entity]["__signature_ok__"] = False
                logger.warning(f"YAML assinatura inválida ({name}): {sig_err}")
                if settings.views_signature_required:
                    result[entity].setdefault("__validation_errors__", []).append(
                        f"signature: {sig_err}"
                    )
            else:
                result[entity]["__signature_ok__"] = True

    return result
