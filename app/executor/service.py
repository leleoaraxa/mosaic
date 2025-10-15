# app/executor/service.py
import os
from typing import List, Dict, Any
import psycopg


class ExecutorService:
    def __init__(self):
        self.mode = os.environ.get("EXECUTOR_MODE", "dummy")

    def run(
        self, sql: str, params: Dict[str, Any], row_limit: int = 100
    ) -> List[Dict[str, Any]]:
        if self.mode == "dummy":
            return [{"__mode": "dummy", "sql": sql, "params": params}]
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL não configurado")
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(sql, params or {})
                return cur.fetchall()

    def columns_for(self, entity: str) -> list[str]:
        """Retorna as colunas reais da view no Postgres. No dummy, vazia."""
        if self.mode == "dummy":
            return []
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL não configurado")
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {entity} LIMIT 0")
                return [desc[0] for desc in (cur.description or [])]


executor_service = ExecutorService()
