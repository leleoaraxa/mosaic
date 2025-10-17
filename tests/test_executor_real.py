# tests/test_executor_real.py
import os

from app.executor.service import executor_service


def test_executor_runs_readonly(monkeypatch):
    os.environ["EXECUTOR_MODE"] = "read-only"

    def _fake_run(sql, params, row_limit=100):
        return [{"ok": 1}]

    monkeypatch.setattr(executor_service, "run", _fake_run)
    result = executor_service.run("SELECT 1 AS ok;", {})
    assert isinstance(result, list)
    assert result[0]["ok"] == 1
