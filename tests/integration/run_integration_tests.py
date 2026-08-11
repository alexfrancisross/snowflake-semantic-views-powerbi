"""Live integration tests for the SnowflakeSemanticViews connector's SQL shapes.

Runs the exact SQL patterns the connector generates (grounded against
SnowflakeSemanticViews.TestGenerateSQL output via PQTest, see
tests/pqtest/queries/01-unit/TestGenerateSQL-*.query.pq) directly through
snowflake-connector-python against the live TPCH_RICH_DB.TPCH_RICH_SVS
fixtures. This has no Power BI/PQTest dependency - it's a fast way to sanity
check the connector's SQL-generation contract independent of the Mashup
Engine.

Usage:
    python tests/integration/run_integration_tests.py
    pytest tests/integration/ -v
"""

import pathlib
import tomllib
import unittest

import snowflake.connector

CONNECTIONS_TOML_PATH = pathlib.Path.home() / ".snowflake" / "connections.toml"
CONNECTION_NAME = "default"

DATABASE = "TPCH_RICH_DB"
SCHEMA = "TPCH_RICH_SVS"


def load_connection_config(toml_path: pathlib.Path = CONNECTIONS_TOML_PATH, name: str = CONNECTION_NAME) -> dict:
    if not toml_path.exists():
        raise FileNotFoundError(f"connections.toml not found at {toml_path}")
    with open(toml_path, "rb") as f:
        config = tomllib.load(f)
    if name not in config:
        raise KeyError(f"Connection '{name}' not found in {toml_path}")
    return config[name]


