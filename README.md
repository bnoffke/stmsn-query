# stmsn-query

Read-only ad hoc SQL access to the stmsn civic geospatial lakehouse. No data is pulled locally: the DuckLake catalog is attached directly from GCS, and queries run against remote Parquet files. This package pins `duckdb==1.5.4` for catalog storage-version compatibility.

## Install

This package is distributed with [uv](https://docs.astral.sh/uv/). If you don't
have it yet, follow the
[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)
first — one command on macOS, Linux, and Windows.

Then:

```bash
uv tool install git+https://github.com/bnoffke/stmsn-query
```

One-off use without installing:

```bash
uvx --from git+https://github.com/bnoffke/stmsn-query stmsn-query -c "SHOW TABLES;"
```

## Credentials

Access requires GCS HMAC keys with the reader role (`storage.objectViewer` on the
`stmsn-meta` and `stmsn-lake` buckets). Keys are issued by the maintainer —
reach out and you'll be given two values: a **key ID** (starts with `GOOG1E`)
and a **secret**. Store both when you receive them; the secret cannot be
retrieved again.

Set them as environment variables.

**macOS / Linux / WSL** — add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export STMSN_GCS_KEY_ID="GOOG1E..."
export STMSN_GCS_SECRET="..."
```

Then `source ~/.bashrc` or open a new terminal.

**Windows** — in PowerShell, persist them to your user account:

```powershell
[Environment]::SetEnvironmentVariable("STMSN_GCS_KEY_ID", "GOOG1E...", "User")
[Environment]::SetEnvironmentVariable("STMSN_GCS_SECRET", "...", "User")
```

These apply to *new* terminals only, so close and reopen your terminal
afterwards — the session you ran them in won't see them. To verify:

```powershell
$env:STMSN_GCS_KEY_ID
```

The same values can also be set through the GUI: search "environment variables"
in the Start menu, then **Edit environment variables for your account**. Avoid
`set STMSN_GCS_KEY_ID=...` in `cmd`, which only lasts for that one window.

The env vars are the fallback source. The Python API also accepts credentials
directly (see [Query (Python)](#query-python)), which is what a deployed app
should use — pull them from that platform's secret store rather than exporting
env vars into the process.

Secret hygiene:
- Never commit these values to version control.
- Prefer a secrets manager, or a shell profile file with restricted permissions (`chmod 600 ~/.bashrc`).
- If a key is lost or exposed, tell the maintainer — keys are revocable per-identity and can be reissued.

## Query (CLI)

Launch the interactive DuckDB shell:

```bash
stmsn-query
```

One-off queries:

```bash
stmsn-query -c "SHOW TABLES;"
stmsn-query -c "SELECT * FROM silver.road_segments LIMIT 10;" -json
stmsn-query -c "SELECT permit_type, count(*) FROM gold.permits GROUP BY 1 ORDER BY 2 DESC;" -csv
```

### Web UI

The DuckDB CLI's `-ui` flag passes straight through, launching the local web UI
with the catalog already attached and credentials already in place. The
interactive shell stays usable in the terminal alongside it.

```bash
stmsn-query -ui
```

**Qualify your tables.** The UI opens its own connections, which start in the
`memory` catalog rather than `stmsn`. The unqualified examples elsewhere in this
README rely on the terminal shell's `USE stmsn`, and will come up empty in the
UI. Either fully-qualify:

```sql
SELECT * FROM stmsn.silver.parcels LIMIT 5;
```

or run `USE stmsn;` as the first cell, after which the unqualified forms work as
documented.

**If no browser opens** (common under WSL), use the URL the shell prints —
`http://localhost:4213` by default. The port is configurable with
`SET ui_local_port = ...` and the browser-launch command with the `.ui_command`
dot-command.

**The UI frontend is served from `https://ui.duckdb.org`**, the `ui_remote_url`
extension default. Queries and data stay local — nothing from the catalog or
`stmsn-lake` is sent there — but the page itself is not self-hosted.

The catalog is replaced daily by the dbt pipeline, so a long-lived UI session
will query stale table definitions after the daily update, same as the Python
sessions noted under [How it works](#how-it-works). Restart `stmsn-query -ui` to
reattach.

Example queries:

```sql
-- Discover available tables
SHOW TABLES;

-- Preview a silver layer table
SELECT * FROM silver.parcels LIMIT 5;

-- Aggregate from the gold layer
SELECT neighborhood, count(*) AS permit_count
FROM gold.permits
GROUP BY neighborhood
ORDER BY permit_count DESC;
```

All DuckDB shell flags (`-json`, `-csv`, `.mode`, dot-commands, pager) work unchanged.

### For agents

```bash
stmsn-query --skill
```

Prints a condensed, LLM-oriented summary of this tool — CLI invocation, the Python API, how to discover
tables, and the gotchas worth knowing. Point a coding agent at this instead of the README; it needs no
credentials, so it works before setup. This is the only flag the package itself defines; everything else
goes to DuckDB.

## Query (Python)

```python
from stmsn_query import connect

con = connect()  # reads STMSN_GCS_KEY_ID / STMSN_GCS_SECRET from the environment

# Pandas
df = con.sql("SELECT * FROM silver.parcels LIMIT 100").df()

# Polars
import polars as pl
df = pl.from_arrow(con.sql("SELECT * FROM gold.permits").arrow())
```

Credentials can also be passed explicitly, which takes precedence over the env
vars. Either argument may be omitted to fall back to its env var individually:

```python
con = connect(key_id="GOOG1E...", secret="...")
```

Streamlit pattern (reconnects once per session), pulling credentials from
`st.secrets`:

```python
import streamlit as st
from stmsn_query import connect

@st.cache_resource
def get_con():
    return connect(
        key_id=st.secrets["STMSN_GCS_KEY_ID"],
        secret=st.secrets["STMSN_GCS_SECRET"],
    )

con = get_con()
df = con.sql("SELECT * FROM gold.permits LIMIT 1000").df()
st.dataframe(df)
```

## How it works

The DuckLake catalog (`gs://stmsn-meta/catalog/stmsn.ducklake`) is attached read-only over HTTPS. Data paths for all tables are persisted inside the catalog, so queries go straight to the Parquet files in `gs://stmsn-lake/` without any local copy.

The catalog is replaced daily by the dbt pipeline. Long-lived Python sessions (Streamlit, Jupyter) will query stale table definitions after the daily update. Call `connect()` again to reattach to the current catalog.

Do not install a separate `duckdb` package alongside this one. The `duckdb==1.5.4` pin is required for catalog storage-version compatibility and must not be loosened.
