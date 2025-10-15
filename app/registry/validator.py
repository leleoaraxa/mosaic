"""
Validador dinâmico de YAMLs do catálogo Mosaic.

Valida apenas a estrutura mínima de cada arquivo:
- entity: str
- columns: list
- identifiers: list
- ask: dict (com subtópicos opcionais)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError


class AskBlock(BaseModel):
    intents: Optional[List[str]] = Field(default_factory=list)
    keywords: Optional[List[str]] = Field(default_factory=list)
    latest_words: Optional[List[str]] = Field(default_factory=list)


class ViewSchema(BaseModel):
    entity: str
    columns: List[Any]
    identifiers: List[str]
    ask: AskBlock


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
