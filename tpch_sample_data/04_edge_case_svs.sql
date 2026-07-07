/*
 * Script: 04_edge_case_svs.sql
 * Purpose: Regression fixtures for GitHub issue #4
 *          "SQL compilation error: invalid identifier when logical dimension
 *           names differ from physical column names"
 *
 * Background:
 *   The connector generates direct "SELECT logical_name FROM semantic_view"
 *   SQL (the officially documented way to query a semantic view without the
 *   SEMANTIC_VIEW() table function - see
 *   https://docs.snowflake.com/en/user-guide/views-semantic/querying).
 *   Issue #4 claims this fails with "invalid identifier" whenever a
 *   dimension/metric/fact's logical name differs from its underlying
 *   physical column.
 *
 *   During the v3.3.0 code review this was investigated directly against a
 *   live account (cs83279.eu-west-2.aws, Snowflake version 10.23.103) using
 *   every variant below, run as plain SQL identical to what the connector's
 *   GenerateSemanticViewQuery would produce (bare SELECT, AGG() wrapper,
 *   WHERE filter, GROUP BY ordinal, outer-subquery metric-filter wrap).
 *   NONE of them reproduced "invalid identifier" - Snowflake resolves the
 *   logical name to the underlying expression correctly in every case,
 *   including SQL-defined (inline-view) logical tables and mixed-case /
 *   space-containing quoted identifiers.
 *
 *   These views are kept as a PERMANENT regression fixture: if a future
 *   Snowflake or connector change ever reintroduces the failure, the
 *   integration test suite (tests/integration/) will catch it.
 *
 * Prerequisites:
 *   - Run 01_tpch_rich_tables.sql first to create base tables
 *   - Snowflake account with Semantic Views enabled (requires Enterprise+)
 *
 * Execution:
 *   snow sql -f 04_edge_case_svs.sql
 */

-- ============================================================================
-- CONFIGURATION
-- ============================================================================
SET DB_NAME = 'TPCH_RICH_DB';
SET BASE_SCHEMA = 'TPCH_RICH_TABLES';
SET SV_SCHEMA = 'TPCH_RICH_SVS';

USE DATABASE IDENTIFIER($DB_NAME);
CREATE SCHEMA IF NOT EXISTS IDENTIFIER($SV_SCHEMA);
USE SCHEMA IDENTIFIER($SV_SCHEMA);

-- ============================================================================
-- SEMANTIC VIEW: SV_EDGE_LOGICAL_MISMATCH
-- Pattern: every dimension/metric logical name differs from its physical
-- column, across a 2-hop relationship (Region -> Nation -> Customer)
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_EDGE_LOGICAL_MISMATCH
TABLES (
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY),
    TPCH_RICH_TABLES.NATION PRIMARY KEY (N_NATIONKEY),
    TPCH_RICH_TABLES.REGION PRIMARY KEY (R_REGIONKEY)
)
RELATIONSHIPS (
    CUSTOMER_NATION AS CUSTOMER(C_NATIONKEY) REFERENCES NATION(N_NATIONKEY),
    NATION_REGION AS NATION(N_REGIONKEY) REFERENCES REGION(R_REGIONKEY)
)
DIMENSIONS (
    CUSTOMER.CUSTOMER_DISPLAY_NAME AS C_NAME COMMENT = 'Logical name differs from physical column C_NAME',
    CUSTOMER.SEGMENT_LABEL AS C_MKTSEGMENT COMMENT = 'Logical name differs from physical column C_MKTSEGMENT',
    NATION.COUNTRY_LABEL AS N_NAME COMMENT = 'Logical name differs from physical column N_NAME',
    REGION.CONTINENT_LABEL AS R_NAME COMMENT = 'Logical name differs from physical column R_NAME (2-hop relationship)'
)
METRICS (
    CUSTOMER.AVERAGE_BALANCE AS AVG(C_ACCTBAL) COMMENT = 'Logical name differs from physical column C_ACCTBAL',
    CUSTOMER.CUSTOMER_TOTAL AS COUNT(DISTINCT C_CUSTKEY) COMMENT = 'Distinct-count metric with mismatched logical name'
)
COMMENT = 'Edge case (#4 regression): every column has logical name != physical column, 2-hop relationship';

