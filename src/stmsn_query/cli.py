import os
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

from .core import CATALOG_URI, DEFAULT_ALIAS, KEY_ID_VAR, SECRET_VAR


def read_skill() -> str:
    """The agent-facing summary of this tool, shipped alongside the package."""
    return resources.files(__package__).joinpath("SKILL.md").read_text(encoding="utf-8")


def build_init_sql() -> str:
    return (
        f"CREATE SECRET (TYPE gcs, KEY_ID getenv('{KEY_ID_VAR}'), SECRET getenv('{SECRET_VAR}'));\n"
        f"ATTACH '{CATALOG_URI}' AS {DEFAULT_ALIAS} (READ_ONLY);\n"
        f"USE {DEFAULT_ALIAS};\n"
    )


def launch(argv: list[str]) -> None:
    """Hand the console over to duckdb, however the platform allows.

    Windows has no real exec: os.execv spawns a new process and kills this one,
    so the parent shell reclaims the console and prints its prompt while duckdb
    is still running -- both then compete for stdin, and the user has to hit
    enter to untangle it. Wait on a child instead and forward its exit code.
    """
    if os.name == "nt":
        sys.exit(subprocess.call(argv))
    os.execv(argv[0], argv)


def main() -> None:
    # Agents run this to load the tool's usage into their context, often before
    # credentials exist -- so it comes first and touches nothing on disk.
    if "--skill" in sys.argv[1:]:
        sys.stdout.write(read_skill())
        return

    missing =[v for v in (KEY_ID_VAR, SECRET_VAR) if not os.environ.get(v)]
    if missing:
        print(
            f"Error: {', '.join(missing)} not set. "
            "See the Credentials section of the README.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Prefer the pinned duckdb-cli binary installed alongside this
    # entrypoint's interpreter; a duckdb on PATH may be the wrong version.
    # uv tool install only links this package's own entrypoints onto PATH, so
    # on Windows the fallback below will not find duckdb.exe at all.
    # "duckdb.exe" is the Windows name and never exists on POSIX, so probing
    # both is safe and avoids branching on the platform.
    script_dir = Path(sys.executable).parent
    duckdb_bin = next(
        (
            str(script_dir / n)
            for n in ("duckdb", "duckdb.exe")
            if (script_dir / n).is_file()
        ),
        None,
    ) or shutil.which("duckdb")
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

    launch([duckdb_bin, "-init", str(init_path), *sys.argv[1:]])
