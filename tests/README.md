# Test suite

Everything here runs manually against a live Snowflake account — there is no
CI pipeline. Three independent layers exercise the connector at different
levels:

| Layer | What it tests | Dependency |
|---|---|---|
| [`pqtest/`](pqtest) | Full Power Query M surface (nav, SQL generation, live data, folding, error handling) via the Mashup Engine | Power Query SDK's `PQTest.exe` |
| [`integration/`](integration) | The connector's generated-SQL shapes, executed directly against Snowflake | `snowflake-connector-python` only — no Power BI dependency |
| [`dax-studio/`](dax-studio) | End-to-end DAX query execution through a real Power BI Desktop DirectQuery session | Power BI Desktop + DAX Studio's `dscmd.exe` |

`streamlit/` (the sample-data setup app) is out of scope for this suite.

## One-time setup

1. Install dev dependencies:
   ```powershell
   pip install -r requirements-dev.txt
   ```
2. Confirm `~/.snowflake/connections.toml` has a `[default]` connection with
   a valid PAT (`password`), `account`, `user`, and `warehouse`. This is the
   sole credential source for every layer below — nothing here mints or
   stores a separate credential outside of PQTest's own credential cache.
3. Confirm the TPCH_RICH_DB sample dataset and semantic views are loaded:
   ```powershell
   pwsh tests/pqtest/Verify-Fixtures.ps1
   ```
   If anything's missing, load it via the `snow` CLI:
   ```powershell
   snow sql -f tpch_sample_data/01_tpch_rich_setup.sql
   # ...and the other 0N_*.sql scripts in that folder
   ```

## Running the PQTest suite

```powershell
pwsh tests/pqtest/Install-PQTools.ps1      # discovers PQTest.exe (Power Query SDK VS Code extension)
pwsh tests/pqtest/Set-PQCredential.ps1     # registers a PQTest credential from connections.toml's PAT
pwsh tests/pqtest/Run-PQTests.ps1          # rebuilds connector.mez, runs all 5 categories
```

Categories, in `tests/pqtest/queries/`:

- `01-unit/` — offline: `RunUnitTests`, `TestGenerateSQL-*`, `TestParseServer-Formats`
- `02-metadata/` — live navigation/schema discovery
- `03-data/` — live data queries, including the v3.3.2 (COUNTROWS) and issue #7 (ORDER BY after single-value filter) regressions
- `04-folding/` — run with `-foff`/`--failOnFoldingFailure` to enforce full DirectQuery folding
- `05-negative/` — expected-failure cases (bad column/database/view names, disabled tables)

Each `.query.pq` has a committed `.query.pqout` golden snapshot alongside it.
`Run-PQTests.ps1` runs PQTest's `compare` command, which diffs live output
against that snapshot (`-fomof` fails the run if a snapshot is missing) —
this catches unintended changes to generated SQL/metadata, not just
pass/fail. If you make an intentional change to SQL generation, regenerate
the snapshots and review the diff before committing:

```powershell
pwsh tests/pqtest/Run-PQTests.ps1 -UpdateSnapshots
git diff tests/pqtest/queries
```

Results are written to `tests/pqtest/results/<timestamp>/` (gitignored).

## Running the Python integration suite

```powershell
python tests/integration/run_integration_tests.py -v
# or: pytest tests/integration/ -v
```

No PQTest/Power BI dependency — runs the connector's SQL-generation shapes
directly through `snowflake-connector-python`.

## Running the DAX Studio suite

1. Open `tests/dax-studio/SnowflakeConnectorFixture.pbip` in Power BI
   Desktop. Complete the connector's auth prompt (Username/Password; the
   password is the PAT from `connections.toml`). Let the three tables
   (`SV_REGIONAL_SALES`, `SV_CUSTOMER_ORDERS`, `SV_DAILY_SALES`) load, then
   save.
2. Leave Desktop open with the file loaded, then run:
   ```powershell
   pwsh tests/dax-studio/Run-DaxStudioTests.ps1
   ```

`dscmd.exe` attaches to the already-open Desktop session for that `.pbip`
path — it does not open the file itself. This is a smoke check (does each
query execute and produce output), not a golden-value diff. Results land in
`tests/dax-studio/output/` and `tests/dax-studio/results/summary.json`
(both gitignored).

## Offline self-test baseline

Independent of all of the above, the connector ships its own offline M
self-test. From the Power Query SDK evaluation pane (no live connection
needed):

```
SnowflakeSemanticViews.RunUnitTests()
```

This should always report `AllPass = true`; it's a fast baseline check
before or after running the live suites above.
