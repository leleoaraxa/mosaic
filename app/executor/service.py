# app/executor/service.py
import os
from typing import List, Dict, Any
import psycopg
import time
import hashlib
from psycopg.rows import dict_row


class ExecutorService:
    """Executor de consultas SQL read-only, com logs e métricas."""

    def __init__(self):
        self.mode = os.environ.get("EXECUTOR_MODE", "read-only").lower()
        self.dsn = os.environ.get("DATABASE_URL")
        if not self.dsn:
            raise RuntimeError("DATABASE_URL não configurado")

    def _connect(self):
        """Abre conexão read-only (se configurado)."""
        conn = psycopg.connect(self.dsn, autocommit=True)
        if self.mode == "read-only":
            try:
                with conn.cursor() as cur:
                    cur.execute("SET default_transaction_read_only = on;")
            except Exception as e:
                print(f"[Executor] aviso: não foi possível aplicar modo read-only: {e}")
        return conn

    def _hash_sql(self, sql: str) -> str:
        return hashlib.sha1(sql.encode("utf-8")).hexdigest()[:10]

    def run(
        self, sql: str, params: Dict[str, Any] | None = None, row_limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Executa a query no Postgres e retorna as linhas."""
        start = time.perf_counter()
        with self._connect() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params or {})
                rows = cur.fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000

        # log local mínimo (pode evoluir para métricas Prometheus)
        print(
            f"[Executor] SQL {self._hash_sql(sql)} | linhas={len(rows)} | tempo={elapsed_ms:.1f}ms | modo={self.mode}"
        )

        return rows

    def columns_for(self, entity: str) -> list[str]:
        """Retorna as colunas reais da view no Postgres."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {entity} LIMIT 0;")
                return [desc[0] for desc in (cur.description or [])]


# Instância global
executor_service = ExecutorService()
