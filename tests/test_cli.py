import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from stmsn_query.cli import build_init_sql, main
from stmsn_query.core import CATALOG_URI, DEFAULT_ALIAS, KEY_ID_VAR, SECRET_VAR


def test_build_init_sql_contains_env_var_names():
    sql = build_init_sql()
    assert KEY_ID_VAR in sql
    assert SECRET_VAR in sql


def test_build_init_sql_contains_catalog_uri():
    sql = build_init_sql()
    assert CATALOG_URI in sql


def test_build_init_sql_read_only():
    sql = build_init_sql()
    assert "READ_ONLY" in sql


def test_build_init_sql_uses_alias():
    sql = build_init_sql()
    assert DEFAULT_ALIAS in sql


def test_build_init_sql_uses_getenv():
    sql = build_init_sql()
    assert "getenv(" in sql
    # No actual secret values should be present
    assert "GOOG1E" not in sql


def test_main_missing_both_vars(monkeypatch):
    monkeypatch.delenv(KEY_ID_VAR, raising=False)
    monkeypatch.delenv(SECRET_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code != 0


def test_main_missing_key_id(monkeypatch, capsys):
    monkeypatch.delenv(KEY_ID_VAR, raising=False)
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    with pytest.raises(SystemExit):
        main()
    err = capsys.readouterr().err
    assert KEY_ID_VAR in err
    assert "dummy_secret" not in err


def test_main_missing_secret(monkeypatch, capsys):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.delenv(SECRET_VAR, raising=False)
    with pytest.raises(SystemExit):
        main()
    err = capsys.readouterr().err
    assert SECRET_VAR in err
    assert "dummy_key" not in err


def test_main_no_duckdb_binary(monkeypatch, capsys):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code != 0
    assert "duckdb" in capsys.readouterr().err.lower()


def test_main_execv(monkeypatch, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    monkeypatch.setattr("sys.argv", ["stmsn-query", "-csv"])

    execv_calls = []

    def fake_execv(path, args):
        execv_calls.append((path, args))

    with patch("shutil.which", return_value="/fake/duckdb"), \
         patch("os.execv", side_effect=fake_execv), \
         patch("stmsn_query.cli.Path.home", return_value=tmp_path):
        main()

    assert len(execv_calls) == 1
    path, args = execv_calls[0]
    assert path == "/fake/duckdb"
    assert args[0] == "/fake/duckdb"
    assert "-init" in args
    assert "-csv" in args


def test_main_init_file_written(monkeypatch, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    monkeypatch.setattr("sys.argv", ["stmsn-query"])

    with patch("shutil.which", return_value="/fake/duckdb"), \
         patch("os.execv"), \
         patch("stmsn_query.cli.Path.home", return_value=tmp_path):
        main()

    init_file = tmp_path / ".cache" / "stmsn-query" / "init.sql"
    assert init_file.exists()
    content = init_file.read_text()
    assert KEY_ID_VAR in content
    assert SECRET_VAR in content
    assert "READ_ONLY" in content
