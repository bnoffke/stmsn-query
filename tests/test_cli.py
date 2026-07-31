import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from stmsn_query.cli import build_init_sql, launch, main, read_skill
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


def test_skill_documents_the_load_bearing_details():
    """Guard against the doc drifting away from what the code actually does."""
    skill = read_skill()
    assert skill.startswith("---")  # frontmatter
    assert "name: stmsn-query" in skill
    assert "SHOW TABLES" in skill  # discovery, rather than named tables
    assert "READ_ONLY" in skill
    assert "1.5.4" in skill


def test_main_skill_works_without_credentials(monkeypatch, capsys, tmp_path):
    """An agent may load the skill before the user has any keys."""
    monkeypatch.delenv(KEY_ID_VAR, raising=False)
    monkeypatch.delenv(SECRET_VAR, raising=False)
    monkeypatch.setattr("sys.argv", ["stmsn-query", "--skill"])

    def fail(argv):
        raise AssertionError(f"--skill must not launch duckdb: {argv}")

    with patch("stmsn_query.cli.launch", side_effect=fail), \
         patch("stmsn_query.cli.Path.home", return_value=tmp_path):
        main()  # no SystemExit

    out = capsys.readouterr().out
    assert out.startswith("---")
    assert not out.endswith("\n\n")  # write(), not print(), so no added newline
    # Pure stdout: nothing written to the cache dir.
    assert not (tmp_path / ".cache").exists()


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


def _no_venv_duckdb(monkeypatch, tmp_path):
    """Point sys.executable somewhere with no adjacent duckdb binary."""
    monkeypatch.setattr("stmsn_query.cli.sys.executable", str(tmp_path / "python"))


def test_main_no_duckdb_binary(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    _no_venv_duckdb(monkeypatch, tmp_path)
    with patch("shutil.which", return_value=None):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code != 0
    assert "duckdb" in capsys.readouterr().err.lower()


def test_main_prefers_venv_duckdb(monkeypatch, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    monkeypatch.setattr("sys.argv", ["stmsn-query"])
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "duckdb").touch()
    monkeypatch.setattr("stmsn_query.cli.sys.executable", str(venv_bin / "python"))

    execv_calls = []
    with patch("shutil.which", return_value="/path/duckdb"), \
         patch("os.execv", side_effect=lambda p, a: execv_calls.append((p, a))), \
         patch("stmsn_query.cli.Path.home", return_value=tmp_path):
        main()

    assert execv_calls[0][0] == str(venv_bin / "duckdb")


def test_launch_execs_on_posix(monkeypatch):
    monkeypatch.setattr("stmsn_query.cli.os.name", "posix")
    with patch("os.execv") as execv, patch("subprocess.call") as call:
        launch(["/fake/duckdb", "-init", "/tmp/init.sql"])
    execv.assert_called_once_with("/fake/duckdb", ["/fake/duckdb", "-init", "/tmp/init.sql"])
    call.assert_not_called()


def test_launch_waits_on_child_on_windows(monkeypatch):
    """os.execv would hand the console back to cmd while duckdb still runs."""
    monkeypatch.setattr("stmsn_query.cli.os.name", "nt")
    argv = [r"C:\venv\Scripts\duckdb.exe", "-init", r"C:\init.sql"]
    with patch("os.execv") as execv, patch("subprocess.call", return_value=3) as call:
        with pytest.raises(SystemExit) as exc:
            launch(argv)
    call.assert_called_once_with(argv)
    execv.assert_not_called()
    assert exc.value.code == 3  # duckdb's exit code is forwarded


def test_main_prefers_venv_duckdb_exe_on_windows(monkeypatch, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    monkeypatch.setattr("sys.argv", ["stmsn-query"])
    scripts = tmp_path / "venv" / "Scripts"
    scripts.mkdir(parents=True)
    # Windows ships only duckdb.exe; the extensionless name is absent there.
    (scripts / "duckdb.exe").touch()
    monkeypatch.setattr("stmsn_query.cli.sys.executable", str(scripts / "python.exe"))

    execv_calls = []
    with patch("shutil.which", return_value=None), \
         patch("os.execv", side_effect=lambda p, a: execv_calls.append((p, a))), \
         patch("stmsn_query.cli.Path.home", return_value=tmp_path):
        main()

    assert execv_calls[0][0] == str(scripts / "duckdb.exe")


def test_main_execv(monkeypatch, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    monkeypatch.setattr("sys.argv", ["stmsn-query", "-csv"])
    _no_venv_duckdb(monkeypatch, tmp_path)

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


def test_main_passes_through_ui_flag(monkeypatch, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    monkeypatch.setattr("sys.argv", ["stmsn-query", "-ui"])
    _no_venv_duckdb(monkeypatch, tmp_path)

    execv_calls = []

    with patch("shutil.which", return_value="/fake/duckdb"), \
         patch("os.execv", side_effect=lambda p, a: execv_calls.append((p, a))), \
         patch("stmsn_query.cli.Path.home", return_value=tmp_path):
        main()

    args = execv_calls[0][1]
    assert "-ui" in args
    # The init file must still be applied, so the UI inherits the attached
    # catalog and the GCS secret.
    assert args.index("-init") < args.index("-ui")


def test_main_init_file_written(monkeypatch, tmp_path):
    monkeypatch.setenv(KEY_ID_VAR, "dummy_key")
    monkeypatch.setenv(SECRET_VAR, "dummy_secret")
    monkeypatch.setattr("sys.argv", ["stmsn-query"])
    _no_venv_duckdb(monkeypatch, tmp_path)

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
