# Changelog

All notable changes to the Snowflake Semantic Views Power BI Connector.

## [Unreleased]

### Added

- PQTest integration test suite (`tests/pqtest/`): executes the connector's
  actual M code end-to-end through the Power Query SDK's PQTest.exe against
  a live Snowflake account, with committed `.query.pqout` snapshots
  (verified byte-deterministic against the static `TPCH_RICH_DB` fixtures).
  Five categories, all passing (22/22): offline unit/SQL-generation tests
  (`RunUnitTests`/`TestParseServer`/`TestGenerateSQL`), live
  navigation/schema metadata, live data correctness (including the four
  issue #4 `SV_EDGE_*` regression views), query-folding gating
  (`--failOnFoldingFailure`), and expected-error negatives (wrapped in
  `try`, since PQTest treats raw errors as failures). The connector `.mez`
  is rebuilt from `connector/src/` before each run, validating the
  published readable source. Includes scripts for PQTest.exe acquisition
  (`Install-PQTools.ps1`), credential setup reusing the snow CLI PAT
  (`Set-PQCredential.ps1`), and fixture verification
  (`Verify-Fixtures.ps1`).

### Fixed

- **Bare multi-segment account identifiers dropped their region**: a
  server value like `cs83279.eu-west-2.aws` (no
  `.snowflakecomputing.com` suffix) was parsed by the connector's
  `ParseSnowflakeServer` as just the first segment, so no ADBC
  `uri.host` override was set and the driver built a host without the
  region - connecting to the wrong host. The connector now appends the
  standard suffix and preserves the region for such identifiers.
  Single-segment identifiers (`myaccount`, `myorg-myaccount`) are
  unchanged. The Python mirror
  (`streamlit/utils/host_builder.py:build_snowflake_host`) had the
  related inverse bug - passing a multi-segment identifier together
  with a `region` produced a double-region host - and now only injects
  the region for single-segment locators.
- **Generated M navigation no longer hangs when a semantic view,
  schema, or database is missing**: the PBIT/TMDL generators emitted
  raw nav-table key lookups (`Source{[name="..."]}[Data]`); on a
  dropped/renamed object the mashup engine's key-miss error embeds the
  entire nav table, forcing evaluation of every sibling entry (observed
  under PQTest as an out-of-memory failure after ~40 minutes). All four
  custom-connector M templates now emit defensive
  `Table.SelectRows` + `Table.IsEmpty` lookups (shared helper
  `build_defensive_custom_m_lines`) that fail fast, in seconds, with a
  clear qualified-name error. Covered by new fast negative PQTest
  snapshots (`Neg-BadDatabase-Defensive`, `Neg-BadViewName-Defensive`)
  and pytest `test_m_expression_generation.py`. Native-connector
  (`Snowflake.Databases`) templates are unchanged.

### Changed

- Connector navigation hardening: `GetSchemasForDatabase` and
  `GetTablesForSchema` now wrap their eager `SHOW` metadata queries in
  `try` (mirroring the existing `GetDatabases` wrap) and surface a
  traced `DataSource.Error` naming the missing database/schema instead
  of an opaque driver error.

### Known issues

- **Raw nav-table key lookups remain an engine-level hazard**: M code
  that navigates the connector's nav table with a raw key lookup
  (`Source{[name="..."]}[Data]`) on a missing key still triggers the
  mashup engine's expensive key-miss error path (every sibling entry is
  evaluated before failing). The connector and all generated M avoid
  the pattern as of this release; the hazard is documented by the
  excluded regression tests
  (`tests/pqtest/queries/05-negative/*.ignore`). Hand-written M against
  the connector should use the defensive `Table.SelectRows` +
  `Table.IsEmpty` pattern instead.

## [3.3.0] - 2026-07-07

### Added

