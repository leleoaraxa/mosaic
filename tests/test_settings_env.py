from app.core.settings import Settings


def test_env_override(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_URL", "http://fake-prom:9999")
    s = Settings()
    assert s.prometheus_url == "http://fake-prom:9999"
    assert s.executor_mode == "read-only"
    assert s.ask_max_limit == 1000
