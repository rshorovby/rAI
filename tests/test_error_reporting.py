from error_reporting import capture_exception, init_sentry, report_failure


def test_init_sentry_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry() is False


def test_report_failure_without_sentry():
    report_failure(RuntimeError("x"), "msg")
    capture_exception(ValueError("y"))
