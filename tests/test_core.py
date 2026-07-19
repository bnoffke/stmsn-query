import pytest
from stmsn_query.core import (
    CATALOG_URI,
    DEFAULT_ALIAS,
    KEY_ID_VAR,
    SECRET_VAR,
    _sq,
    build_secret_sql,
    connect,
)


def test_sq_no_quotes():
    assert _sq("plain") == "plain"


def test_sq_escapes_single_quote():
    assert _sq("it's") == "it''s"


def test_sq_multiple_quotes():
    assert _sq("a'b'c") == "a''b''c"


def test_build_secret_sql_contains_values():
    sql = build_secret_sql("KEYID123", "s3cr3t")
    assert "KEYID123" in sql
    assert "s3cr3t" in sql
    assert "TYPE gcs" in sql


def test_build_secret_sql_escapes_quotes():
    sql = build_secret_sql("KEY'ID", "sec'ret")
    assert "KEY''ID" in sql
    assert "sec''ret" in sql
    assert "KEY'ID" not in sql.split("KEY''ID")[0] + sql.split("KEY''ID")[-1]


def test_connect_missing_both(monkeypatch):
    monkeypatch.delenv(KEY_ID_VAR, raising=False)
    monkeypatch.delenv(SECRET_VAR, raising=False)
    with pytest.raises(RuntimeError) as exc:
        connect()
    msg = str(exc.value)
    assert KEY_ID_VAR in msg
    assert SECRET_VAR in msg


def test_connect_missing_key_id(monkeypatch):
    monkeypatch.delenv(KEY_ID_VAR, raising=False)
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    with pytest.raises(RuntimeError) as exc:
        connect()
    assert KEY_ID_VAR in str(exc.value)
    assert "dummy_secret" not in str(exc.value)


def test_connect_missing_secret(monkeypatch):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.delenv(SECRET_VAR, raising=False)
    with pytest.raises(RuntimeError) as exc:
        connect()
    assert SECRET_VAR in str(exc.value)
    assert "dummy_key" not in str(exc.value)