- **Readable source published** (#5): the Power BI connector's M source
  (`connector/src/*.pq`/`*.pqm`) and the Streamlit PBI Template Generator's
  Python source (`streamlit/`) are now published unminified, alongside a
  `connector/build.ps1` script that rebuilds `SnowflakeSemanticViews.mez`
  from source. Previously only a minified/compiled build was shipped.
- **Local authentication for the Streamlit app** (#3): a connection form
  (Password, Key-pair file, or Browser/SSO) is shown when no
  `connections.toml` entry is found or the named connection doesn't
  exist, instead of a dead-ended error. A "Reconnect to Snowflake"
  sidebar button is available when running outside Snowflake, and
  cached sessions are checked for liveness before reuse.
- Test suite: pytest unit tests (`streamlit/tests/`), a live-Snowflake
  integration test script (`tests/integration/`) covering the
  connector's generated SQL shapes, a ported DAX Studio query pack
  (`tests/dax-studio/`, Windows/Power BI Desktop only), an M connector
  self-test (`SnowflakeSemanticViews.RunUnitTests()` /
  `TestParseServer`), ruff linting, and a GitHub Actions CI workflow.
- `tpch_sample_data/04_edge_case_svs.sql`: permanent regression fixtures
  for issue #4 (see below).
- `LICENSE` file (MIT, matching the license already referenced in
  `README.md`).

### Fixed

- **Crash on missing metadata value** (#6): `escape_m_string` in the
  Streamlit app's TMDL/PBIT generators raised
  `AttributeError: 'NoneType' object has no attribute 'replace'` when a
  column comment or other optional metadata field was `None`. It now
  returns an empty string for `None` input.
- **Warehouse not detected** (#6, root cause): `get_connection_info`
  checked the truthiness of the SQL result *list* (always non-empty)
  instead of the warehouse *value* (which can be `NULL`), so a session
  with no active warehouse silently defaulted to a fake `"XSMALL"`
  instead of prompting the user. The app now detects a missing
  warehouse and offers a warehouse override in the UI.
- **PrivateLink / legacy locator host handling on the Streamlit app
  side** (#1, #2): the app built Snowflake hostnames as
  `{account}.snowflakecomputing.com` in four places, with no PrivateLink
  or region handling - dropping the region for legacy locator accounts
  and mangling PrivateLink hosts embedded in generated M code. All host
  construction is now centralized in `streamlit/utils/host_builder.py`,
  mirroring the connector's own `ParseSnowflakeServer` semantics
  (the connector side of #1/#2 was already fixed in 3.2.0).
- Raw f-string SQL identifier interpolation in `metadata_fetcher.py`
  (e.g. `f'SHOW SCHEMAS IN DATABASE "{database}"'`) replaced with
  `validation.escape_identifier` / `build_qualified_name` throughout,
  so database/schema/object names containing quotes are handled safely.
- `WIZARD_TOTAL_STEPS`/`WIZARD_STEP_GENERATE` in `config.py` no longer
  reference a retired 4th wizard step (`step_semantic.py`, dead code
  with its `@register_page` decorator already commented out) - removed
  the dead files and corrected the constants to match the 3-step wizard.

### Investigated (not reproduced)

- **Issue #4** ("invalid identifier" when a semantic view's logical
  dimension/metric name differs from its physical column): extensively
  investigated against a live account (Snowflake 10.23.103) using the
  exact SQL shapes the connector generates - bare `SELECT logical_name`,
  `AGG()` wrapping, `WHERE` filters, multi-hop relationship dimensions,
  the metric-filter outer-subquery wrap, SQL-defined inline logical
  tables, and mixed-case/space-containing quoted names. None reproduced
  the reported error; Snowflake's documented
  `SELECT logical_name FROM semantic_view` syntax resolves the logical
  name to its underlying expression correctly in every case tested.
  Kept as a permanent regression fixture
  (`tpch_sample_data/04_edge_case_svs.sql` +
  `tests/integration/run_integration_tests.py`) rather than a code
  change, since no reproducible defect was found to fix.

### Documentation corrections

- The 3.1.0 changelog entry's "Role parameter support" claim does not
  match the current connector source, which explicitly notes
  `adbc.snowflake.sql.role` is *not* implemented (would require a new
  UI parameter). Session-level role selection is not currently
  supported by the connector; use a default role on the Snowflake user
  instead.

## [3.2.0] - 2026-03-27

### Fixed

- **PrivateLink connections failing**: The ADBC driver was not receiving the full hostname for PrivateLink URLs, causing connection errors. The connector now correctly sets the host for all PrivateLink formats.
- **Legacy locator URLs stripped of region**: Server URLs like `exxxo.west-europe.azure.snowflakecomputing.com` were reduced to `exxxo.snowflakecomputing.com`, causing 404 errors. The connector now preserves the full hostname for legacy locator formats.
- **TLS certificate mismatch on PrivateLink**: Account identifiers were being uppercased, which propagated to hostnames and caused TLS certificate validation failures. Hostnames now preserve their original case.

### URL Format Support

The connector now correctly handles all Snowflake server URL formats:

| Format                | Example                                                  | Status    |
| --------------------- | -------------------------------------------------------- | --------- |
| Org account name      | `orgname-acct.snowflakecomputing.com`                  | Supported |
| Legacy locator        | `exxxo.west-europe.azure.snowflakecomputing.com`       | Fixed     |
| PrivateLink (org)     | `orgname-acct.privatelink.snowflakecomputing.com`      | Fixed     |
| PrivateLink (locator) | `xy12345.eu-west-1.privatelink.snowflakecomputing.com` | Fixed     |

## [3.1.0] - 2025-12

### Added

- PrivateLink connection support.
- KeyPair authentication alongside PAT and OAuth.
- Configurable connection and command timeouts via UI parameters.
- High precision toggle for numeric value handling.
- DateTime precision option (microseconds / nanoseconds).
- Role parameter support (optional, for session-level Snowflake role).
- Query folding support for date, text, numeric, and aggregate functions.
- Filter expression parsing for WHERE clause generation.
- Error handling for warehouse suspended, OAuth expiration, and validation errors.

### Changed

- Migrated all query execution to ADBC with session-aware queries.
- Connection pooling for improved performance.
- Query tagging with JSON metadata for Snowflake query history.

## [3.0.0] - 2025-11

### Breaking Changes

- **Standard tables disabled**: The custom connector now only supports semantic views. Standard tables/views should use Power BI's native Snowflake connector.

### Added

- Full multi-tool ecosystem: Power BI, Tableau, Excel, Qlik, MicroStrategy support.
- Streamlit PBIT generator app for dual-source reports.

## [2.0.0]

### Added

- ADBC (Arrow Database Connectivity) migration from ODBC for faster data transfer.
- DirectQuery support for real-time queries.

### Fixed

- Column alias mismatch errors ("field 'a0' not found") eliminated by ADBC migration.

## [1.0.0]

### Added

- Initial Power BI custom connector for Snowflake Semantic Views.
- Navigation hierarchy: Databases, Schemas, Semantic Views.
- Metadata discovery via SHOW SEMANTIC DIMENSIONS/METRICS/FACTS.
- Standard SQL query generation with AGG() functions.
