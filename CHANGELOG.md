# Changelog

All notable changes to the Snowflake Semantic Views Power BI Connector.

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