class SnowflakeSemanticViewSQLTests(unittest.TestCase):
    """Exercises the connector's generated-SQL shapes against live data.

    Each test's SQL is copied verbatim (or with a live LIMIT added) from a
    real SnowflakeSemanticViews.TestGenerateSQL(...) call so these tests stay
    provably in sync with what the connector actually emits.
    """

    @classmethod
    def setUpClass(cls):
        conn_cfg = load_connection_config()
        cls.conn = snowflake.connector.connect(
            account=conn_cfg["account"],
            user=conn_cfg["user"],
            password=conn_cfg["password"],
            warehouse=conn_cfg.get("warehouse", "XSMALL"),
        )

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def query(self, sql: str):
        cur = self.conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [c[0] for c in cur.description]
        return columns, rows

    def test_basic_dims_and_metric(self):
        """Two dimensions + one metric, plain GROUP BY (matches TestGenerateSQL-Basic)."""
        sql = (
            f'SELECT "REGION_NAME" AS "REGION_NAME", "NATION_NAME" AS "NATION_NAME", '
            f'AGG("TOTAL_REVENUE") AS "TOTAL_REVENUE" '
            f'FROM {DATABASE}.{SCHEMA}.SV_REGIONAL_SALES GROUP BY 1, 2'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["REGION_NAME", "NATION_NAME", "TOTAL_REVENUE"])
        self.assertGreater(len(rows), 0)

    def test_dimension_filter_sort_limit(self):
        """Dimension WHERE filter + ORDER BY + LIMIT (matches TestGenerateSQL-FilterSortLimit)."""
        sql = (
            f'SELECT "REGION_NAME" AS "REGION_NAME", AGG("TOTAL_REVENUE") AS "TOTAL_REVENUE" '
            f'FROM {DATABASE}.{SCHEMA}.SV_REGIONAL_SALES '
            f'WHERE "REGION_NAME" = \'EUROPE\' GROUP BY 1 ORDER BY 2 DESC LIMIT 10'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["REGION_NAME", "TOTAL_REVENUE"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "EUROPE")

    def test_metric_filter_outer_subquery_wrap(self):
        """Metric filter must be wrapped in an outer subquery (matches TestGenerateSQL-MetricFilterWrap)."""
        sql = (
            f'SELECT * FROM ('
            f'SELECT "SEGMENT_NAME" AS "SEGMENT_NAME", AGG("REVENUE_TOTAL") AS "REVENUE_TOTAL" '
            f'FROM {DATABASE}.{SCHEMA}.SV_EDGE_METRIC_FILTER GROUP BY 1'
            f') AS "_" WHERE "REVENUE_TOTAL" > 1000000'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["SEGMENT_NAME", "REVENUE_TOTAL"])
        for row in rows:
            self.assertGreater(row[1], 1000000)

    def test_countrows_renders_as_count_column_not_star(self):
        """COUNTROWS must render as COUNT("<col>"), never COUNT(*) (v3.3.2 regression)."""
        sql = (
            f'SELECT "REGION_NAME" AS "REGION_NAME", COUNT("REGION_NAME") AS "RowCount" '
            f'FROM {DATABASE}.{SCHEMA}.SV_REGIONAL_SALES GROUP BY 1 ORDER BY 1'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["REGION_NAME", "RowCount"])
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(row[1], 1)

    def test_ordinal_order_by_after_single_value_filter(self):
        """ORDER BY still resolves correctly after a single-value filter (issue #7 regression)."""
        sql = (
            f'SELECT "SALE_DATE" AS "SALE_DATE", "REGION_NAME" AS "REGION_NAME", '
            f'AGG("TOTAL_REVENUE") AS "TOTAL_REVENUE" '
            f'FROM {DATABASE}.{SCHEMA}.SV_DAILY_SALES '
            f'WHERE "REGION_NAME" = \'EUROPE\' GROUP BY 1, 2 ORDER BY 2, 1 LIMIT 20'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["SALE_DATE", "REGION_NAME", "TOTAL_REVENUE"])
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual(row[1], "EUROPE")

    def test_multi_value_or_filter_sql_shape(self):
        """OR-chained equality filter (IN-list shape) on a dimension folds correctly."""
        sql = (
            f'SELECT "REGION_NAME" AS "REGION_NAME", AGG("TOTAL_REVENUE") AS "TOTAL_REVENUE" '
            f'FROM {DATABASE}.{SCHEMA}.SV_CUSTOMER_ORDERS '
            f'WHERE "REGION_NAME" = \'EUROPE\' OR "REGION_NAME" = \'ASIA\' GROUP BY 1 ORDER BY 1'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["REGION_NAME", "TOTAL_REVENUE"])
        self.assertEqual(len(rows), 2)
        self.assertEqual({row[0] for row in rows}, {"ASIA", "EUROPE"})

    def test_metric_filter_actually_excludes_rows(self):
        """Metric filter (outer-subquery wrap) with a threshold that excludes some rows.

        Rigor follow-up to test_metric_filter_outer_subquery_wrap: that test's
        threshold (1,000,000) sits far below every nation's actual ~9B
        revenue, so it never excludes a row. This confirms the exclusion path
        itself works, not just the pass-through path.
        """
        baseline_sql = (
            f'SELECT "NATION_NAME" AS "NATION_NAME", AGG("TOTAL_REVENUE") AS "TOTAL_REVENUE" '
            f'FROM {DATABASE}.{SCHEMA}.SV_REGIONAL_SALES GROUP BY 1'
        )
        _, baseline_rows = self.query(baseline_sql)

        filtered_sql = (
            f'SELECT * FROM ('
            f'SELECT "NATION_NAME" AS "NATION_NAME", AGG("TOTAL_REVENUE") AS "TOTAL_REVENUE" '
            f'FROM {DATABASE}.{SCHEMA}.SV_REGIONAL_SALES GROUP BY 1'
            f') AS "_" WHERE "TOTAL_REVENUE" > 9100000000'
        )
        columns, filtered_rows = self.query(filtered_sql)
        self.assertEqual(columns, ["NATION_NAME", "TOTAL_REVENUE"])
        self.assertGreater(len(filtered_rows), 0)
        self.assertLess(len(filtered_rows), len(baseline_rows))
        for row in filtered_rows:
            self.assertGreater(row[1], 9100000000)

    def test_supply_chain_mm_view_smoke(self):
        """SV_SUPPLY_CHAIN (M:M relationship via the PARTSUPP bridge table) generates valid SQL."""
        sql = (
            f'SELECT "BRAND" AS "BRAND", AGG("TOTAL_SUPPLY_COST") AS "TOTAL_SUPPLY_COST", '
            f'AGG("TOTAL_AVAIL_QTY") AS "TOTAL_AVAIL_QTY" '
            f'FROM {DATABASE}.{SCHEMA}.SV_SUPPLY_CHAIN GROUP BY 1 ORDER BY 1 LIMIT 10'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["BRAND", "TOTAL_SUPPLY_COST", "TOTAL_AVAIL_QTY"])
        self.assertGreater(len(rows), 0)

    def test_monthly_trends_view_smoke(self):
        """SV_MONTHLY_TRENDS (pre-aggregated time-series view) generates valid SQL."""
        sql = (
            f'SELECT "YEAR_MONTH" AS "YEAR_MONTH", AGG("MONTHLY_REVENUE") AS "MONTHLY_REVENUE", '
            f'AGG("CUMULATIVE_YTD") AS "CUMULATIVE_YTD" '
            f'FROM {DATABASE}.{SCHEMA}.SV_MONTHLY_TRENDS '
            f'WHERE "YEAR" = 1997 GROUP BY 1 ORDER BY 1'
        )
        columns, rows = self.query(sql)
        self.assertEqual(columns, ["YEAR_MONTH", "MONTHLY_REVENUE", "CUMULATIVE_YTD"])
        self.assertGreater(len(rows), 0)

    def test_all_edge_case_views_smoke(self):
        """Smoke pass: every edge-case semantic view's dims+metrics query returns rows.

        A bare SELECT * against a semantic view fails (Snowflake rejects an
        unaggregated metric expression), so each case selects its own real
        dimension(s) + AGG(metric), mirroring what the connector generates.
        """
        edge_view_shapes = {
            "SV_EDGE_INLINE_TABLE": '"CUSTOMER_LOGICAL_NAME" AS "CUSTOMER_LOGICAL_NAME", '
            'AGG("TOTAL_BALANCE") AS "TOTAL_BALANCE"',
            "SV_EDGE_LOGICAL_MISMATCH": '"CUSTOMER_DISPLAY_NAME" AS "CUSTOMER_DISPLAY_NAME", '
            'AGG("AVERAGE_BALANCE") AS "AVERAGE_BALANCE"',
            "SV_EDGE_METRIC_FILTER": '"SEGMENT_NAME" AS "SEGMENT_NAME", '
            'AGG("REVENUE_TOTAL") AS "REVENUE_TOTAL"',
            "SV_EDGE_QUOTED_MIXED_CASE": '"Market Segment" AS "Market Segment", '
            'AGG("Total Balance") AS "Total Balance"',
        }
        for view, select_clause in edge_view_shapes.items():
            with self.subTest(view=view):
                sql = f'SELECT {select_clause} FROM {DATABASE}.{SCHEMA}.{view} GROUP BY 1 LIMIT 5'
                columns, rows = self.query(sql)
                self.assertGreater(len(columns), 0)
                self.assertGreater(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