-- ============================================================================
-- SEMANTIC VIEW: SV_EDGE_INLINE_TABLE
-- Pattern: SQL-defined (inline-view) logical table, not a physical table -
-- DESCRIBE SEMANTIC VIEW omits BASE_TABLE_NAME and includes DEFINITION
-- instead; dimension/metric names still differ from the physical columns
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_EDGE_INLINE_TABLE
TABLES (
    CUSTOMER_INFO AS (
        SELECT
            C_CUSTKEY AS CUST_ID,
            C_NAME AS CUST_NAME,
            C_MKTSEGMENT AS SEGMENT_CODE,
            C_ACCTBAL AS BAL
        FROM TPCH_RICH_TABLES.CUSTOMER
    ) PRIMARY KEY (CUST_ID)
)
DIMENSIONS (
    CUSTOMER_INFO.CUSTOMER_LOGICAL_NAME AS CUSTOMER_INFO.CUST_NAME COMMENT = 'Logical name differs from inline-view column CUST_NAME',
    CUSTOMER_INFO.MARKET_SEGMENT AS CUSTOMER_INFO.SEGMENT_CODE COMMENT = 'Logical name differs from inline-view column SEGMENT_CODE'
)
METRICS (
    CUSTOMER_INFO.TOTAL_BALANCE AS SUM(CUSTOMER_INFO.BAL) COMMENT = 'Metric over an inline SQL-defined logical table'
)
COMMENT = 'Edge case (#4 regression): SQL-defined (inline-view) logical table with mismatched logical names';

-- ============================================================================
-- SEMANTIC VIEW: SV_EDGE_QUOTED_MIXED_CASE
-- Pattern: mixed-case and space-containing quoted logical names, still
-- differing from their (upper-case) physical columns
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_EDGE_QUOTED_MIXED_CASE
TABLES (
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY)
)
DIMENSIONS (
    CUSTOMER."customerName" AS CUSTOMER.C_NAME COMMENT = 'Mixed-case quoted logical name',
    CUSTOMER."Market Segment" AS CUSTOMER.C_MKTSEGMENT COMMENT = 'Space-containing quoted logical name'
)
METRICS (
    CUSTOMER."Total Balance" AS SUM(CUSTOMER.C_ACCTBAL) COMMENT = 'Space-containing quoted metric name'
)
COMMENT = 'Edge case (#4 regression): mixed-case / space-containing quoted logical names';

-- ============================================================================
-- SEMANTIC VIEW: SV_EDGE_METRIC_FILTER
-- Pattern: metric-filter scenario (outer subquery wrap) combined with
-- logical != physical names, to exercise BuildWhereClause's metric-filter
-- path alongside the mismatch
-- ============================================================================
CREATE OR REPLACE SEMANTIC VIEW SV_EDGE_METRIC_FILTER
TABLES (
    TPCH_RICH_TABLES.ORDERS PRIMARY KEY (O_ORDERKEY),
    TPCH_RICH_TABLES.CUSTOMER PRIMARY KEY (C_CUSTKEY)
)
RELATIONSHIPS (
    ORDER_CUSTOMER AS ORDERS(O_CUSTKEY) REFERENCES CUSTOMER(C_CUSTKEY)
)
DIMENSIONS (
    CUSTOMER.SEGMENT_NAME AS C_MKTSEGMENT COMMENT = 'Logical name differs from physical column C_MKTSEGMENT'
)
METRICS (
    ORDERS.REVENUE_TOTAL AS SUM(O_TOTALPRICE) COMMENT = 'Metric filtered in outer subquery wrap, logical name differs from O_TOTALPRICE'
)
COMMENT = 'Edge case (#4 regression): metric-filter (outer subquery wrap) with mismatched logical names';

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SHOW SEMANTIC VIEWS IN SCHEMA;

SELECT 'Script 04_edge_case_svs.sql completed successfully!' AS STATUS;
SELECT '4 edge-case Semantic Views created in TPCH_RICH_DB.TPCH_RICH_SVS for issue #4 regression testing' AS SUMMARY;
