# tests/conftest.py
import os
from pathlib import Path

# carregue o .env o mais cedo possível
env_file = Path(__file__).resolve().parents[1] / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if not line or line.strip().startswith("#"):
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# valores de fallback úteis no CI
os.environ.setdefault("EXECUTOR_MODE", "read-only")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://edge_user:***@sirios_db:5432/edge_db"
)
