# tests/test_executor_real.py
import os
from app.executor.service import executor_service


def test_executor_runs_readonly(monkeypatch):
    os.environ["EXECUTOR_MODE"] = "read-only"
    result = executor_service.run("SELECT 1 AS ok;", {})
    assert isinstance(result, list)
    assert result[0]["ok"] == 1
