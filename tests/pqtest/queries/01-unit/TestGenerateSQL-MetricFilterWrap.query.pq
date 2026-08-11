// Snapshots generated SQL when a METRIC column is filtered: Snowflake
// semantic views disallow metrics in WHERE, so the generator must wrap the
// aggregate query in an outer subquery and filter there (issue #4 shape).
let
    Metadata = {
        [ColumnName = "SEGMENT_NAME", ColumnType = "TEXT", ColumnKind = "DIMENSION"],
        [ColumnName = "REVENUE_TOTAL", ColumnType = "NUMBER", ColumnKind = "METRIC"]
    },
    Filters = {
        [Column = "REVENUE_TOTAL", Operator = ">", Value = 1000000]
    }
in
    SnowflakeSemanticViews.TestGenerateSQL(
        "TPCH_RICH_DB.TPCH_RICH_SVS.SV_EDGE_METRIC_FILTER",
        {"SEGMENT_NAME", "REVENUE_TOTAL"},
        Metadata,
        null,
        null,
        null,
        null,
        null,
        Filters
    )
