# stmsn-query

Read-only ad hoc SQL access to the stmsn civic geospatial lakehouse. No data is pulled locally: the DuckLake catalog is attached directly from GCS, and queries run against remote Parquet files. This package pins `duckdb==1.5.4` for catalog storage-version compatibility.

## Install

```bash
uv tool install git+https://github.com/bnoffke/stmsn-query
```

One-off use without installing:

```bash
uvx --from git+https://github.com/bnoffke/stmsn-query stmsn-query -c "SHOW TABLES;"
```

## Credentials

Access requires GCS HMAC keys tied to a service account or user identity that has been granted `storage.objectViewer` on the `stmsn-meta` and `stmsn-lake` buckets (the reader role). Contact the maintainer to get that grant added.

Once you have access, mint HMAC keys:

```bash
gcloud storage hmac create SERVICE_ACCOUNT_EMAIL
```

The output contains two values: `accessId` (your key ID, starts with `GOOG1E`) and `secret`. The secret is shown once. Copy both immediately.

Set these env vars in your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export STMSN_GCS_KEY_ID="GOOG1E..."
export STMSN_GCS_SECRET="..."
```

Secret hygiene:
- Never commit these values to version control.
- Prefer a secrets manager or a shell profile file with restricted permissions (`chmod 600 ~/.bashrc`).
- Keys are revocable per-identity via `gcloud storage hmac delete ACCESS_ID` if compromised.

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

## Query (Python)

```python
from stmsn_query import connect

con = connect()

# Pandas
df = con.sql("SELECT * FROM silver.parcels LIMIT 100").df()

# Polars
import polars as pl
df = pl.from_arrow(con.sql("SELECT * FROM gold.permits").arrow())
```

Streamlit pattern (reconnects once per session):

```python
import streamlit as st
from stmsn_query import connect

@st.cache_resource
def get_con():
    return connect()

con = get_con()
df = con.sql("SELECT * FROM gold.permits LIMIT 1000").df()
st.dataframe(df)
```

## How it works

The DuckLake catalog (`gs://stmsn-meta/catalog/stmsn.ducklake`) is attached read-only over HTTPS. Data paths for all tables are persisted inside the catalog, so queries go straight to the Parquet files in `gs://stmsn-lake/` without any local copy.

The catalog is replaced daily by the dbt pipeline. Long-lived Python sessions (Streamlit, Jupyter) will query stale table definitions after the daily update. Call `connect()` again to reattach to the current catalog.

Do not install a separate `duckdb` package alongside this one. The `duckdb==1.5.4` pin is required for catalog storage-version compatibility and must not be loosened.
