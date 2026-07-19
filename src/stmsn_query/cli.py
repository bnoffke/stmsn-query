import os
import shutil
import sys
from pathlib import Path

from .core import CATALOG_URI, DEFAULT_ALIAS, KEY_ID_VAR, SECRET_VAR


def build_init_sql() -> str:
    return (
        f"CREATE SECRET (TYPE gcs, KEY_ID getenv('{KEY_ID_VAR}'), SECRET getenv('{SECRET_VAR}'));\n"
        f"ATTACH '{CATALOG_URI}' AS {DEFAULT_ALIAS} (READ_ONLY);\n"
        f"USE {DEFAULT_ALIAS};\n"
    )


def main() -> None:
    missing = [v for v in (KEY_ID_VAR, SECRET_VAR) if not os.environ.get(v)]
    if missing:
        print(
            f"Error: {', '.join(missing)} not set. "
            "See the Credentials section of the README.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Prefer the pinned duckdb-cli binary installed alongside this
    # entrypoint's interpreter; a duckdb on PATH may be the wrong version.
    venv_bin = Path(sys.executable).parent / "duckdb"
    duckdb_bin = str(venv_bin) if venv_bin.is_file() else shutil.which("duckdb")
    if not duckdb_bin:
        print(
            "Error: duckdb binary not found on PATH. "
            "Reinstall stmsn-query to restore the pinned CLI.",
            file=sys.stderr,
        )
        sys.exit(1)

    init_dir = Path.home() / ".cache" / "stmsn-query"
    init_dir.mkdir(parents=True, exist_ok=True)
    init_path = init_dir / "init.sql"
    init_path.write_text(build_init_sql())

    os.execv(duckdb_bin, [duckdb_bin, "-init", str(init_path), *sys.argv[1:]])
