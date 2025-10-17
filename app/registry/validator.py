"""
Validador dinâmico de YAMLs do catálogo Mosaic.

Valida apenas a estrutura mínima de cada arquivo:
- entity: str
- columns: list
- identifiers: list
- ask: dict (com subtópicos opcionais)
"""

import hashlib
import hmac
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from app.core.settings import settings


class AskBlock(BaseModel):
    intents: Optional[List[str]] = Field(default_factory=list)
    keywords: Optional[List[str]] = Field(default_factory=list)
    latest_words: Optional[List[str]] = Field(default_factory=list)


class ViewSchema(BaseModel):
    entity: str
    columns: List[Any]
    identifiers: List[str]
    ask: AskBlock
    signature: Optional[str] = None  # opcional: hash/assinatura


def validate_yaml_structure(data: Dict[str, Any]) -> List[str]:
    """
    Executa validação do YAML e retorna lista de mensagens de erro (vazia se válido).
    """
    try:
        ViewSchema(**data)
        return []
    except ValidationError as e:
        msgs: List[str] = []
        for err in e.errors():
            loc = ".".join(map(str, err["loc"]))
            msgs.append(f"{loc}: {err['msg']}")
        return msgs


def verify_signature(raw_text: str, data: Dict[str, Any]) -> Optional[str]:
    """
    Retorna None se OK, ou mensagem de erro se falhar.
    """
    mode = settings.views_signature_mode.lower()
    sig = (data or {}).get("signature")
    if mode == "none":
        return None
    if not sig:
        return "signature ausente no YAML"
    if mode == "sha256":
        digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        return None if sig == digest else "sha256 mismatch"
    if mode == "hmac":
        key = settings.views_signature_key or ""
        mac = hmac.new(
            key.encode("utf-8"), raw_text.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return None if hmac.compare_digest(sig, mac) else "hmac mismatch"
    return f"modo de assinatura desconhecido: {mode}"
