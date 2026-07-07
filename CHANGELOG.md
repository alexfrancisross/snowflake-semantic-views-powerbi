# Changelog

All notable changes to the Snowflake Semantic Views Power BI Connector.

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
